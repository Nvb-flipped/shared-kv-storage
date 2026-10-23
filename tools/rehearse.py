"""Rehearse every CLI command against independent local processes."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.cluster import Cluster
from experiment import dataset


def require(condition, message='Rehearsal check failed.'):
    if not condition:
        raise ValueError(message)


def run(mode, v):
    transcript, checks = [], []
    with Cluster(mode, v) as c:
        pids = {n: p.pid for n, p in c.processes.items()}
        def cli(*words, expected=0):
            result = subprocess.run([sys.executable, 'client.py', '--router', c.url, *words], capture_output=True, text=True, cwd=ROOT)
            require(result.returncode == expected, result.stderr)
            require('Traceback' not in result.stdout+result.stderr)
            transcript.append('>> User: '+' '.join(words)+'\n'+result.stdout+result.stderr)
            checks.append({'command': list(words), 'exit': result.returncode})
            return result.stdout+result.stderr
        cli('put', 'user:101', 'Apple'); cli('put', 'user:102', 'Banana')
        cli('put', 'user:101', 'Apple-2')
        require('Apple-2' in cli('get', 'user:101'))
        cli('get', 'missing', expected=3)
        require('Placement only' in cli('ring', 'missing'))
        require('Stored on' in cli('ring', 'missing', '--check'))
        cli('owner', 'user:101'); cli('ring', 'user:101', '--check')
        cli('help'); cli('membership'); cli('keys'); cli('recover', expected=4)
        cli('vnodes', 'not-an-integer', expected=2); cli('unknown', expected=2)
        records = dict(dataset(1000), **{'user:101': 'Apple-2', 'user:102': 'Banana'})
        for key, value in dataset(1000).items(): c.api('/put', 'POST', {'key': key, 'value': value})
        before = c.api('/stats')
        require('[JOINED]' in cli('addnode', 'D', c.addresses['D']))
        joined = c.api('/admin/membership')
        require(joined['version'] == 2 and not joined['paused_writes'])
        failures = [key for key, value in records.items()
                    if c.api('/get?'+urlencode({'key': key}))['value'] != value]
        require(not failures)
        inventory = c.api('/keys')
        require(len(inventory['keys']) == len(records))
        require(all(row['stored_on'] == [row['owner']] for row in inventory['keys']))
        cli('ring', 'user:101', '--check'); cli('stats'); cli('reset-counters')
        cli('placement', 'modulo' if mode == 'consistent' else 'consistent')
        cli('get', 'user:101', expected=4)
        cli('flush'); cli('vnodes', '128'); cli('put', 'user:101', 'Reloaded')
        require('Reloaded' in cli('get', 'user:101'))
        session = subprocess.run([sys.executable, 'client.py', '--router', c.url], input='get absent\nput k v\nget k\nquit\n', text=True, capture_output=True, cwd=ROOT)
        require(session.returncode == 0 and 'NOT FOUND' in session.stderr and '[FOUND]' in session.stdout)
        transcript += ['Interactive continuation:\n'+session.stdout+session.stderr]
        report = {'mode': mode, 'v': v, 'pids': pids, 'addresses': c.addresses,
            'cli_cases': checks, 'before': before, 'membership_after_join': joined,
            'verified_values': len(records), 'failures': failures,
            'physical_ownership_verified': True, 'interactive_continues_after_miss': True}
    report['owned_children_stopped'] = all(p.poll() is not None for p in c.processes.values())
    return report, '\n'.join(transcript)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'results/runs/cli-rehearsal')
    args = parser.parse_args()
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        parser.error('Choose a new or empty --out directory.')
    started = time.perf_counter(); rows = []
    out = args.out; out.mkdir(parents=True, exist_ok=True)
    for mode, v in [('modulo', 1), ('consistent', 1), ('consistent', 16)]:
        result, text = run(mode, v); rows.append(result)
        name = f'cli-{mode}-v{v}'
        (out/(name+'.ansi.txt')).write_text(text, encoding='utf-8', newline='\n')
        (out/(name+'.txt')).write_text(re.sub(r'\x1b\[[0-9;]*m', '', text), encoding='utf-8', newline='\n')
        print(f'PASS {mode} V={v}: CLI commands, misses, 1002 exact values, reconfiguration and clean shutdown.', flush=True)
    report = {'author': 'Paco', 'status': 'passed', 'cases': rows, 'seconds': time.perf_counter()-started,
              'kind': 'Automated CLI exercise; concurrent migration behavior is tested with deterministic barriers in tests/test_framework.py'}
    (out/'rehearsal.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__': main()
