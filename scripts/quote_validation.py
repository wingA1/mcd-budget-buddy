"""Validate a complete pickup basket against its original MCP request/response."""
from collections import Counter
from decimal import Decimal


class QuoteError(ValueError):
    pass


def nonnegative_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QuoteError(label + '必须是非负整数（分）')
    return value


def yuan(fen):
    return format(Decimal(nonnegative_int(fen, '金额')) / 100, '.2f')


def business_body(response):
    if not isinstance(response, dict) or response.get('error'):
        raise QuoteError('JSON-RPC调用失败')
    result = response.get('result')
    if not isinstance(result, dict) or result.get('isError'):
        raise QuoteError('MCP工具调用失败')
    body = result.get('structuredContent')
    if not isinstance(body, dict) or body.get('success') is not True or body.get('code') != 200:
        raise QuoteError('缺少结构化成功响应或业务调用失败')
    return body


def validate_quote(request, response, menu_codes):
    """Fail closed on missing products, quantities or unaccounted fees.

    Scope: pickup (orderType=1, beType=1). Does not authenticate evidence origin,
    prove current availability, or infer coupon stacking.
    """
    if request.get('orderType') != 1 or request.get('beType') != 1 or request.get('beCode'):
        raise QuoteError('当前校验器仅支持到店自取且不传beCode')
    if not isinstance(request.get('storeCode'), str) or not request['storeCode']:
        raise QuoteError('缺少门店编号')
    if request.get('withOrder'):
        raise QuoteError('此流程不支持随单购会员卡')
    expected = Counter()
    items = request.get('items')
    if not isinstance(items, list) or not items:
        raise QuoteError('请求餐品为空')
    for item in items:
        code = item.get('productCode')
        if not isinstance(code, str) or code not in menu_codes:
            raise QuoteError('请求含非本店菜单商品编码')
        count = nonnegative_int(item.get('quantity'), '商品数量')
        if count < 1:
            raise QuoteError('商品数量至少为1')
        expected[code] += count
    data = business_body(response).get('data')
    if not isinstance(data, dict):
        raise QuoteError('缺少报价data')
    actual = Counter()
    lines = data.get('productList')
    if not isinstance(lines, list) or not lines:
        raise QuoteError('返回餐品为空')
    subtotal = 0
    for line in lines:
        code = line.get('productCode')
        if not isinstance(code, str) or not code:
            raise QuoteError('返回商品编码无效')
        count = nonnegative_int(line.get('quantity'), '返回数量')
        if count < 1:
            raise QuoteError('返回商品数量至少为1')
        actual[code] += count
        subtotal += nonnegative_int(line.get('subtotal'), '商品小计')
    if actual != expected:
        raise QuoteError('返回商品编码或数量与请求不一致，拒绝少算报价')
    product = nonnegative_int(data.get('productPrice'), '商品总额')
    total = nonnegative_int(data.get('price'), '整单应付价')
    if subtotal != product:
        raise QuoteError('商品逐项小计与productPrice不一致')
    fees = {key: nonnegative_int(data.get(key, 0), key)
            for key in ('deliveryPrice', 'packingPrice', 'tablewarePrice')}
    if total != product + sum(fees.values()):
        raise QuoteError('整单总价与商品及费用之和不一致，优惠或费用口径待确认')
    return {'payable_yuan': yuan(total), 'product_yuan': yuan(product),
            'fees_yuan': {k: yuan(v) for k, v in fees.items()},
            'verified_items': dict(actual),
            'checks': ['business_success', 'menu_codes', 'product_quantities',
                       'line_subtotals', 'total_with_fees']}
