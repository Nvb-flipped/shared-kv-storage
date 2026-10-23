"""The replacement framework: integer placement, real processes and safe reads."""
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from sharedkv.cluster import Cluster, child_interpreter
from sharedkv.placement import Placement, hash_integer
from sharedkv.router import Router
from sharedkv.storage import Storage
from sharedkv.terminal import ring_view
from sharedkv.transport import ApiError, request
from experiment import run_case


class LauncherTests(unittest.TestCase):
    def test_windows_venv_uses_real_executable_and_preserves_environment(self):
        with patch('sys.platform', 'win32'), patch('sys.prefix', 'venv'), \
             patch('sys.base_prefix', 'base'), patch('sys.executable', 'venv-python'), \
             patch('sys._base_executable', 'real-python'):
            executable, environment = child_interpreter()
        self.assertEqual(executable, 'real-python')
        self.assertEqual(environment['__PYVENV_LAUNCHER__'], 'venv-python')

    def test_storage_port_override_and_progress(self):
        messages=[]
        with Cluster(progress=messages.append) as cluster:
            self.assertEqual(len(cluster.processes),5)
        self.assertEqual(len([message for message in messages if 'ready (PID' in message]),5)
        cluster=Cluster(isolated=False,storage_base_port=5101)
        self.assertEqual(cluster.node_ports,dict(zip('ABCD',range(5101,5105))))
        self.assertEqual(cluster.addresses['D'],'127.0.0.1:5104')
        cluster.stop()
        for port in (0,65533,7998):
            with self.assertRaises(ValueError):Cluster(isolated=False,storage_base_port=port)

    def test_readiness_timeout_cleans_up_owned_child(self):
        cluster=Cluster()
        child=Mock();child.pid=123;child.poll.return_value=None
        with patch('sharedkv.cluster.subprocess.Popen',return_value=child), \
             patch('sharedkv.cluster.time.monotonic',side_effect=[0,6]):
            with self.assertRaisesRegex(RuntimeError,'within 5 seconds'):
                cluster.start()
        child.terminate.assert_called_once()
        child.wait.assert_called_once_with(timeout=5)
        self.assertFalse(Path(cluster.temp.name).exists())


class PlacementTests(unittest.TestCase):
    def test_integer_modulo_and_clockwise_boundaries(self):
        self.assertIs(type(hash_integer('user:101')), int)
        for mode in ('modulo', 'consistent'):
            p = Placement('ABC', mode, 10)
            for key in ['user:101', 'λ/🍎', '0', '']:
                if mode == 'modulo':
                    self.assertEqual(p.owner(key), sorted('ABC')[hash_integer(key) % 3])
                else:
                    wanted = next((t for t in p.tokens if t[0] >= hash_integer(key)), p.tokens[0])
                    self.assertEqual(p.owner(key), wanted[1])
            self.assertEqual(p.owner('test'), Placement('CBA', mode, 10).owner('test'))
        tokens = Placement('ABC', 'consistent', 10).view()
        self.assertEqual(len(tokens['tokens']), 30)
        self.assertAlmostEqual(sum(v['fraction'] for v in tokens['node_shares'].values()), 1)

    def test_clients_do_not_import_placement_or_router(self):
        for file in ('client.py', 'experiment.py', 'sharedkv/cli.py', 'sharedkv/experiment.py', 'sharedkv/terminal.py'):
            tree = ast.parse(Path(file).read_text())
            modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
            self.assertFalse(any('placement' in (m or '') or 'router' in (m or '') or 'cluster' in (m or '') for m in modules), file)

    def test_exact_token_boundary_and_wrap(self):
        ring = Placement('ABC', 'consistent', 10)
        for i, token in enumerate(ring.tokens):
            with patch('sharedkv.placement.hash_integer', return_value=token[0]):
                self.assertEqual(ring.locate('boundary')['owner_token_index'], i)
        with patch('sharedkv.placement.hash_integer', return_value=2**256-1):
            result = ring.locate('wrap')
            self.assertEqual(result['owner_token_index'], 0)
            self.assertTrue(result['wrap_around'])

    def test_ring_caret_uses_server_index_and_wraps(self):
        for v in (1, 10, 128):
            p = Placement('ABCD', 'consistent', v)
            for key in ('user:101', 'key-00999'):
                data = dict(p.view(), **p.locate(key))
                output = ring_view(data, width=40)
                plain = __import__('re').sub(r'\x1b\[[0-9;]*m', '', output).splitlines()
                caret = next(i for i, line in enumerate(plain) if '^' in line)
                index = data['owner_token_index']
                self.assertEqual(plain[caret].index('^')-2, index % 36)
                self.assertEqual(plain[caret-1][plain[caret].index('^')], data['owner'])


