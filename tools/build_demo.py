"""Build a standalone historical demo from public, sanitized evidence summaries."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from quote_validation import validate_quote

def main():
    fixture = json.loads((ROOT / 'examples/verified-history.json').read_text(encoding='utf-8'))
    data = {'quotes': []}
    for q in fixture['quotes']:
        ev = q['raw_evidence']
        validated = validate_quote(ev['request'], ev['response'], set(ev['menu_codes']))
        if validated['payable_yuan'] != q['payable_yuan']:
            raise ValueError('历史展示金额与原始报价不一致')
        data['quotes'].append({'id': q['id'], 'total_fen': ev['response']['result']['structuredContent']['data']['price'],
            'main_units': sum(i['quantity'] * i['main_units_per_item'] for i in q['items']),
            'drink_units': sum(i['quantity'] * i.get('drink_units_per_item', 0) for i in q['items']),
            'items': [{'name': i['name'], 'quantity': i['quantity']} for i in q['items']],
            'captured_at': q['quoted_at'], 'store_name': fixture['store_name']})
    template = (ROOT / 'web/demo.html').read_text(encoding='utf-8')
    # JSON embedded in an HTML script element must not terminate its container.
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    (ROOT / 'docs/index.html').write_text(template.replace('__HISTORY_JSON__', payload), encoding='utf-8')
    print('Built docs/index.html with', len(data['quotes']), 'historical baskets')

if __name__ == '__main__': main()
