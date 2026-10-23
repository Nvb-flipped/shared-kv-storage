"""Central membership, placement, request accounting and verified migration."""
from collections import Counter
import copy
import hashlib
import json
import os
import threading
import time
from urllib.parse import quote, urlsplit
from .placement import Placement
from .transport import ApiError, fields, request, require, text_key


def address(value):
    if not isinstance(value, str):
        raise ApiError(400, 'invalid_address', 'Use localhost:PORT or 127.0.0.1:PORT.')
    parsed = urlsplit('//'+value)
    try:
        valid = parsed.hostname in ('localhost', '127.0.0.1') and parsed.port and 1 <= parsed.port <= 65535
    except ValueError:
        valid = False
    if not valid or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ApiError(400, 'invalid_address', 'Use localhost:PORT or 127.0.0.1:PORT.')
    return f'127.0.0.1:{parsed.port}'


def key_route(key):
    return '/kv/'+quote(key, safe='')


def query_key(query):
    if len(query.get('key', [])) != 1:
        raise ApiError(400, 'invalid_key', 'Provide exactly one key query parameter.')
    return text_key(query['key'][0])


class Router:
    def __init__(self, nodes, mode='consistent', vnodes=16, phase_hook=None):
        self.nodes = {node: {'id': node, 'addr': address(addr), 'status': 'active'} for node, addr in nodes.items()}
        self.map = Placement(nodes, mode, vnodes)
        self.membership_version = self.placement_revision = 1
        self.control, self.read_gate = threading.RLock(), threading.RLock()
        self.mutation = threading.Lock()
        self.counts, self.key_counts = Counter(), Counter()
        self.inspection_reads = 0
        self.reload_required = False
        self.paused = False
        self.migration = {'state': 'idle', 'old_membership_version': None, 'new_membership_version': None}
        self.pending = None
        self.staged, self.cleanup = [], []
        self.published, self.candidate = False, None
        self.last_migration = None
        self.phase_hook = phase_hook

    def call_node(self, node, route, method='GET', data=None):
        try:
            return request('http://'+self.nodes[node]['addr'], route, method, data, timeout=5)
        except ApiError as exc:
            if exc.status >= 500:
                with self.control:
                    self.nodes[node]['status'] = 'down'
                raise ApiError(503, 'node_unavailable', f'Storage {node} is unavailable.', {'owner': node}) from exc
            raise

    def phase(self, name):
        with self.control:
            self.migration['state'] = name
        if self.phase_hook:
            self.phase_hook(name)

    def membership(self):
        with self.control:
            return {'version': self.membership_version, 'placement_revision': self.placement_revision,
                    'nodes': copy.deepcopy(list(self.nodes.values())), 'paused_writes': self.paused,
                    'reload_required': self.reload_required, 'migration': copy.deepcopy(self.migration),
                    'last_migration': copy.deepcopy(self.last_migration), 'pid': os.getpid()}

    def check_data_ready(self):
        if self.reload_required:
            raise ApiError(409, 'reload_required', 'Placement changed. Flush and reload before Put/Get.')

    def route_get(self, key, count=True):
        # Hold this gate through the read so publication waits for old-owner reads.
        with self.read_gate:
            with self.control:
                self.check_data_ready()
                node = self.map.owner(key)
                if count:
                    self.counts[node] += 1; self.key_counts[key] += 1
                else:
                    self.inspection_reads += 1
            try:
                value = self.call_node(node, key_route(key))['value']
            except ApiError as exc:
                if exc.status == 404:
                    raise ApiError(404, 'not_found', 'The key does not exist.', {'key': key, 'owner': node}) from exc
                raise
            return {'key': key, 'value': value, 'owner': node}

    def put(self, data):
        fields(data, ['key', 'value']); key = text_key(data['key'])
        if not isinstance(data['value'], str):
            raise ApiError(400, 'invalid_value', 'Values must be text.')
        if not self.mutation.acquire(blocking=False):
            raise ApiError(503, 'migration_in_progress' if self.paused else 'busy',
                           'Writes are paused or another mutation is running.', {'retry_after_ms': 500})
        try:
            with self.control:
                if self.paused:
                    raise ApiError(503, 'migration_in_progress', 'Writes stay paused until recovery.', {'retry_after_ms': 500})
                self.check_data_ready()
                owner = self.map.owner(key)
                self.counts[owner] += 1; self.key_counts[key] += 1
            self.call_node(owner, key_route(key), 'PUT', {'value': data['value']})
            return {'ok': True, 'owner': owner}
        finally:
            self.mutation.release()

    def stats(self):
        with self.control:
            info = self.membership()
            mode, vnodes = self.map.mode, self.map.vnodes
            counts = self.counts.copy()
            top = [{'key': key, 'owner': self.map.owner(key), 'requests': count}
                   for key, count in self.key_counts.most_common(10)]
        rows = []
        for node in info['nodes']:
            try:
                count = self.call_node(node['id'], '/stats')['key_count']
            except ApiError:
                count = None; node['status'] = 'down'
            rows.append(dict(node, key_count=count, request_count=counts[node['id']]))
        return {'placement_mode': mode, 'vnodes_per_node': vnodes,
                'membership_version': info['version'], 'placement_revision': info['placement_revision'],
                'paused_writes': info['paused_writes'], 'reload_required': info['reload_required'],
                'migration_state': info['migration']['state'], 'nodes': rows,
                'key_counts_total': sum(row['key_count'] or 0 for row in rows),
                'top_keys_by_requests': top, 'inspection_reads': self.inspection_reads,
                'counts_complete': all(row['key_count'] is not None for row in rows)}

    def ring(self, query):
        with self.read_gate:
            with self.control:
                result = dict(self.map.view(), membership_version=self.membership_version,
                              placement_revision=self.placement_revision, migration_state=self.migration['state'],
                              paused_writes=self.paused, reload_required=self.reload_required)
                key = query_key(query) if 'key' in query else None
                if key is not None:
                    result.update(self.map.locate(key))
                    if self.pending and self.pending.owner(key) != result['owner']:
                        result['pending_owner'] = self.pending.owner(key)
            if query.get('check', ['0']) not in (['0'], ['1']):
                raise ApiError(400, 'invalid_check', 'check must be 0 or 1.')
            if query.get('check') == ['1']:
                if key is None:
                    raise ApiError(400, 'invalid_key', 'An existence check requires a key.')
                try:
                    self.route_get(key, count=False)
                    result['exists'] = True
                except ApiError as exc:
                    if exc.status != 404:
                        raise
                    result['exists'] = False
            return result

    def inventory(self):
        with self.read_gate:
            with self.control:
                nodes = list(self.nodes)
                version = self.membership_version
            keys = {}
            for node in nodes:
                for key in self.call_node(node, '/keys')['keys']:
                    keys.setdefault(key, []).append(node)
            with self.control:
                return {'membership_version': version, 'reload_required': self.reload_required,
                        'keys': [{'key': key, 'owner': self.map.owner(key), 'stored_on': hosts}
                                 for key, hosts in sorted(keys.items())]}

    def reconfigure(self, mode=None, vnodes=None):
        if not self.mutation.acquire(blocking=False):
            raise ApiError(409, 'migration_in_progress', 'Cannot reconfigure during another mutation.')
        try:
            with self.read_gate:
                if self.paused:
                    raise ApiError(409, 'migration_in_progress', 'Recover the failed migration first.')
                try:
                    new = Placement(self.map.members, self.map.mode if mode is None else mode,
                                    self.map.vnodes if vnodes is None else vnodes)
                except ValueError as exc:
                    raise ApiError(400, 'invalid_placement', str(exc)) from exc
                changed = (new.mode, new.vnodes) != (self.map.mode, self.map.vnodes)
                populated = any(self.call_node(n, '/stats')['key_count'] for n in self.nodes)
                with self.control:
                    self.map = new
                    if changed:
                        self.placement_revision += 1
                        self.reload_required |= populated
                return {'ok': True, 'mode': new.mode, 'vnodes_per_node': new.vnodes,
                        'reload_required': self.reload_required, 'placement_revision': self.placement_revision}
        finally:
            self.mutation.release()

    def addnode(self, data):
        fields(data, ['id', 'addr']); node = data['id']
        if not isinstance(node, str) or len(node) != 1 or not 'A' <= node <= 'Z':
            raise ApiError(400, 'invalid_id', 'Node IDs are uppercase letters A–Z.')
        addr = address(data['addr'])
        if not self.mutation.acquire(blocking=False):
            raise ApiError(409, 'migration_in_progress', 'Another membership change or mutation is running.')
        started = time.perf_counter()
        try:
            with self.control:
                if self.paused:
                    raise ApiError(409, 'migration_in_progress', 'Recover the failed migration first.')
                self.check_data_ready()
                if node in self.nodes or any(row['addr'] == addr for row in self.nodes.values()):
                    raise ApiError(409, 'duplicate_node', 'The ID or address is already registered.')
            health = request('http://'+addr, '/health', timeout=5)
            if health.get('id') != node:
                raise ApiError(400, 'node_id_mismatch', 'The storage ID does not match registration.')
            if request('http://'+addr, '/keys')['keys']:
                raise ApiError(409, 'destination_not_empty', 'The joining storage process must be empty.')
            old = self.map
            new = Placement(old.members+[node], old.mode, old.vnodes)
            with self.control:
                self.nodes[node] = {'id': node, 'addr': addr, 'status': 'joining'}
                self.paused, self.pending, self.candidate = True, new, node
                self.staged, self.cleanup, self.published = [], [], False
                old_version = self.membership_version
                self.migration = {'state': 'preparing', 'old_membership_version': old_version,
                                  'new_membership_version': old_version+1}
            try:
                self.phase('preparing')
                transfers, seen = [], set()
                for source in old.members:
                    for key in self.call_node(source, '/keys')['keys']:
                        if key in seen or old.owner(key) != source:
                            raise ApiError(409, 'invalid_inventory', 'Storage inventory does not match the old placement.')
                        seen.add(key)
                        destination = new.owner(key)
                        if source != destination:
                            transfers.append((key, source, destination))
                self.phase('migrating')
                expected, migrated, estimated = {}, 0, 0
                for key, source, destination in transfers:
                    value = self.call_node(source, key_route(key))['value']
                    self.staged.append((destination, key))
                    self.call_node(destination, key_route(key), 'PUT', {'value': value})
                    expected[key] = hashlib.sha256(value.encode('utf-8')).hexdigest()
                    migrated += 1
                    estimated += len(json.dumps({'key': key, 'value': value}, ensure_ascii=False).encode('utf-8'))
                self.phase('verifying')
                failures = []
                for key, source, destination in transfers:
                    value = self.call_node(destination, key_route(key))['value']
                    if hashlib.sha256(value.encode('utf-8')).hexdigest() != expected[key]:
                        failures.append(key)
                if failures:
                    raise ApiError(503, 'verification_failed', 'Destination values do not match.', {'keys': failures})
                # Wait for in-flight old-owner Gets; subsequent Gets use the verified map.
                with self.read_gate:
                    with self.control:
                        self.map = new
                        self.membership_version += 1
                        self.nodes[node]['status'] = 'active'
                        self.published = True
                        self.cleanup = [(source, key) for key, source, _ in transfers]
                        self.staged = []
                        self.pending = None
                self.phase('done')
                self.clean_sources()
                summary = {'ok': True, 'old_membership_version': old_version,
                    'new_membership_version': self.membership_version, 'placement_mode': new.mode,
                    'paused_writes': False, 'writes_paused_during_migration': True,
                    'reassigned_key_count': len(transfers), 'reassigned_keys': [key for key, _, _ in transfers],
                    'migrated': migrated, 'verified': len(transfers), 'verification_failures': [],
                    'estimated_item_bytes': estimated, 'seconds': time.perf_counter()-started,
                    'key_counts_after': {n: self.call_node(n, '/stats')['key_count'] for n in new.members}}
                with self.control:
                    self.last_migration = summary; self.paused = False
                    self.migration['state'] = 'idle'
                return summary
            except Exception:
                self.phase('failed')
                raise
        finally:
            self.mutation.release()

    def clean_sources(self):
        while self.cleanup:
            node, key = self.cleanup[0]
            self.call_node(node, key_route(key), 'DELETE')
            self.cleanup.pop(0)

    def recover(self):
        if not self.mutation.acquire(blocking=False):
            raise ApiError(409, 'migration_in_progress', 'Wait for the migration response.')
        try:
            if self.migration['state'] != 'failed':
                raise ApiError(409, 'no_failed_migration', 'There is no failed migration to recover.')
            if self.published:
                self.clean_sources()
            else:
                while self.staged:
                    node, key = self.staged[0]
                    self.call_node(node, key_route(key), 'DELETE')
                    self.staged.pop(0)
            for node in self.map.members:
                if self.call_node(node, '/health')['id'] != node:
                    raise ApiError(503, 'node_id_mismatch', 'Restore the original storage processes.')
            with self.control:
                if not self.published and self.candidate:
                    self.nodes.pop(self.candidate, None)
                for node in self.map.members:
                    self.nodes[node]['status'] = 'active'
                self.pending = None; self.paused = False; self.migration['state'] = 'idle'
            return {'ok': True, 'membership_version': self.membership_version}
        finally:
            self.mutation.release()

    def handle(self, method, path, query, data):
        if path == '/put':
            require(method, 'POST'); return self.put(data)
        if path in ('/get', '/owner'):
            require(method, 'GET'); key = query_key(query)
            if path == '/get':
                return self.route_get(key)
            with self.control:
                return dict(self.map.locate(key), membership_version=self.membership_version,
                            placement_revision=self.placement_revision)
        if path == '/ring':
            require(method, 'GET'); return self.ring(query)
        if path == '/stats':
            require(method, 'GET'); return self.stats()
        if path == '/keys':
            require(method, 'GET'); return self.inventory()
        if path == '/admin/membership':
            require(method, 'GET'); return self.membership()
        if path == '/admin/health':
            require(method, 'GET'); return {'ok': True, 'pid': os.getpid()}
        if path == '/admin/addnode':
            require(method, 'POST'); return self.addnode(data)
        if path == '/admin/recover':
            require(method, 'POST'); return self.recover()
        if path == '/admin/placement':
            require(method, 'POST'); fields(data, ['mode'])
            if not isinstance(data['mode'], str):
                raise ApiError(400, 'invalid_placement', 'mode must be modulo or consistent.')
            return self.reconfigure(mode=data['mode'])
        if path == '/admin/vnodes':
            require(method, 'POST'); fields(data, ['v'])
            if type(data['v']) is not int:
                raise ApiError(400, 'invalid_placement', 'v must be an integer from 1 to 1024.')
            return self.reconfigure(vnodes=data['v'])
        if path == '/admin/reset_counters':
            require(method, 'POST')
            with self.control:
                self.counts.clear(); self.key_counts.clear(); self.inspection_reads = 0
            return {'ok': True}
        if path == '/admin/flush':
            require(method, 'POST')
            if not self.mutation.acquire(blocking=False):
                raise ApiError(409, 'migration_in_progress', 'Cannot flush during a mutation.')
            try:
                with self.read_gate:
                    if self.paused:
                        raise ApiError(409, 'migration_in_progress', 'Recover before flushing.')
                    self.reload_required = True
                    deleted = sum(self.call_node(n, '/keys', 'DELETE')['deleted'] for n in self.nodes)
                    self.reload_required = False
                return {'ok': True, 'deleted': deleted}
            finally:
                self.mutation.release()
        raise ApiError(404, 'unknown_endpoint', 'Unknown router endpoint.')
