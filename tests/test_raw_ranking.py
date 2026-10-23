import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from datetime import datetime, timezone
from copy import deepcopy
import unittest
from rank_quotes import rank
from test_pipeline import request, price


class RawEvidenceRankingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 23, 2, tzinfo=timezone.utc)
        self.data = {'people': 2, 'budget_yuan': '30.00', 'store_id': 'store', 'dining_mode': 'pickup',
          'quotes': [{'id': 'valid', 'store_id': 'store', 'dining_mode': 'pickup',
          'source_tool': 'calculate-price', 'evidence_type': 'mcp-live', 'evidence_ref': 'test-only',
          'quoted_at': self.now.isoformat(), 'payable_yuan': '22.00',
          'payable_includes_all_fees': True, 'quote_accepted': True, 'constraints_checked': True,
          'items': [{'product_code': 'main', 'name': 'test item', 'quantity': 2, 'main_units_per_item': 1}],
          'raw_evidence': {'request': request(), 'response': price(), 'menu_codes': ['main']}}]}

    def test_original_response_and_normalized_fields_match(self):
        self.assertEqual(rank(self.data, self.now)['plans'][0]['payable_yuan'], '22.00')

    def test_tampered_price_rejected(self):
        self.data['quotes'][0]['payable_yuan'] = '1.00'
        self.assertFalse(rank(self.data, self.now)['plans'])

    def test_tampered_product_rejected(self):
        self.data['quotes'][0]['items'][0]['product_code'] = 'fake'
        self.assertFalse(rank(self.data, self.now)['plans'])

    def test_tampered_store_rejected(self):
        self.data['quotes'][0]['raw_evidence']['request']['storeCode'] = 'other'
        self.assertFalse(rank(self.data, self.now)['plans'])

    def test_boolean_flag_is_insufficient(self):
        del self.data['quotes'][0]['raw_evidence']
        self.assertFalse(rank(self.data, self.now)['plans'])

    def test_malformed_candidate_produces_rejection(self):
        self.data['quotes'] = [None, 'not an object']
        self.assertEqual(len(rank(self.data, self.now)['rejected']), 2)

if __name__ == '__main__': unittest.main()
