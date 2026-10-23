import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import copy
from decimal import Decimal
import json
import unittest

from quote_validation import validate_quote, QuoteError, business_body, yuan
from mcp_readonly import decode_response, MCPClient, MCPError
from meal_planner import recipe_from_detail, generate_candidates, run, render_markdown


def response(data, success=True):
    return {'result': {'isError': False, 'structuredContent': {'success': success, 'code': 200 if success else 400, 'data': data}}}


def request(items=None):
    return {'storeCode': 'store', 'orderType': 1, 'beType': 1,
            'items': items or [{'productCode': 'main', 'quantity': 2}]}


def price(total=2200, product=2200, quantity=2):
    return response({'price': total, 'productPrice': product,
        'productList': [{'productCode': 'main', 'quantity': quantity, 'subtotal': product}]})


class ValidationTests(unittest.TestCase):
    def test_fen_to_yuan_and_valid_quote(self):
        self.assertEqual(validate_quote(request(), price(), {'main'})['payable_yuan'], '22.00')
        self.assertEqual(yuan(1), '0.01')

    def test_missing_or_changed_product(self):
        for mutate in ('missing', 'wrong_code', 'wrong_quantity'):
            result = price()
            data = result['result']['structuredContent']['data']
            if mutate == 'missing': data['productList'] = []
            elif mutate == 'wrong_code': data['productList'][0]['productCode'] = 'other'
            else: data['productList'][0]['quantity'] = 1
            with self.assertRaises(QuoteError): validate_quote(request(), result, {'main'})

    def test_unknown_option_code_before_quote(self):
        with self.assertRaises(QuoteError): validate_quote(request(), price(), {'different-menu-code'})

    def test_fees_are_included_once(self):
        result = price(total=2300)
        result['result']['structuredContent']['data']['packingPrice'] = 100
        self.assertEqual(validate_quote(request(), result, {'main'})['payable_yuan'], '23.00')

    def test_unexplained_total_and_line_mismatch(self):
        result = price(total=2100)
        with self.assertRaises(QuoteError): validate_quote(request(), result, {'main'})
        result = price()
        result['result']['structuredContent']['data']['productList'][0]['subtotal'] = 2000
        with self.assertRaises(QuoteError): validate_quote(request(), result, {'main'})

    def test_negative_float_or_bool_prices(self):
        for value in (-1, True, 1.5, '2200'):
            with self.assertRaises(QuoteError): validate_quote(request(), price(total=value), {'main'})

    def test_http_success_is_not_business_success(self):
        for result in ({'error': {}}, {'result': {'isError': True}}, response({}, False)):
            with self.assertRaises(QuoteError): business_body(result)

    def test_delivery_and_membership_not_implicitly_accepted(self):
        for addition in ({'beType': 2}, {'beCode': 'something'}, {'withOrder': {'cardId': 'card'}}):
            with self.assertRaises(QuoteError): validate_quote(dict(request(), **addition), price(), {'main'})


class TransportTests(unittest.TestCase):
    def test_json_and_multiline_sse(self):
        payload = {'jsonrpc': '2.0', 'id': 1, 'result': {}}
        self.assertEqual(decode_response(json.dumps(payload)), payload)
        stream = ': heartbeat\n\nevent: message\ndata: {"id": 1,\ndata: "result": {}}\n\n'
        self.assertEqual(decode_response(stream), {'id': 1, 'result': {}})

    def test_write_tool_blocked_before_network(self):
        client = object.__new__(MCPClient)
        for name in ['create-order', 'auto-bind-coupons', 'mall-create-order', 'draw-lottery']:
            with self.assertRaises(MCPError): client.call(name)


