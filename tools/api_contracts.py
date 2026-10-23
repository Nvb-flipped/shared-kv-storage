"""The router/storage API contracts; no documentation server or web UI."""
import json
from pathlib import Path

S = {'type': 'string'}
I = {'type': 'integer', 'minimum': 0}
P = {'type': 'integer', 'minimum': 1}
B = {'type': 'boolean'}
NODE = {'type': 'string', 'pattern': '^[A-Z]$'}


def obj(props, required=None, extra=False):
    return {'type': 'object', 'properties': props, 'required': list(props) if required is None else required, 'additionalProperties': extra}


def ref(name): return {'$ref': '#/components/schemas/'+name}
def arr(item): return {'type': 'array', 'items': item}
def mapping(item): return {'type': 'object', 'additionalProperties': item}
def nullable(schema): return {'anyOf': [schema, {'type': 'null'}]}


SCHEMAS = {
    'Error': obj({'error': S, 'message': S, 'details': {'type': 'object', 'additionalProperties': True}}),
    'Ok': obj({'ok': {'const': True}}),
    'Put': obj({'key': dict(S, minLength=1), 'value': S}),
    'Value': obj({'value': S}),
    'KeyValue': obj({'key': S, 'value': S}),
    'Get': obj({'key': S, 'value': S, 'owner': NODE}),
    'PutResult': obj({'ok': {'const': True}, 'owner': NODE}),
    'StorageStats': obj({'id': NODE, 'status': {'const': 'ok'}, 'key_count': I, 'pid': P}),
    'KeyList': obj({'keys': arr(S)}),
    'Flush': obj({'ok': {'const': True}, 'deleted': I}),
    'Batch': obj({'items': arr(ref('KeyValue'))}),
    'BatchResult': obj({'ok': {'const': True}, 'count': I}),
    'Token': obj({'pos': dict(I, description='Unsigned integer SHA-256 position, up to 256 bits; preserve integer precision.'), 'node': NODE, 'label': S}),
    'Owner': obj({'key': S, 'key_hash': I, 'owner': NODE, 'owner_index': I, 'nodes_sorted': arr(NODE),
        'owner_token': ref('Token'), 'owner_token_index': I, 'wrap_around': B,
        'membership_version': P, 'placement_revision': P}, ['key', 'key_hash', 'owner', 'membership_version', 'placement_revision']),
    'Ring': obj({'placement_mode': {'enum': ['modulo', 'consistent']}, 'vnodes_per_node': P, 'hash_space': P,
        'membership_version': P, 'placement_revision': P, 'migration_state': S, 'paused_writes': B, 'reload_required': B,
        'nodes_sorted': arr(NODE), 'tokens': arr(ref('Token')), 'total_tokens': I,
        'node_shares': mapping(obj({'tokens': I, 'fraction': {'type': 'number', 'minimum': 0, 'maximum': 1}, 'hash_units': I})),
        'key': S, 'key_hash': I, 'owner': NODE, 'owner_index': I, 'owner_token': ref('Token'), 'owner_token_index': I,
        'wrap_around': B, 'exists': B, 'pending_owner': NODE},
        ['placement_mode', 'vnodes_per_node', 'hash_space', 'membership_version', 'placement_revision', 'migration_state', 'paused_writes', 'reload_required']),
    'Node': obj({'id': NODE, 'addr': S, 'status': {'enum': ['active', 'joining', 'down']}}),
    'Migration': obj({'state': {'enum': ['idle', 'preparing', 'migrating', 'verifying', 'done', 'failed']},
        'old_membership_version': nullable(P), 'new_membership_version': nullable(P)}),
    'MigrationSummary': obj({'ok': {'const': True}, 'old_membership_version': P, 'new_membership_version': P,
        'placement_mode': {'enum': ['modulo', 'consistent']}, 'paused_writes': {'const': False}, 'writes_paused_during_migration': {'const': True},
        'reassigned_key_count': I, 'reassigned_keys': arr(S), 'migrated': I, 'verified': I,
        'verification_failures': arr(S), 'estimated_item_bytes': I, 'seconds': {'type': 'number', 'minimum': 0}, 'key_counts_after': mapping(I)}),
    'Membership': obj({'version': P, 'placement_revision': P, 'nodes': arr(ref('Node')), 'paused_writes': B,
        'reload_required': B, 'migration': ref('Migration'), 'last_migration': nullable(ref('MigrationSummary')), 'pid': P}),
    'NodeStats': obj({'id': NODE, 'addr': S, 'status': {'enum': ['active', 'joining', 'down']}, 'key_count': nullable(I), 'request_count': I}),
    'Stats': obj({'placement_mode': {'enum': ['modulo', 'consistent']}, 'vnodes_per_node': P, 'membership_version': P,
        'placement_revision': P, 'paused_writes': B, 'reload_required': B, 'migration_state': S, 'nodes': arr(ref('NodeStats')),
        'key_counts_total': I, 'top_keys_by_requests': arr(obj({'key': S, 'owner': NODE, 'requests': I})),
        'inspection_reads': I, 'counts_complete': B}),
    'Inventory': obj({'membership_version': P, 'reload_required': B, 'keys': arr(obj({'key': S, 'owner': NODE, 'stored_on': arr(NODE)}))}),
    'AddNode': obj({'id': NODE, 'addr': S}),
    'Mode': obj({'mode': {'enum': ['modulo', 'consistent']}}),
    'Vnodes': obj({'v': {'type': 'integer', 'minimum': 1, 'maximum': 1024}}),
    'Reconfigured': obj({'ok': {'const': True}, 'mode': {'enum': ['modulo', 'consistent']}, 'vnodes_per_node': P, 'reload_required': B, 'placement_revision': P}),
    'Recovered': obj({'ok': {'const': True}, 'membership_version': P}),
    'Health': obj({'ok': {'const': True}, 'pid': P})
}
ROUTER = [
    ('post', '/put', 'Put', 'PutResult', 'Store or overwrite text; single-owner acknowledgment.'),
    ('get', '/get', None, 'Get', 'Read current text. Missing keys return 404 with the routed owner.'),
    ('get', '/owner', None, 'Owner', 'Placement only; the key need not exist.'),
    ('get', '/ring', None, 'Ring', 'Sorted integer tokens or modulo inputs. check=1 probes existence separately from client request counts.'),
    ('get', '/stats', None, 'Stats', 'Physical key counts and router-counted Put/Get forwarding attempts, including misses. Counts may include staged copies during migration.'),
    ('get', '/keys', None, 'Inventory', 'Course-scale inventory of every stored key, routed owner and physical hosts. No pagination.'),
    ('get', '/admin/membership', None, 'Membership', 'Membership, migration phase and placement revision; no storage reads.'),
    ('get', '/admin/health', None, 'Health', 'Router process health and PID.'),
    ('post', '/admin/addnode', 'AddNode', 'MigrationSummary', 'Register an empty reachable storage process, pause writes, copy and verify, publish, delete old copies, resume. Gets remain available.'),
    ('post', '/admin/placement', 'Mode', 'Reconfigured', 'Rebuild only; populated stores require explicit flush/reload. Reject during migration.'),
    ('post', '/admin/vnodes', 'Vnodes', 'Reconfigured', 'Set integer V from 1 to 1024; same reconfiguration semantics.'),
    ('post', '/admin/reset_counters', None, 'Ok', 'Reset router client and inspection counters. Establish an experiment boundary without concurrent traffic.'),
    ('post', '/admin/flush', None, 'Flush', 'Explicitly delete all registered stores’ data. Partial failure keeps reload_required=true; retry only after inspection.'),
    ('post', '/admin/recover', None, 'Recovered', 'Failed migration only. Roll back unpublished staging or finish published cleanup; unpause only when cleanup and member health checks succeed.')
]
STORAGE = [
    ('get', '/health', None, 'StorageStats', 'Storage identity, key count, PID.'),
    ('get', '/stats', None, 'StorageStats', 'Local key count; no placement or peer knowledge.'),
    ('get', '/keys', None, 'KeyList', 'All local keys, sorted.'),
    ('delete', '/keys', None, 'Flush', 'Delete all local values; for coordinated experiments.'),
    ('put', '/kv/{key}', 'Value', 'Ok', 'Store text only. No record version.'),
    ('get', '/kv/{key}', None, 'KeyValue', 'Read local text; 404 if absent.'),
    ('delete', '/kv/{key}', None, 'Ok', 'Delete if present, otherwise succeed; router migration cleanup only.'),
    ('post', '/migrate_in', 'Batch', 'BatchResult', 'Validate the full batch before writing it. Distinct keys and text values required.')
]