class StorageTests(unittest.TestCase):
    def test_text_only_overwrite_empty_and_batch_validation(self):
        store = Storage('A')
        put = lambda data: store.handle('PUT', '/kv/user%3A101', {}, data)
        put({'value': 'Apple'}); put({'value': ''})
        self.assertEqual(store.kv, {'user:101': ''})
        self.assertEqual(store.handle('GET', '/kv/user%3A101', {}, {}), {'key': 'user:101', 'value': ''})
        with self.assertRaises(ApiError): put({'value': 12})
        with self.assertRaises(ApiError): put({'value': 'x', 'version': 1})
        with self.assertRaises(ApiError):
            store.handle('POST', '/migrate_in', {}, {'items': [{'key': 'k', 'value': 'v'}, {'key': 'x', 'value': 1}]})
        self.assertNotIn('k', store.kv)
        store.handle('DELETE', '/kv/user%3A101', {}, {})
        self.assertEqual(store.kv, {})


class ProcessTests(unittest.TestCase):
    def test_http_boundary_errors_have_one_envelope(self):
        with Cluster() as c:
            cases = [(b'[]', 'application/json', {}, 400),
                     (b'{"key":"a","value":NaN}', 'application/json', {}, 400),
                     (b'{"key":"a","value":"v"}', 'text/plain', {}, 415),
                     (b'', 'application/json', {'Content-Length': str(1024*1024+1)}, 413)]
            for raw, media, extra, status in cases:
                req = Request(c.url+'/put', raw, {'Content-Type': media, **extra}, method='POST')
                with self.assertRaises(HTTPError) as caught: urlopen(req, timeout=5)
                self.assertEqual(caught.exception.code, status)
                body = json.loads(caught.exception.read()); caught.exception.close()
                self.assertEqual(set(body), {'error', 'message', 'details'})
    def test_real_processes_both_policies_values_and_hot_key(self):
        for mode in ('modulo', 'consistent'):
            with self.subTest(mode=mode), Cluster(mode, 10) as c:
                self.assertEqual(len(set(p.pid for p in c.processes.values())), 5)
                result = run_case(c.url, mode, 10, keys=100, reads=100, hot_requests=50,
                                  new_address=c.addresses['D'])
                self.assertEqual(result['verification']['failures'], [])
                self.assertEqual(result['verification']['checked'], 100)
                if mode == 'modulo':
                    matrix = result['reassignment']['matrix_counts']
                    self.assertGreater(sum(n for a, row in matrix.items() for b, n in row.items() if a != b and b != 'D'), 0)
            self.assertTrue(all(p.poll() is not None for p in c.processes.values()))

    def test_runtime_switch_requires_explicit_flush_and_reload(self):
        with Cluster() as c:
            c.api('/put', 'POST', {'key': 'x', 'value': 'first'})
            result = c.api('/admin/placement', 'POST', {'mode': 'modulo'})
            self.assertTrue(result['reload_required'])
            with self.assertRaises(ApiError) as caught:
                c.api('/get?key=x')
            self.assertEqual(caught.exception.code, 'reload_required')
            self.assertEqual(c.api('/admin/flush', 'POST', {})['deleted'], 1)
            c.api('/put', 'POST', {'key': 'x', 'value': 'second'})
            self.assertEqual(c.api('/get?key=x')['value'], 'second')
            self.assertEqual(c.api('/admin/vnodes', 'POST', {'v': 128})['vnodes_per_node'], 128)
            with self.assertRaises(ApiError): c.api('/admin/vnodes', 'POST', {'v': True})

    def test_miss_probe_counters_and_cli_exit(self):
        with Cluster() as c:
            c.api('/put', 'POST', {'key': 'user:101', 'value': 'Apple'})
            c.api('/admin/reset_counters', 'POST', {})
            view = c.api('/ring?key=missing')
            self.assertNotIn('exists', view)
            checked = c.api('/ring?key=missing&check=1')
            self.assertFalse(checked['exists'])
            stats = c.api('/stats')
            self.assertEqual(sum(n['request_count'] for n in stats['nodes']), 0)
            self.assertEqual(stats['inspection_reads'], 1)
            got = subprocess.run([sys.executable, 'client.py', '--router', c.url, 'get', 'missing'], text=True, capture_output=True)
            self.assertEqual(got.returncode, 3)
            self.assertIn('NOT FOUND', got.stderr)
            self.assertNotIn('Traceback', got.stderr)
            self.assertEqual(sum(n['request_count'] for n in c.api('/stats')['nodes']), 1)

    def test_down_node_keeps_its_owner_without_eviction(self):
        with Cluster() as c:
            owner = c.api('/put', 'POST', {'key': 'x', 'value': 'v'})['owner']
            c.processes[owner].terminate(); c.processes[owner].wait()
            with self.assertRaises(ApiError) as caught: c.api('/get?key=x')
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(c.api('/owner?key=x')['owner'], owner)
            self.assertEqual(next(n for n in c.api('/admin/membership')['nodes'] if n['id'] == owner)['status'], 'down')


