"""Pure HTTP experiment client. Owners come exclusively from router responses."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time
from urllib.parse import urlencode
from .metrics import balance, movement
from .config import ExperimentConfig
from .transport import ApiError, request


def dataset(count):
    return {f'key-{i:05d}': f'value-{i:05d}-λ-{i*i}' for i in range(count)}


def verify(condition, message):
    # These are runtime evidence checks and must also run under python -O.
    if not condition:
        raise ValueError('Experiment verification failed: '+message)


def run_case(base, mode, vnodes=16, keys=1000, reads=1000, hot_requests=500,
             seed=3010, new_node='D', new_address='localhost:5004'):
    api = lambda route, method='GET', body=None: request(base, route, method, body, timeout=120)
    ExperimentConfig(keys=keys, uniform_reads=reads, additional_hot_reads=hot_requests,
                     seed=seed, trials=1, modes=(mode,), vnodes=(vnodes,))
    if not isinstance(new_node, str) or len(new_node) != 1 or not 'A' <= new_node <= 'Z':
        raise ValueError('The joining node must be an uppercase ID A..Z.')
    records = dataset(keys)
    initial = api('/admin/membership')
    if new_node in [n['id'] for n in initial['nodes']]:
        raise ValueError('Use a fresh cluster; the joining ID is already registered.')
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
    verify(len(inventory['keys']) == keys and not physical_failures and not failures, 'values or physical ownership differ.')
    verify(joined['migrated'] == joined['verified'] == joined['reassigned_key_count'] == observed['reassigned_key_count'], 'migration counts differ.')
    expected_size = sum(len(json.dumps({'key': key, 'value': records[key]}, ensure_ascii=False).encode())
                        for key in joined['reassigned_keys'])
    verify(expected_size == joined['estimated_item_bytes'], 'logical size estimate differs.')
    # Measurements below exclude loading, migration, verification and inspection.
    api('/admin/reset_counters', 'POST', {})
    rng = random.Random(seed)
    key_list = list(records)
    sequence = [rng.choice(key_list) for _ in range(reads)]
    for key in sequence:
        verify(api('/get?'+urlencode({'key': key}))['value'] == records[key], 'uniform read returned a wrong value.')
    uniform = api('/stats')
    hot_key = next(iter(records))
    for _ in range(hot_requests):
        verify(api('/get?'+urlencode({'key': hot_key}))['value'] == records[hot_key], 'hot read returned a wrong value.')
    hot = api('/stats')
    count = lambda stats: {n['id']: n['key_count'] for n in stats['nodes']}
    traffic = lambda stats: {n['id']: n['request_count'] for n in stats['nodes']}
    verify(count(uniform) == count(hot) == count(after), 'key counts changed during reads.')
    verify(sum(traffic(uniform).values()) == reads, 'uniform read counters differ.')
    verify(sum(traffic(hot).values()) == reads+hot_requests, 'combined read counters differ.')
    hot_owner = owners_after[hot_key]
    verify(all(traffic(hot)[n]-traffic(uniform)[n] == (hot_requests if n == hot_owner else 0)
               for n in traffic(hot)), 'hot reads reached an unexpected owner.')
    return {'mode': mode, 'vnodes_per_node': vnodes, 'key_count': keys,
        'dataset_sha256': hashlib.sha256(json.dumps(records, ensure_ascii=False).encode()).hexdigest(),
        'uniform_sequence_sha256': hashlib.sha256(json.dumps(sequence).encode()).hexdigest(),
        'initial_nodes': sorted(n['id'] for n in initial['nodes']), 'joining_node': new_node,
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
    p.add_argument('--reads', type=int, default=1000)
    p.add_argument('--seed', type=int, default=3010)
    p.add_argument('--new-node', default='D=localhost:5004')
    p.add_argument('--out', type=Path, default=Path('results/experiment.json'))
    args = p.parse_args()
    try:
        node, addr = args.new_node.split('=', 1)
        result = run_case(args.router, args.mode, args.vnodes, args.keys, reads=args.reads,
                          hot_requests=args.hot_requests, seed=args.seed,
                          new_node=node, new_address=addr)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    except (ValueError, OSError, ApiError) as exc:
        p.exit(1, f'Experiment failed: {exc}\n')
    except KeyboardInterrupt:
        p.exit(130, 'Experiment interrupted; inspect the existing cluster before retrying.\n')
    print(f"PASS: {args.keys} exact values; {result['reassignment']['fraction']:.1%} reassigned; output {args.out}")


if __name__ == '__main__':
    main()
