import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from datetime import datetime
import json
import subprocess
import tempfile
import unittest
import zipfile
from rank_quotes import rank
from quote_validation import validate_quote
from package_skill import build
ROOT=Path(__file__).resolve().parents[1]


class HistoryAndPackageTests(unittest.TestCase):
    def test_all_published_history_matches_original_quotes(self):
        data=json.loads((ROOT/'examples/verified-history.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['quotes']),5)
        for quote in data['quotes']:
            ev=quote['raw_evidence']
            checked=validate_quote(ev['request'],ev['response'],set(ev['menu_codes']))
            self.assertEqual(checked['payable_yuan'],quote['payable_yuan'])
        now=max(datetime.fromisoformat(q['quoted_at']) for q in data['quotes'])
        data['quote_max_age_minutes']=60
        data['require_drinks']=True
        result=rank(data,now=now)
        self.assertEqual([p['payable_yuan'] for p in result['plans']],['39.00','44.50','50.00'])

    def test_skill_archive_is_reproducible_and_runs_after_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            first=build(Path(temp)/'first.zip');second=build(Path(temp)/'second.zip')
            self.assertEqual(first.read_bytes(),second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertTrue(all('/private/' not in n for n in archive.namelist()))
                archive.extractall(Path(temp)/'unpacked')
            skill=Path(temp)/'unpacked/mcd-budget-buddy'
            command=subprocess.run([sys.executable,'scripts/rank_quotes.py','examples/quotes.demo.json','--demo'],cwd=skill,capture_output=True,text=True)
            self.assertEqual(command.returncode,0,command.stderr)
            self.assertEqual(json.loads(command.stdout)['status'],'demo')
            command=subprocess.run([sys.executable,'scripts/meal_planner.py','--help'],cwd=skill,capture_output=True,text=True)
            self.assertEqual(command.returncode,0,command.stderr)

if __name__=='__main__':unittest.main()