def document(rows, title, port):
    paths = {}
    for method, route, body, result, description in rows:
        operation = {'operationId': method+'_'+route.strip('/').replace('/', '_').replace('{key}', 'key'),
            'summary': description.split('.')[0], 'description': description,
            'responses': {'200': {'description': 'Success', 'content': {'application/json': {'schema': ref(result)}}}}}
        for status in (400, 404, 405, 409, 413, 415, 500, 502, 503):
            operation['responses'][str(status)] = {'description': {
                400: 'Invalid input', 404: 'Missing key or endpoint', 405: 'Wrong method', 409: 'State conflict or reload required',
                413: 'Body exceeds 1 MiB', 415: 'Use application/json', 500: 'Internal error', 502: 'Invalid dependency response',
                503: 'Migration, busy writer or unavailable storage'}[status], 'content': {'application/json': {'schema': ref('Error')}}}
        parameters = []
        if '{key}' in route:
            parameters.append({'name': 'key', 'in': 'path', 'required': True, 'schema': dict(S, minLength=1),
                               'description': 'Percent-encoded key; 1–1024 UTF-8 bytes after decoding.'})
        if route in ('/get', '/owner', '/ring'):
            parameters.append({'name': 'key', 'in': 'query', 'required': route != '/ring', 'schema': dict(S, minLength=1)})
        if route == '/ring':
            parameters.append({'name': 'check', 'in': 'query', 'required': False, 'schema': {'type': 'integer', 'enum': [0, 1], 'default': 0}})
        if parameters: operation['parameters'] = parameters
        if body:
            operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': ref(body)}}}
        paths.setdefault(route, {})[method] = operation
    return {'openapi': '3.1.0', 'info': {'title': title, 'version': '2.0.0', 'contact': {'name': 'Paco'},
        'description': 'Local, volatile course framework. UTF-8 JSON object bodies, 1 MiB maximum; text keys 1–1024 bytes. No authentication, CORS or external listener. See docs/api.md for concurrency and retry semantics.'},
        'servers': [{'url': f'http://127.0.0.1:{port}'}], 'paths': paths, 'components': {'schemas': SCHEMAS}}


def main():
    for name, rows, title, port in [('openapi.json', ROUTER, 'Shared KV router', 8000),
                                    ('storage-openapi.json', STORAGE, 'Shared KV internal storage', 5001)]:
        Path('docs', name).write_text(json.dumps(document(rows, title, port), indent=2)+'\n')
    print('Generated 14 router and 8 storage operations; no browser UI.')


if __name__ == '__main__':
    main()
