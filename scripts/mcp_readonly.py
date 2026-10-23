"""Dependency-free MCP client restricted to reads and pickup price calculation."""
import argparse
import getpass
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ALLOWED = {'now-time-info', 'query-nearby-stores', 'query-meals',
           'query-meal-detail', 'query-store-coupons', 'calculate-price'}


class MCPError(RuntimeError):
    pass


def decode_response(raw):
    if not raw.strip():
        return None
    if raw.lstrip().startswith('{'):
        return json.loads(raw)
    # SSE data fields can span multiple lines; consume one complete RPC result.
    events = raw.replace('\r\n', '\n').split('\n\n')
    for event in events:
        data = '\n'.join(line[5:].lstrip(' ') for line in event.splitlines()
                         if line.startswith('data:'))
        if data:
            obj = json.loads(data)
            if 'result' in obj or 'error' in obj:
                return obj
    raise MCPError('未取得完整的JSON-RPC响应')


def save_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        json.dump(data, output, ensure_ascii=False, indent=2)


class MCPClient:
    def __init__(self, token):
        if not isinstance(token, str) or not token.strip():
            raise MCPError('缺少MCD_MCP_TOKEN')
        self.headers = {'Authorization': 'Bearer ' + token.strip(),
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/event-stream'}
        self.next_id = 1
        reply = self.rpc('initialize', {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'mcd-budget-buddy', 'version': '0.2.0'}})
        version = reply.get('result', {}).get('protocolVersion')
        if version != '2024-11-05':
            raise MCPError('服务器未协商本客户端支持的协议版本')
        self.headers['MCP-Protocol-Version'] = version
        self.rpc('notifications/initialized', notification=True)

    def rpc(self, method, params=None, notification=False):
        payload = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            payload['params'] = params
        if not notification:
            payload['id'] = self.next_id
            self.next_id += 1
        request = urllib.request.Request('https://mcp.mcd.cn',
                  data=json.dumps(payload).encode(), headers=self.headers, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                session = response.headers.get('Mcp-Session-Id')
                if session:
                    self.headers['Mcp-Session-Id'] = session
                if notification:
                    return None
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise MCPError('响应过大，停止读取')
                result = decode_response(raw.decode('utf-8'))
        except urllib.error.HTTPError as exc:
            # Never include request headers or full response bodies in errors.
            raise MCPError('MCP HTTP错误 ' + str(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MCPError('MCP网络连接失败或超时') from None
        if not isinstance(result, dict) or result.get('id') != payload['id']:
            raise MCPError('JSON-RPC响应ID不匹配')
        if result.get('error'):
            raise MCPError('MCP协议层返回错误')
        return result

    def list_tools(self):
        return self.rpc('tools/list', {}).get('result', {}).get('tools', [])

    def call(self, name, arguments=None):
        if name not in ALLOWED:
            raise MCPError('工具不在查询与试算白名单内')
        return self.rpc('tools/call', {'name': name, 'arguments': arguments or {}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool', choices=sorted(ALLOWED))
    parser.add_argument('--arguments', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        arguments = json.loads(args.arguments.read_text(encoding='utf-8')) if args.arguments else {}
        if not isinstance(arguments, dict):
            raise MCPError('参数必须为JSON对象')
        token = os.environ.get('MCD_MCP_TOKEN') or getpass.getpass('MCD MCP Token: ')
        result = MCPClient(token).call(args.tool, arguments)
        save_private(args.output, result)
        body = result.get('result', {}).get('structuredContent', {})
        if result.get('result', {}).get('isError') or body.get('success') is not True:
            raise MCPError('工具业务调用失败；原始结果已私有保存')
    except (MCPError, ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    print('结果已写入指定文件；公开前请脱敏。')


if __name__ == '__main__':
    main()
