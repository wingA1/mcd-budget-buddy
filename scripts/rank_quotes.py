"""Rank whole-basket MCP quotes; never infer coupon stacking or live prices."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path


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
    prohibited = set(data.get('exclude_tags', []))
    ttl = integer(data.get('quote_max_age_minutes', 15), '报价有效分钟数')
    if ttl < 1:
        raise ValueError('报价有效分钟数至少为1')
    valid, rejected, seen = [], [], set()
    for q in data['quotes']:
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
            stamp = datetime.fromisoformat(q['quoted_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('报价时间必须带时区')
            age = now - stamp
            if age < timedelta(0) or age > timedelta(minutes=ttl):
                raise ValueError('报价过期或时间在未来')
            if q.get('payable_includes_all_fees') is not True:
                raise ValueError('未确认应付价包含全部费用')
            if q.get('available') is not True or q.get('constraints_checked') is not True:
                raise ValueError('未确认供应状态及优惠适用条件')
            amount = money(q['payable_yuan'])
            if amount > budget:
                raise ValueError('超过总预算')
            items = q['items']
            if not isinstance(items, list) or not items:
                raise ValueError('候选餐品为空')
            mains = 0
            for item in items:
                quantity = integer(item['quantity'], '餐品数量')
                if quantity < 1:
                    raise ValueError('餐品数量至少为1')
                if item.get('tags_complete') is not True and prohibited:
                    raise ValueError('餐品标签不完整，无法排除忌口')
                if prohibited.intersection(item.get('tags', [])):
                    raise ValueError('包含排除的口味标签')
                mains += quantity * integer(item['main_units_per_item'], '每份主食数')
            if mains < people:
                raise ValueError('主食份数不足人数')
            valid.append((amount, label, q))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            rejected.append({'id': label, 'reason': str(exc)})
    valid.sort(key=lambda row: (row[0], row[1]))
    return {
        'status': 'demo' if demo else 'live-quotes-ranked',
        'warning': '模拟数据，仅验证程序流程，不代表麦当劳真实价格。' if demo else
                   '只在已查询的候选中按报价排序；不是全菜单最低价保证。引用由调用者提供，程序不验证记录真实性。',
        'budget_yuan': str(budget), 'people': people,
        'plans': [dict(q, remaining_yuan=str(budget - price),
                       per_person_yuan=str((price / people).quantize(Decimal('0.01'))))
                  for price, _, q in valid[:3]],
        'rejected': rejected,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding='utf-8'))
        # Synthetic samples use a fixed evaluation clock to remain reproducible.
        clock = datetime.fromisoformat(data['demo_now']) if args.demo else None
        result = rank(data, now=clock, demo=args.demo)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, '输入错误: ' + str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
