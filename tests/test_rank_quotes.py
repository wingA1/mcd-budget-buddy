import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'scripts'))
import copy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import json
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rank_quotes', root / 'scripts/rank_quotes.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((root/'examples/quotes.demo.json').read_text(encoding='utf-8'))
        self.now = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)
    def run_rank(self, demo=True):
        return module.rank(self.data, self.now, demo)
    def test_sorted_and_over_budget_rejected(self):
        out = self.run_rank()
        self.assertEqual([q['id'] for q in out['plans']], ['demo-a', 'demo-b'])
        self.assertEqual(out['plans'][0]['remaining_yuan'], '5.00')
        self.assertEqual(out['rejected'][0]['id'], 'demo-c')
    def test_demo_cannot_pass_as_live(self):
        self.assertFalse(self.run_rank(False)['plans'])
    def test_expired_quote_rejected(self):
        self.data['quotes'][0]['quoted_at'] = '2026-10-23T00:00:00+00:00'
        self.assertNotIn('demo-a', [q['id'] for q in self.run_rank()['plans']])
    def test_wrong_store_rejected(self):
        self.data['quotes'][0]['store_id'] = 'other'
        self.assertNotIn('demo-a', [q['id'] for q in self.run_rank()['plans']])
    def test_fees_not_confirmed_rejected(self):
        self.data['quotes'][0]['payable_includes_all_fees'] = False
        self.assertNotIn('demo-a', [q['id'] for q in self.run_rank()['plans']])
    def test_insufficient_mains(self):
        self.data['people'] = 3
        self.assertFalse(self.run_rank()['plans'])
    def test_exclusion_and_unknown_tags(self):
        self.data['exclude_tags'] = ['spicy']
        self.data['quotes'][0]['items'][0]['tags'] = ['spicy']
        self.data['quotes'][1]['items'][0]['tags_complete'] = False
        self.assertFalse(self.run_rank()['plans'])
    def test_money_invalid(self):
        for value in ['NaN', 'Infinity', '-1', '0.001', True]:
            with self.assertRaises(ValueError): module.money(value)
    def test_live_metadata_path(self):
        for q in self.data['quotes']:
            q['evidence_type'] = 'mcp-live'
            q['evidence_ref'] = 'unit-test-only-not-real-evidence'
        self.assertFalse(self.run_rank(False)['plans'])
    def test_future_and_naive_times(self):
        for stamp in ['2026-10-23T01:01:00+00:00', '2026-10-23T00:59:00']:
            self.data['quotes'][0]['quoted_at'] = stamp
            self.assertNotIn('demo-a', [q['id'] for q in self.run_rank()['plans']])

if __name__ == '__main__': unittest.main()
