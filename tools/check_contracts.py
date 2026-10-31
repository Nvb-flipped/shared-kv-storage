"""Optional OpenAPI/schema checks against real storage and router processes."""
import json
import argparse
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading
from urllib.parse import quote
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
from sharedkv.cluster import Cluster
from sharedkv.storage import Storage
from sharedkv.transport import ApiError, Handler, request


def timeout_responses():
    """Exercise the common HTTP boundary over real sockets with a short deadline."""
    class FastDeadline(Handler):
        timeout = .2

    http = ThreadingHTTPServer(('127.0.0.1', 0), FastDeadline)
    http.daemon_threads = True
    http.app = Storage('T')
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        for contract in ('openapi.json', 'storage-openapi.json'):
            connection = HTTPConnection('127.0.0.1', http.server_port, timeout=3)
            try:
                connection.putrequest('POST', '/migrate_in')
                connection.putheader('Content-Type', 'application/json')
                connection.putheader('Content-Length', '10')
                connection.endheaders(b'{')
                response = connection.getresponse()
                if response.status != 408:
                    raise ValueError(f'Expected HTTP 408, got {response.status}.')
                yield contract, json.loads(response.read())
            finally:
                connection.close()
        if request(f'http://127.0.0.1:{http.server_port}', '/health')['status'] != 'ok':
            raise ValueError('Storage did not remain healthy after timed-out bodies.')
    finally:
        http.shutdown()
        thread.join(3)
        http.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'results/runs/api-contracts')
    args = parser.parse_args()
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        parser.error('Choose a new or empty --out directory.')
    specs = {n: json.loads((ROOT/'docs'/n).read_text()) for n in ('openapi.json', 'storage-openapi.json')}
    for spec in specs.values(): validate(spec)
    checks = []
    def check(name, schema, result):
        Draft202012Validator({'$ref': '#/components/schemas/'+schema, 'components': specs[name]['components']}).validate(result)
        checks.append({'contract': name, 'schema': schema})
    router, storage = 'openapi.json', 'storage-openapi.json'
    with Cluster() as c:
        check(router, 'Health', c.api('/admin/health'))
        check(router, 'Membership', c.api('/admin/membership'))
        check(router, 'PutResult', c.api('/put', 'POST', {'key': 'user:101', 'value': 'Apple'}))
        check(router, 'Get', c.api('/get?key=user%3A101'))
        check(router, 'Owner', c.api('/owner?key=user%3A101'))
        check(router, 'Ring', c.api('/ring?key=absent&check=1'))
        check(router, 'Stats', c.api('/stats'))
        check(router, 'Inventory', c.api('/keys'))
        for route, method, body, status in [('/get?key=missing', 'GET', None, 404),
                ('/put', 'POST', {'key': 'x', 'value': 2}, 400), ('/admin/placement', 'POST', {'mode': None}, 400),
                ('/admin/recover', 'POST', {}, 409), ('/put', 'GET', None, 405)]:
            try:
                c.api(route, method, body); raise AssertionError('Expected error')
            except ApiError as exc:
                if exc.status != status:
                    raise ValueError(f'Expected HTTP {status}, got {exc.status}.')
                check(router, 'Error', exc.json())
        check(router, 'MigrationSummary', c.api('/admin/addnode', 'POST', {'id': 'D', 'addr': c.addresses['D']}))
        check(router, 'Membership', c.api('/admin/membership'))
        check(router, 'Reconfigured', c.api('/admin/placement', 'POST', {'mode': 'modulo'}))
        check(router, 'Flush', c.api('/admin/flush', 'POST', {}))
        check(router, 'Reconfigured', c.api('/admin/vnodes', 'POST', {'v': 128}))
        check(router, 'Ring', c.api('/ring?key=x'))
        check(router, 'Ok', c.api('/admin/reset_counters', 'POST', {}))
        base = 'http://'+c.addresses['A']
        for route in ('/health', '/stats'): check(storage, 'StorageStats', request(base, route))
        check(storage, 'Ok', request(base, '/kv/'+quote('λ/fruit', safe=''), 'PUT', {'value': 'Apple'}))
        check(storage, 'KeyValue', request(base, '/kv/'+quote('λ/fruit', safe='')))
        check(storage, 'KeyList', request(base, '/keys'))
        check(storage, 'BatchResult', request(base, '/migrate_in', 'POST', {'items': [{'key': 'k', 'value': 'v'}]}))
        check(storage, 'Ok', request(base, '/kv/k', 'DELETE'))
        check(storage, 'Flush', request(base, '/keys', 'DELETE'))
    for contract, response in timeout_responses():
        if response['error'] != 'request_timeout':
            raise ValueError('The timeout error code differs from the HTTP contract.')
        check(contract, 'Error', response)
    out = args.out; out.mkdir(parents=True, exist_ok=True)
    (out/'api-audit.json').write_text(json.dumps({'author': 'Paco', 'status': 'passed', 'documents': 2, 'live_response_checks': checks}, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f'PASS: two OpenAPI 3.1 documents; {len(checks)} real response schemas.')


if __name__ == '__main__': main()
