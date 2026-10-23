"""Pure HTTP experiment client. Owners come exclusively from router responses."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time
from urllib.parse import urlencode
from sharedkv.metrics import balance, movement
from sharedkv.transport import request


def dataset(count):
    return {f'key-{i:05d}': f'value-{i:05d}-λ-{i*i}' for i in range(count)}


def run_case(base, mode, vnodes=16, keys=1000, reads=1000, hot_requests=500,
             seed=3010, new_node='D', new_address='localhost:5004'):
    api = lambda route, method='GET', body=None: request(base, route, method, body, timeout=120)
    records = dataset(keys)
    if keys < 1 or reads < 1 or hot_requests < 1:
        raise ValueError('Keys, uniform reads and hot requests must be positive.')
    initial = api('/admin/membership')
    if new_node in [n['id'] for n in initial['nodes']]:
        raise ValueError('Use a fresh three-member cluster; the joining ID is already registered.')
    api('/admin/placement', 'POST', {'mode': mode})
    api('/admin/vnodes', 'POST', {'v': vnodes})
    api('/admin/flush', 'POST', {})
    api('/admin/reset_counters', 'POST', {})
    for key, value in records.items():
        api('/put', 'POST', {'key': key, 'value': value})
    before = api('/stats')
    ring_before = api('/ring')
    owners_before = {key: api('/owner?'+urlencode({'key': key}))['owner'] for key in records}
    joined = api('/admin/addnode', 'POST', {'id': new_node, 'addr': new_address})
    after = api('/stats')
    ring_after = api('/ring')
    owners_after = {key: api('/owner?'+urlencode({'key': key}))['owner'] for key in records}
    failures = []
    for key, expected in records.items():
        actual = api('/get?'+urlencode({'key': key}))
        if actual['value'] != expected or actual['owner'] != owners_after[key]:
            failures.append(key)
    inventory = api('/keys')
    physical_failures = [r['key'] for r in inventory['keys'] if r['stored_on'] != [r['owner']]]
    observed = movement(owners_before, owners_after)
    assert len(inventory['keys']) == keys and not physical_failures and not failures
    assert joined['migrated'] == joined['verified'] == joined['reassigned_key_count'] == observed['reassigned_key_count']
    expected_size = sum(len(json.dumps({'key': key, 'value': records[key]}, ensure_ascii=False).encode())
                        for key in joined['reassigned_keys'])
    assert expected_size == joined['estimated_item_bytes']
    # Measurements below exclude loading, migration, verification and inspection.
    api('/admin/reset_counters', 'POST', {})
    rng = random.Random(seed)
    sequence = [rng.choice(list(records)) for _ in range(reads)]
    for key in sequence:
        assert api('/get?'+urlencode({'key': key}))['value'] == records[key]
    uniform = api('/stats')
    hot_key = next(iter(records))
    for _ in range(hot_requests):
        assert api('/get?'+urlencode({'key': hot_key}))['value'] == records[hot_key]
    hot = api('/stats')
    count = lambda stats: {n['id']: n['key_count'] for n in stats['nodes']}
    traffic = lambda stats: {n['id']: n['request_count'] for n in stats['nodes']}
    assert count(uniform) == count(hot) == count(after)
    assert sum(traffic(uniform).values()) == reads
    assert sum(traffic(hot).values()) == reads+hot_requests
    hot_owner = owners_after[hot_key]
    assert all(traffic(hot)[n]-traffic(uniform)[n] == (hot_requests if n == hot_owner else 0)
               for n in traffic(hot))
    return {'mode': mode, 'vnodes_per_node': vnodes, 'key_count': keys,
        'dataset_sha256': hashlib.sha256(json.dumps(records, ensure_ascii=False).encode()).hexdigest(),
        'uniform_sequence_sha256': hashlib.sha256(json.dumps(sequence).encode()).hexdigest(),
        'placement_balance_before': balance(count(before)), 'placement_balance_after': balance(count(after)),
        'owners_before': owners_before, 'owners_after': owners_after,
        'ring_before': ring_before, 'ring_after': ring_after,
        'reassignment': observed, 'migration': joined,
        'verification': {'checked': keys, 'failures': failures, 'physical_failures': physical_failures},
        'request_balance': {'uniform_reads': reads, 'additional_hot_reads': hot_requests,
            'before_hot': traffic(uniform), 'after_hot': traffic(hot), 'hot_key': hot_key,
            'hot_key_owner': hot_owner, 'ratio_after_hot': balance(traffic(hot))['max_min_ratio']},
        'physical_inventory': inventory, 'membership': api('/admin/membership')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--router', default='http://127.0.0.1:8000')
    p.add_argument('--keys', type=int, default=1000)
    p.add_argument('--mode', choices=['modulo', 'consistent'], default='consistent')
    p.add_argument('--vnodes', type=int, default=16)
    p.add_argument('--hot-requests', type=int, default=500)
    p.add_argument('--new-node', default='D=localhost:5004')
    p.add_argument('--out', type=Path, default=Path('results/experiment.json'))
    args = p.parse_args()
    node, addr = args.new_node.split('=', 1)
    result = run_case(args.router, args.mode, args.vnodes, args.keys, hot_requests=args.hot_requests,
                      new_node=node, new_address=addr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(f"PASS: {args.keys} exact values; {result['reassignment']['fraction']:.1%} reassigned; output {args.out}")


if __name__ == '__main__':
    main()