class MigrationTests(unittest.TestCase):
    def prepare(self, cluster, hook=None):
        app = Router({n: cluster.addresses[n] for n in 'ABC'}, 'modulo', phase_hook=hook)
        for i in range(40): app.put({'key': f'k{i}', 'value': f'λ-{i}'})
        return app

    def test_get_allowed_while_put_and_reconfiguration_are_paused(self):
        entered, release = threading.Event(), threading.Event()
        def hook(phase):
            if phase == 'verifying': entered.set(); self.assertTrue(release.wait(10))
        with Cluster() as c:
            app = self.prepare(c, hook)
            with ThreadPoolExecutor() as pool:
                join = pool.submit(app.addnode, {'id': 'D', 'addr': c.addresses['D']})
                self.assertTrue(entered.wait(10))
                try:
                    self.assertEqual(app.route_get('k1')['value'], 'λ-1')
                    self.assertTrue(app.stats()['paused_writes'])
                    for action, status in [(lambda: app.put({'key': 'new', 'value': 'blocked'}), 503),
                            (lambda: app.reconfigure(vnodes=128), 409),
                            (lambda: app.addnode({'id': 'E', 'addr': 'localhost:5005'}), 409)]:
                        with self.assertRaises(ApiError) as caught: action()
                        self.assertEqual(caught.exception.status, status)
                finally:
                    release.set()
                result = join.result(15)
            self.assertEqual(result['migrated'], result['verified'])
            self.assertFalse(app.paused)
            for i in range(40): self.assertEqual(app.route_get(f'k{i}')['value'], f'λ-{i}')

    def test_lost_ack_rolls_back_staging_before_recovery(self):
        with Cluster() as c:
            app = self.prepare(c); original = app.call_node; failed = False
            def fault(node, route, method='GET', data=None):
                nonlocal failed
                result = original(node, route, method, data)
                if method == 'PUT' and not failed:
                    failed = True
                    raise ApiError(503, 'lost_ack', 'Injected lost acknowledgment.')
                return result
            app.call_node = fault
            with self.assertRaises(ApiError): app.addnode({'id': 'D', 'addr': c.addresses['D']})
            self.assertEqual(app.migration['state'], 'failed'); self.assertEqual(app.membership_version, 1)
            self.assertTrue(app.paused)
            app.call_node = original
            app.recover()
            self.assertNotIn('D', app.nodes)
            self.assertEqual(request('http://'+c.addresses['D'], '/keys')['keys'], [])
            for i in range(40): self.assertEqual(app.route_get(f'k{i}')['value'], f'λ-{i}')

    def test_publication_waits_for_inflight_old_owner_get(self):
        verifying, continue_join = threading.Event(), threading.Event()
        reading, release_read, destinations_read = threading.Event(), threading.Event(), threading.Event()
        def phase(name):
            if name == 'verifying': verifying.set(); self.assertTrue(continue_join.wait(10))
        with Cluster() as c:
            app = self.prepare(c, phase)
            with ThreadPoolExecutor() as pool:
                joined = pool.submit(app.addnode, {'id': 'D', 'addr': c.addresses['D']})
                self.assertTrue(verifying.wait(10))
                chosen = app.staged[0][1]; old_owner = app.map.owner(chosen)
                original = app.call_node; checked = 0
                def read_barrier(node, route, method='GET', data=None):
                    nonlocal checked
                    if method == 'GET' and node == old_owner and route == '/kv/'+chosen:
                        reading.set(); self.assertTrue(release_read.wait(10))
                    result = original(node, route, method, data)
                    if method == 'GET' and any(node == dest and route == '/kv/'+key for dest, key in app.staged):
                        checked += 1
                        if checked == len(app.staged): destinations_read.set()
                    return result
                app.call_node = read_barrier
                old_get = pool.submit(app.route_get, chosen)
                try:
                    self.assertTrue(reading.wait(10)); continue_join.set()
                    self.assertTrue(destinations_read.wait(10))
                    self.assertEqual(app.membership_version, 1)
                    self.assertFalse(joined.done())
                finally:
                    release_read.set(); continue_join.set()
                self.assertEqual(old_get.result(10)['value'], 'λ-'+chosen[1:])
                self.assertEqual(joined.result(10)['new_membership_version'], 2)

    def test_published_cleanup_failure_recovers_forward(self):
        with Cluster() as c:
            app = self.prepare(c); original = app.call_node; failed = False
            def fault(node, route, method='GET', data=None):
                nonlocal failed
                if method == 'DELETE' and not failed:
                    failed = True; raise ApiError(503, 'delete_failed', 'Injected deletion failure.')
                return original(node, route, method, data)
            app.call_node = fault
            with self.assertRaises(ApiError): app.addnode({'id': 'D', 'addr': c.addresses['D']})
            self.assertTrue(app.published); self.assertEqual(app.membership_version, 2)
            self.assertEqual(app.route_get('k1')['value'], 'λ-1')
            app.call_node = original; app.recover()
            self.assertFalse(app.paused); self.assertEqual(app.membership_version, 2)
            self.assertTrue(all(row['stored_on'] == [row['owner']] for row in app.inventory()['keys']))


if __name__ == '__main__':
    unittest.main()
