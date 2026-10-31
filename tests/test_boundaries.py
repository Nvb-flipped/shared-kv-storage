"""Regression checks for malformed external input and unsupported operations."""
from contextlib import contextmanager
from http.client import HTTPConnection
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sharedkv.analysis import load_run
from sharedkv.cluster import Cluster
from sharedkv.config import ClusterConfig, ConfigError, ExperimentConfig, StudyConfig
from sharedkv.experiment import run_case
from sharedkv.storage import Storage
from sharedkv.study import digest, run_study, write_json
from sharedkv.transport import ApiError, Handler, decode_json, request, server

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def running_server(app):
    http = server(app, 0)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield http.server_port
    finally:
        http.shutdown()
        thread.join(5)
        http.server_close()


class ExternalBoundaryTests(unittest.TestCase):
    def test_initial_storage_addresses_cannot_alias_one_physical_process(self):
        from sharedkv.router import Router
        for nodes in ({'A': '127.0.0.1:5101', 'B': '127.0.0.1:5101'},
                      {'A': 'localhost:5101', 'B': '127.0.0.1:5101'}):
            with self.subTest(nodes=nodes), self.assertRaises(ApiError) as caught:
                Router(nodes)
            self.assertEqual(caught.exception.code, 'duplicate_address')
        result = subprocess.run([sys.executable, '-m', 'sharedkv.router', '--nodes',
            'A=localhost:5101,B=127.0.0.1:5101'], cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('distinct storage address', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_both_openapi_contracts_describe_body_timeouts(self):
        for name in ('openapi.json', 'storage-openapi.json'):
            spec = json.loads((ROOT/'docs'/name).read_text(encoding='utf-8'))
            for path, methods in spec['paths'].items():
                for operation in methods.values():
                    if isinstance(operation, dict) and 'responses' in operation:
                        with self.subTest(contract=name, path=path):
                            self.assertIn('408', operation['responses'])

    def test_standalone_startup_rejects_bad_ports_addresses_and_occupied_port(self):
        commands = [('-m', 'sharedkv.storage', '--id', 'A', '--port', str(p)) for p in (-1, 0, 65536)]
        commands += [('-m', 'sharedkv.router', '--port', str(p)) for p in (-1, 0, 65536)]
        commands += [('-m', 'sharedkv.router', '--nodes', n) for n in ('A=example.com:5001', 'A=[', 'A=localhost:0', 'A=localhost:5001,A=localhost:5002')]
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            port = str(occupied.getsockname()[1])
            commands += [('-m', 'sharedkv.router', '--port', port),
                         ('-m', 'sharedkv.storage', '--id', 'A', '--port', port)]
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run([sys.executable, *command], cwd=ROOT, capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('Traceback', result.stdout+result.stderr)

    def test_invalid_nested_settings_and_unrepresentable_timeout(self):
        for settings in ({'startup_timeout': 10**400}, {'initial_nodes': None}, {'initial_nodes': [['A']]}):
            with self.subTest(settings=settings), self.assertRaises(ConfigError):
                ClusterConfig(**settings)
        for settings in ({'modes': [['consistent']]}, {'modes': 'consistent'}, {'vnodes': [[2]]}, {'vnodes': None}):
            with self.subTest(settings=settings), self.assertRaises(ConfigError):
                ExperimentConfig(**settings)

    def test_invalid_experiment_settings_are_rejected_before_http_mutations(self):
        for settings in ({'keys': 1.5}, {'seed': -1}, {'vnodes': True}, {'mode': 'other'}, {'new_node': 'long'}):
            with self.subTest(settings=settings), patch('sharedkv.experiment.request') as api:
                with self.assertRaises(ValueError):
                    run_case('http://127.0.0.1:8000', **({'mode': 'consistent'} | settings))
                api.assert_not_called()

    def test_strict_json_and_malformed_dependency_envelopes(self):
        for raw in ('{"x":NaN}', '{"x":1e999}', '{"x":Infinity}', '{"x":1,"x":2}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                decode_json(raw)
        for raw in (b'[]', b'{"x":NaN}', b'not-json'):
            with patch('sharedkv.transport.urlopen', return_value=BytesIO(raw)):
                with self.assertRaises(ApiError) as caught:
                    request('http://127.0.0.1:8000', '/stats')
                self.assertEqual(caught.exception.code, 'invalid_response')
        for raw in (b'[]', b'{"error":1,"message":null}', b'{"error":"bad","message":"bad","details":[]}'):
            error = HTTPError('http://127.0.0.1', 400, 'Bad request', {}, BytesIO(raw))
            with patch('sharedkv.transport.urlopen', side_effect=error), self.assertRaises(ApiError) as caught:
                request('http://127.0.0.1:8000', '/stats')
            self.assertEqual(caught.exception.code, 'invalid_response')

    def test_incomplete_repeated_length_and_slow_bodies_leave_server_usable(self):
        with patch.object(Handler, 'timeout', .2), running_server(Storage('A')) as port:
            conn = HTTPConnection('127.0.0.1', port, timeout=3)
            conn.putrequest('POST', '/migrate_in')
            conn.putheader('Content-Type', 'application/json')
            conn.putheader('Content-Length', '10')
            conn.putheader('Content-Length', '10')
            conn.endheaders()
            self.assertEqual(conn.getresponse().status, 400)
            conn.close()
            conn = HTTPConnection('127.0.0.1', port, timeout=3)
            conn.putrequest('POST', '/migrate_in')
            conn.putheader('Content-Type', 'application/json')
            conn.putheader('Content-Length', '10')
            conn.endheaders(b'{')
            response = conn.getresponse()
            self.assertEqual(response.status, 408)
            self.assertEqual(json.loads(response.read())['error'], 'request_timeout')
            conn.close()
            self.assertEqual(request(f'http://127.0.0.1:{port}', '/health')['status'], 'ok')

    def test_wrong_operations_and_strange_http_inputs_do_not_mutate_or_stop_cluster(self):
        with Cluster() as cluster:
            cases = [('/put', 'POST', {'key': '', 'value': 'v'}, 400),
                     ('/put', 'POST', {'key': 'a'*1025, 'value': 'v'}, 400),
                     ('/put', 'POST', {'key': 'x', 'value': []}, 400),
                     ('/put', 'GET', None, 405), ('/missing', 'POST', {}, 404),
                     ('/get?key=a&key=b', 'GET', None, 400),
                     ('/get?key=%FF', 'GET', None, 400),
                     ('/ring?check=1', 'GET', None, 400),
                     ('/admin/vnodes', 'POST', {'v': -1}, 400),
                     ('/admin/placement', 'POST', {'mode': []}, 400),
                     ('/admin/addnode', 'POST', {'id': 'A', 'addr': cluster.addresses['A']}, 409),
                     ('/admin/addnode', 'POST', {'id': 'D', 'addr': 'http://remote.invalid'}, 400),
                     ('/admin/addnode', 'POST', {'id': 'D', 'addr': cluster.addresses['A']}, 409),
                     ('/admin/recover', 'POST', {}, 409)]
            for route, method, data, status in cases:
                with self.subTest(route=route, data=data), self.assertRaises(ApiError) as caught:
                    cluster.api(route, method, data)
                self.assertEqual(caught.exception.status, status)
            for raw in (b'{"key":"x","key":"y","value":"v"}', b'{"key":"x","value":"\\ud800"}', b'['*1200+b']'*1200):
                req = Request(cluster.url+'/put', raw, {'Content-Type': 'application/json'}, method='POST')
                with self.assertRaises(HTTPError) as caught:
                    urlopen(req, timeout=5)
                self.assertEqual(caught.exception.code, 400)
                caught.exception.close()
            self.assertEqual(cluster.api('/keys')['keys'], [])
            cluster.api('/put', 'POST', {'key': 'valid', 'value': 'still works'})
            self.assertEqual(cluster.api('/get?key=valid')['value'], 'still works')
            cluster.api('/put', 'POST', {'key': 'unicode', 'value': 'λ/🍎'})
            output = subprocess.run([sys.executable, '-m', 'sharedkv', 'client', '--router', cluster.url, 'get', 'unicode'],
                cwd=ROOT, env={**os.environ, 'PYTHONIOENCODING': 'ascii'}, capture_output=True, text=True)
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertNotIn('Traceback', output.stdout+output.stderr)

    def test_invalid_application_response_is_a_json_error(self):
        class InvalidApp:
            def handle(self, *args):
                return {'value': float('nan')}
        with running_server(InvalidApp()) as port, self.assertRaises(ApiError) as caught:
            request(f'http://127.0.0.1:{port}', '/')
        self.assertEqual(caught.exception.status, 500)


class EvidenceBoundaryTests(unittest.TestCase):
    def test_malformed_manifest_is_rejected_without_cli_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'environment.json'
            for raw in ('[]', 'null', '{"schema_version":1,"status":"complete","config":{}}', '{"x":NaN}', '['*1200+']'*1200):
                path.write_text(raw, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_run(tmp)
                result = subprocess.run([sys.executable, '-m', 'sharedkv', 'check', '--input', tmp], cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stdout+result.stderr)

    def test_nested_evidence_and_wrong_hot_key_and_source_change_are_detected(self):
        config = StudyConfig(ClusterConfig(initial_nodes=('X',), joining_node='Y'),
            ExperimentConfig(keys=3, uniform_reads=4, additional_hot_reads=0, trials=1,
                             modes=('consistent',), vnodes=(2,)))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'run'
            run_study(config, out)
            manifest = json.loads((out/'environment.json').read_text())
            case = out/manifest['schedule'][0]['file']
            original = json.loads(case.read_text())
            for field, value, message in [('pids', ['X', 'Y', 'router'], 'Malformed'),
                                          ('owned_children_stopped', 'yes', 'stop')]:
                row = dict(original, **{field: value})
                write_json(case, row)
                manifest['completed'][0]['sha256'] = digest(case)
                write_json(out/'environment.json', manifest)
                with self.assertRaisesRegex(ValueError, message):
                    load_run(out)
            row = json.loads(json.dumps(original))
            row['request_balance']['hot_key'] = list(row['owners_after'])[1]
            write_json(case, row)
            manifest['completed'][0]['sha256'] = digest(case)
            write_json(out/'environment.json', manifest)
            with self.assertRaisesRegex(ValueError, 'Hot key'):
                load_run(out)
            drift = Path(tmp)/'source-changed'
            with patch('sharedkv.study.source_hashes', side_effect=[{'source': 'before'}, {'source': 'after'}]):
                with self.assertRaisesRegex(RuntimeError, 'Sources changed'):
                    run_study(config, drift)
            self.assertEqual(json.loads((drift/'environment.json').read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
