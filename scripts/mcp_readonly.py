import json, urllib.request
from pathlib import Path
import os, getpass
def call(payload):
 req=urllib.request.Request('https://mcp.mcd.cn', data=json.dumps(payload).encode(),headers=headers,method='POST')
 with urllib.request.urlopen(req,timeout=25) as r:
  if r.headers.get('Mcp-Session-Id'): headers['Mcp-Session-Id']=r.headers['Mcp-Session-Id']
  raw=r.read(2000000).decode()
  if not raw.strip(): return None
  if raw.lstrip().startswith('{'): return json.loads(raw)
  for line in raw.splitlines():
   if line.startswith('data: '):
    obj=json.loads(line[6:])
    if 'result' in obj or 'error' in obj:return obj
  raise RuntimeError('Unsupported MCP response')



import argparse
parser=argparse.ArgumentParser(description='麦当劳 MCP 只读查询及价格试算客户端；结果可能含个人数据，请妥善保管。')
parser.add_argument('tool', choices=['now-time-info','query-nearby-stores','query-meals','query-meal-detail','query-store-coupons','calculate-price'])
parser.add_argument('--arguments', type=Path, help='工具参数JSON文件；省略时为空对象')
parser.add_argument('--output', type=Path, required=True, help='私有结果文件，建议放入private目录')
args=parser.parse_args()
arguments=json.loads(args.arguments.read_text(encoding='utf-8')) if args.arguments else {}
TOKEN=os.environ.get('MCD_MCP_TOKEN') or getpass.getpass('MCD MCP Token: ')
headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
call({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'mcd-budget-buddy-validation','version':'0.1.0'}}})
headers['MCP-Protocol-Version']='2024-11-05'
call({'jsonrpc':'2.0','method':'notifications/initialized'})
result=call({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':args.tool,'arguments':arguments}})
args.output.parent.mkdir(parents=True,exist_ok=True)
# Exclusive creation prevents accidentally overwriting an existing evidence file.
with args.output.open('x', encoding='utf-8') as f:
 import os
 os.chmod(args.output,0o600)
 json.dump(result,f,ensure_ascii=False,indent=2)
print('结果已写入指定文件；公开前请脱敏。')
if 'error' in result or result.get('result',{}).get('isError'):
 raise SystemExit(1)
body=result.get('result',{}).get('structuredContent',{})
if body.get('success') is False:
 raise SystemExit(1)
