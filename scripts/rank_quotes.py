"""Rank whole-basket MCP quotes; never infer coupon stacking or live prices."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from collections import Counter
from quote_validation import validate_quote


def money(value):
    if isinstance(value, bool):
        raise ValueError('金额不能为布尔值')
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('金额必须为数字') from exc
    if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2:
        raise ValueError('金额必须为非负、最多两位小数')
    return number


def integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(name + '必须为非负整数')
    return value


def rank(data, now=None, demo=False):
    now = now or datetime.now(timezone.utc)
    budget = money(data['budget_yuan'])
    people = integer(data['people'], '人数')
    if people < 1:
        raise ValueError('人数至少为1')
    store, mode = data['store_id'], data['dining_mode']
    if not isinstance(store, str) or not store or not isinstance(mode, str) or not mode:
        raise ValueError('门店与就餐方式不能为空')
    tags = data.get('exclude_tags', [])
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ValueError('排除标签必须为字符串数组')
    prohibited = set(tags)
    if not isinstance(data.get('quotes'), list):
        raise ValueError('quotes必须为数组')
    ttl = integer(data.get('quote_max_age_minutes', 15), '报价有效分钟数')
    if ttl < 1:
        raise ValueError('报价有效分钟数至少为1')
    valid, rejected, seen = [], [], set()
    for q in data['quotes']:
        if not isinstance(q, dict):
            rejected.append({'id': '(无效候选)', 'reason': '候选必须为对象'})
            continue
        label = q.get('id', '(缺少id)')
        try:
            if not isinstance(label, str) or not label or label in seen:
                raise ValueError('候选ID为空或重复')
            seen.add(label)
            if q['store_id'] != store or q['dining_mode'] != mode:
                raise ValueError('门店或就餐方式不一致')
            if q.get('source_tool') != 'calculate-price':
                raise ValueError('缺少calculate-price报价来源')
            if demo:
                if q.get('evidence_type') != 'synthetic-demo':
                    raise ValueError('演示模式只接受明确标记的模拟数据')
            elif q.get('evidence_type') != 'mcp-live' or not q.get('evidence_ref'):
                raise ValueError('缺少真实调用记录引用')
            if not demo:
                evidence = q.get('raw_evidence')
                if not isinstance(evidence, dict):
                    raise ValueError('缺少原始请求与响应，不能仅凭已核验标记排序')
                request = evidence['request']
                if request.get('storeCode') != store or mode != 'pickup':
                    raise ValueError('原始请求门店或就餐方式不一致')
                checked = validate_quote(request, evidence['response'], set(evidence['menu_codes']))
                if money(q['payable_yuan']) != money(checked['payable_yuan']):
                    raise ValueError('归一化应付价与原始报价不一致')
                normalized = Counter()
                for entry in q['items']:
                    count = integer(entry['quantity'], '餐品数量')
                    normalized[entry['product_code']] += count
                if normalized != Counter(checked['verified_items']):
                    raise ValueError('展示餐品与核验商品不一致')
            stamp = datetime.fromisoformat(q['quoted_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('报价时间必须带时区')
            age = now - stamp
            if age < timedelta(0) or age > timedelta(minutes=ttl):
                raise ValueError('报价过期或时间在未来')
            if q.get('payable_includes_all_fees') is not True:
                raise ValueError('未确认应付价包含全部费用')
            accepted = q.get('available') is True if demo else q.get('quote_accepted') is True
            if not accepted or q.get('constraints_checked') is not True:
                raise ValueError('未确认试算成功及适用条件')
            amount = money(q['payable_yuan'])
            if amount > budget:
                raise ValueError('超过总预算')
            items = q['items']
            if not isinstance(items, list) or not items:
                raise ValueError('候选餐品为空')
            mains, drinks = 0, 0
            for item in items:
                quantity = integer(item['quantity'], '餐品数量')
                if quantity < 1:
                    raise ValueError('餐品数量至少为1')
                if item.get('tags_complete') is not True and prohibited:
                    raise ValueError('餐品标签不完整，无法排除忌口')
                if prohibited.intersection(item.get('tags', [])):
                    raise ValueError('包含排除的口味标签')
                mains += quantity * integer(item['main_units_per_item'], '每份主食数')
                drinks += quantity * integer(item.get('drink_units_per_item', 0), '每份饮料数')
            if mains < people:
                raise ValueError('主食份数不足人数')
            if data.get('require_drinks') and drinks < people:
                raise ValueError('饮料份数不足人数')
            valid.append((amount, label, q))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            rejected.append({'id': label, 'reason': str(exc)})
    valid.sort(key=lambda row: (row[0], row[1]))
    return {
        'status': 'demo' if demo else 'live-quotes-ranked',
        'warning': '模拟数据，仅验证程序流程，不代表麦当劳真实价格。' if demo else
                   '基于原始请求与响应校验商品、数量及金额；只比较本次候选。原始证据由调用者提供，不能证明其来源真实性或保证库存。',
        'budget_yuan': str(budget), 'people': people,
        'plans': [dict(q, remaining_yuan=str(budget - price),
                       per_person_yuan=str((price / people).quantize(Decimal('0.01'))))
                  for price, _, q in valid[:3]],
        'rejected': rejected,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--demo', action='store_true')
    modes.add_argument('--replay', action='store_true', help='按记录时刻回放真实历史证据，输出不代表当前价格')
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding='utf-8'))
        # Synthetic samples use a fixed evaluation clock to remain reproducible.
        if args.replay:
            clock = max(datetime.fromisoformat(q['quoted_at'].replace('Z', '+00:00')) for q in data['quotes'])
            # Replay a collection sampled in separate sessions; freshness still
            # enforced for live operation. A replay is explicitly never live.
            oldest = min(datetime.fromisoformat(q['quoted_at'].replace('Z', '+00:00')) for q in data['quotes'])
            data['quote_max_age_minutes'] = int((clock-oldest).total_seconds() // 60) + 1
        else:
            clock = datetime.fromisoformat(data['demo_now']) if args.demo else None
        result = rank(data, now=clock, demo=args.demo)
        if args.replay:
            result['status'] = 'historical-replay-not-live'
            result['warning'] = '真实历史记录回放，按采集时刻筛选；不代表当前价格或供应状态。'
        for plan in result['plans']:
            plan.pop('raw_evidence', None)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, '输入错误: ' + str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
