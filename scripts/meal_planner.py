"""Build bounded pickup baskets, quote each with MCP, validate, and rank."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import getpass
from itertools import combinations_with_replacement
import json
import os
from pathlib import Path
import re

from mcp_readonly import MCPClient, MCPError, save_private
from quote_validation import business_body, validate_quote, QuoteError
from rank_quotes import rank

MAIN_WORDS = ('汉堡', '麦满分', '蛋堡', '鸡腿堡', '猪柳堡', '营养卷', '粥')
DRINK_WORDS = ('可乐', '豆浆', '牛奶', '美式', '橙汁', '苹果汁', '柠檬茶')


def role(name):
    if any(word in name for word in MAIN_WORDS):
        return 'main'
    if any(word in name for word in DRINK_WORDS):
        return 'drink'
    return 'other'


def estimate(item):
    try:
        amount = Decimal(str(item.get('currentPrice')))
        return amount if amount.is_finite() and amount >= 0 else None
    except InvalidOperation:
        return None


def default_modification(data):
    values = []
    for group in (data.get('modification') or {}).get('items', []):
        selected = 0
        for value in group.get('values', []):
            count = value.get('selectedQuantity', 0)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError('特制默认数量无法解析')
            if count:
                key = value.get('selectedKey')
                if not key:
                    raise ValueError('特制选中key缺失')
                selected += count
            else:
                key = value.get('unselectedKey')
            if key:
                values.append({'code': value['code'], 'key': key, 'quantity': count})
        if selected < group.get('minValues', 0) or selected > group.get('maxValues', selected):
            raise ValueError('特制默认数量不满足约束')
    return {'values': values} if values else None


def recipe_from_detail(code, menu_item, detail):
    """Use exact default rounds, never invent an unselected combo choice."""
    data = business_body(detail)['data']
    if data.get('code') != code:
        raise ValueError('详情商品编码不匹配')
    item = {'productCode': code, 'quantity': 1}
    modification = default_modification(data)
    if modification:
        item['modification'] = modification
    rounds, mains, drinks, components = [], 0, 0, []
    for group in data.get('rounds') or []:
        selected = []
        for choice in group.get('choices', []):
            if choice.get('isDefault') != 1:
                continue
            count = choice.get('quantity')
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise ValueError('套餐默认选项缺少正整数数量')
            selected_item = {'code': choice['code'], 'quantity': count}
            mod = default_modification(choice)
            if mod:
                selected_item['modification'] = mod
            selected.append(selected_item)
            kind = role(choice.get('name', ''))
            mains += count if kind == 'main' else 0
            drinks += count if kind == 'drink' else 0
            components.append({'name': choice.get('name', ''), 'quantity': count})
        count = sum(x['quantity'] for x in selected)
        if not selected or count < group.get('minQuantity', 0) or count > group.get('maxQuantity', count):
            raise ValueError('套餐默认搭配不完整，需用户选择后再试算')
        rounds.append({'round': str(group['id']), 'comboItemList': selected})
    if rounds:
        item['roundList'] = rounds
    else:
        kind = role(data.get('name', ''))
        mains = int(kind == 'main')
        drinks = int(kind == 'drink')
    return {'code': code, 'name': data['name'], 'item': item,
            'main_units_per_item': mains, 'drink_units_per_item': drinks,
            'components': components, 'estimate_yuan': estimate(menu_item)}


def generate_candidates(recipes, people, with_drinks=False, limit=6):
    if isinstance(people, bool) or not isinstance(people, int) or not 1 <= people <= 6:
        raise ValueError('人数仅支持1—6人')
    if not 1 <= limit <= 6:
        raise ValueError('每次最多核价6个候选')
    mains = sorted([r for r in recipes if r['main_units_per_item'] > 0],
                   key=lambda r: (r['estimate_yuan'] or Decimal(0), r['code']))[:6]
    beverages = sorted([r for r in recipes if r['main_units_per_item'] == 0 and r['drink_units_per_item'] > 0],
                       key=lambda r: (r['estimate_yuan'] or Decimal(0), r['code']))[:3]
    by_code = {r['code']: r for r in recipes}
    baskets = {}
    for size in range(1, people + 1):
        for choices in combinations_with_replacement(mains, size):
            coverage = sum(r['main_units_per_item'] for r in choices)
            if coverage != people:
                continue
            counts = Counter(r['code'] for r in choices)
            drinks = sum(r['drink_units_per_item'] for r in choices)
            missing = max(people - drinks, 0) if with_drinks else 0
            additions = beverages if missing else [None]
            for beverage in additions:
                count_copy = counts.copy()
                if beverage:
                    count_copy[beverage['code']] += missing
                key = tuple(sorted(count_copy.items()))
                estimated = sum((by_code[c]['estimate_yuan'] or Decimal(0)) * n for c, n in key)
                baskets[key] = {'counts': dict(key), 'estimate_yuan': estimated}
    # Prefer one affordable homogeneous plan per main recipe, then mixed options.
    # This bounds calls and improves variety without claiming a global optimum.
    ordered = sorted(baskets.values(), key=lambda b: (b['estimate_yuan'], tuple(b['counts'].items())))
    selected, primary_seen = [], set()
    for basket in ordered:
        primary = tuple(c for c in basket['counts'] if by_code[c]['main_units_per_item'])
        if len(primary) == 1 and primary not in primary_seen:
            selected.append(basket)
            primary_seen.add(primary)
        if len(selected) == limit:
            break
    for basket in ordered:
        if len(selected) == limit:
            break
        if basket not in selected:
            selected.append(basket)
    return selected


def run(client, store_code, people, budget, with_drinks, main_codes, drink_codes, max_candidates):
    from copy import deepcopy
    context = {'storeCode': store_code, 'orderType': 1, 'beType': 1}
    catalog_response = client.call('query-meals', context)
    catalog = business_body(catalog_response)['data']['meals']
    if not isinstance(catalog, dict):
        raise ValueError('菜单结构不符合预期')
    coupons_response = client.call('query-store-coupons', context)
    coupons = business_body(coupons_response)['data']
    skipped = []
    # Exclude conditional membership prices entirely; never buy a card implicitly.
    eligible = {code: item for code, item in catalog.items()
                if not item.get('canWithOrder') and not item.get('withOrder')}
    requested = list(dict.fromkeys(main_codes + drink_codes))
    unknown = [code for code in requested if code not in eligible]
    if unknown:
        raise ValueError('指定餐品不存在或要求随单购卡：' + ', '.join(unknown))
    def pick(kind, count):
        return [code for code, item in sorted(eligible.items(), key=lambda row: (
                estimate(row[1]) if estimate(row[1]) is not None else Decimal('Infinity'), row[0]))
                if role(item.get('name', '')) == kind and estimate(item) is not None][:count]
    selected_codes = list(dict.fromkeys(main_codes)) if main_codes else pick('main', 4)
    if with_drinks:
        selected_codes += drink_codes if drink_codes else pick('drink', 2)
    selected_codes = list(dict.fromkeys(selected_codes))
    recipes, raw_records = [], []
    for code in selected_codes:
        detail = client.call('query-meal-detail', dict(context, code=code))
        raw_records.append({'tool': 'query-meal-detail', 'arguments': dict(context, code=code), 'response': detail})
        try:
            recipes.append(recipe_from_detail(code, eligible[code], detail))
        except (ValueError, KeyError, TypeError) as exc:
            skipped.append({'code': code, 'reason': str(exc)})
    candidates = generate_candidates(recipes, people, with_drinks, max_candidates)
    if not candidates:
        raise ValueError('候选不足：未能确认足够主食或饮料，请指定菜单中的餐品编码')
    by_code = {r['code']: r for r in recipes}
    quotes, failed = [], []
    for index, candidate in enumerate(candidates):
        request = dict(context, needTableware=False, items=[])
        for code, count in candidate['counts'].items():
            product = deepcopy(by_code[code]['item'])
            product['quantity'] = count
            request['items'].append(product)
        response = client.call('calculate-price', request)
        captured = datetime.now(timezone.utc).isoformat()
        record = {'tool': 'calculate-price', 'arguments': request, 'response': response, 'captured_at': captured}
        raw_records.append(record)
        try:
            checked = validate_quote(request, response, set(catalog))
            quote = {'id': 'candidate-' + str(index + 1), 'store_id': store_code,
                'dining_mode': 'pickup', 'source_tool': 'calculate-price', 'evidence_type': 'mcp-live',
                'evidence_ref': 'private session record #' + str(len(raw_records)),
                'quoted_at': captured, 'payable_yuan': checked['payable_yuan'],
                'payable_includes_all_fees': True, 'constraints_checked': True,
                'quote_accepted': True, 'raw_evidence': {'request': request, 'response': response,
                                                       'menu_codes': list(catalog)},
                'validation': checked, 'items': []}
            for code, count in candidate['counts'].items():
                recipe = by_code[code]
                quote['items'].append({'product_code': code, 'name': recipe['name'], 'quantity': count,
                    'main_units_per_item': recipe['main_units_per_item'],
                    'drink_units_per_item': recipe['drink_units_per_item'],
                    'components': recipe['components'], 'tags': [], 'tags_complete': False})
            quotes.append(quote)
        except (QuoteError, KeyError, TypeError) as exc:
            failed.append({'id': 'candidate-' + str(index + 1), 'reason': str(exc)})
    ranking_input = {'budget_yuan': budget, 'people': people, 'store_id': store_code,
                     'dining_mode': 'pickup', 'require_drinks': with_drinks,
                     'exclude_tags': [], 'quotes': quotes}
    result = rank(ranking_input)
    for plan in result['plans']:
        # Raw payloads may contain personal metadata; keep them in private session only.
        plan.pop('raw_evidence', None)
    result.update({'store_code': store_code, 'with_drinks': with_drinks,
                   'candidates_quoted': len(candidates), 'coupon_count': len(coupons),
                   'coupon_policy': '仅查询可用券，未自动领券或应用任何券',
                   'failed_quotes': failed, 'skipped_recipes': skipped,
                   'generated_at': datetime.now(timezone.utc).isoformat()})
    session = {'catalog_response': catalog_response, 'coupons_response': coupons_response,
               'records': raw_records, 'ranking_input': ranking_input}
    return result, session


def render_markdown(result):
    rows = ['# 麦麦预算官 · 到店配餐报告', '',
            '门店编号：' + result['store_code'] + '｜人数：' + str(result['people']) +
            '｜总预算：¥' + result['budget_yuan'], '',
            '| 方案 | 餐品与数量 | 应付价 | 人均 | 预算余额 |',
            '| --- | --- | ---: | ---: | ---: |']
    def safe(text):
        return str(text).replace('|', '／').replace('\n', ' ')
    for i, plan in enumerate(result['plans'], 1):
        items = '；'.join(safe(x['name']) + ' ×' + str(x['quantity']) for x in plan['items'])
        rows.append('| ' + str(i) + ' | ' + items + ' | ¥' + plan['payable_yuan'] +
                    ' | ¥' + plan['per_person_yuan'] + ' | ¥' + plan['remaining_yuan'] + ' |')
    if not result['plans']:
        rows += ['', '**本次已核价候选中，没有满足预算与人数要求的方案。**']
    rows += ['', '查询时间：' + result['generated_at'], '',
             '本次核价 ' + str(result['candidates_quoted']) + ' 个候选；' + result['coupon_policy'] + '。', '',
             '只比较本次候选，不保证全菜单最低价。主食/饮料份数是数量约束，不保证饱腹或过敏安全。价格和供应以官方实时结果为准。']
    return '\n'.join(rows) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store-code', required=True)
    parser.add_argument('--people', type=int, default=1)
    parser.add_argument('--budget', required=True)
    parser.add_argument('--with-drinks', action='store_true')
    parser.add_argument('--main-code', action='append', default=[])
    parser.add_argument('--drink-code', action='append', default=[])
    parser.add_argument('--max-candidates', type=int, default=4)
    parser.add_argument('--output-dir', type=Path, required=True, help='必须为尚不存在的新目录；含私有响应')
    args = parser.parse_args()
    try:
        from rank_quotes import money
        money(args.budget)
        if not 1 <= args.people <= 6 or not 1 <= args.max_candidates <= 6:
            raise ValueError('人数须为1—6，核价候选数须为1—6')
        if args.output_dir.exists():
            raise ValueError('输出目录已存在，请换用新目录')
        args.output_dir.mkdir(parents=True, mode=0o700)
        token = os.environ.get('MCD_MCP_TOKEN') or getpass.getpass('MCD MCP Token: ')
        client = MCPClient(token)
        result, session = run(client, args.store_code, args.people, args.budget,
                              args.with_drinks, args.main_code, args.drink_code, args.max_candidates)
        save_private(args.output_dir / 'session.json', session)
        save_private(args.output_dir / 'result.json', result)
        report = render_markdown(result)
        path = args.output_dir / 'report.md'
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(report)
        print(report)
    except (ValueError, KeyError, TypeError, OSError, MCPError) as exc:
        parser.exit(2, '配餐停止：' + str(exc) + '\n')


if __name__ == '__main__':
    main()