class RecipeTests(unittest.TestCase):
    def test_combo_default_rounds_and_modifications(self):
        detail = response({'code': 'combo', 'name': '麦满分组合', 'rounds': [
            {'id': 1, 'minQuantity': 1, 'maxQuantity': 1, 'choices': [
                {'code': 'inside-main', 'name': '吉士蛋麦满分', 'isDefault': 1, 'quantity': 1}]},
            {'id': 2, 'minQuantity': 1, 'maxQuantity': 1, 'choices': [
                {'code': 'inside-drink', 'name': '优品豆浆', 'isDefault': 1, 'quantity': 1}]}]})
        recipe = recipe_from_detail('combo', {'currentPrice': '15'}, detail)
        self.assertEqual(recipe['main_units_per_item'], 1)
        self.assertEqual(recipe['drink_units_per_item'], 1)
        self.assertEqual(recipe['item']['roundList'][1]['comboItemList'][0]['code'], 'inside-drink')
        self.assertEqual(recipe['item']['roundList'][0]['round'], '1')

    def test_unknown_default_requires_choice(self):
        detail = response({'code': 'combo', 'name': '组合', 'rounds': [
            {'id': 1, 'minQuantity': 1, 'choices': []}]})
        with self.assertRaises(ValueError): recipe_from_detail('combo', {'currentPrice': '10'}, detail)

    def test_beverages_not_double_counted(self):
        recipes = [dict(code='combo', main_units_per_item=1, drink_units_per_item=1, estimate_yuan=Decimal('15')),
                   dict(code='drink', main_units_per_item=0, drink_units_per_item=1, estimate_yuan=Decimal('5'))]
        baskets = generate_candidates(recipes, 2, True)
        self.assertEqual(baskets[0]['counts'], {'combo': 2})


class FakeClient:
    def __init__(self, drop=False):
        self.drop = drop
        self.calls = []

    def call(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        if name == 'query-meals':
            return response({'meals': {
                'main': {'name': '吉士蛋麦满分', 'currentPrice': '10'},
                'drink': {'name': '优品豆浆', 'currentPrice': '9.5'},
                'conditional': {'name': '超低价麦满分', 'currentPrice': '1', 'canWithOrder': True}}})
        if name == 'query-store-coupons': return response([])
        if name == 'query-meal-detail':
            return response({'code': arguments['code'], 'name': '吉士蛋麦满分' if arguments['code'] == 'main' else '优品豆浆', 'rounds': []})
        if name == 'calculate-price':
            lines = [{'productCode': x['productCode'], 'quantity': x['quantity'],
                      'subtotal': x['quantity'] * (1000 if x['productCode'] == 'main' else 950)}
                     for x in arguments['items']]
            if self.drop: lines = lines[:-1]
            total = sum(x['subtotal'] for x in lines)
            return response({'price': total, 'productPrice': total, 'productList': lines})
        raise AssertionError('Unexpected tool')


class EndToEndTests(unittest.TestCase):
    def test_query_build_validate_rank_render(self):
        client = FakeClient()
        result, session = run(client, 'store', 2, '50', True, [], [], 4)
        plan = result['plans'][0]
        self.assertEqual(plan['payable_yuan'], '39.00')
        self.assertEqual(plan['remaining_yuan'], '11.00')
        self.assertNotIn('raw_evidence', plan)
        self.assertIn('raw_evidence', session['ranking_input']['quotes'][0])
        self.assertIn('39.00', render_markdown(result))
        codes = [x['productCode'] for n,a in client.calls if n == 'calculate-price' for x in a['items']]
        self.assertNotIn('conditional', codes)
        self.assertFalse(any(n == 'create-order' for n,a in client.calls))

    def test_silent_omission_never_yields_recommendation(self):
        result, _ = run(FakeClient(drop=True), 'store', 2, '50', True, [], [], 4)
        self.assertFalse(result['plans'])
        self.assertTrue(result['failed_quotes'])

    def test_no_budget_match(self):
        result, _ = run(FakeClient(), 'store', 2, '1', True, [], [], 4)
        self.assertFalse(result['plans'])
        self.assertIn('没有满足预算', render_markdown(result))

    def test_drink_only_selection_keeps_automatic_main_pool(self):
        result, _ = run(FakeClient(), 'store', 2, '50', True, [], ['drink'], 4)
        self.assertEqual(result['plans'][0]['payable_yuan'], '39.00')

    def test_conditional_explicit_product_refused(self):
        with self.assertRaises(ValueError): run(FakeClient(), 'store', 1, '50', False, ['conditional'], [], 4)


if __name__ == '__main__': unittest.main()
