"""Rehearse the CLI and readable migration against independent WSL processes."""
from concurrent.futures import ThreadPoolExecutor
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
from sharedkv.transport import ApiError
from experiment import dataset


def run(mode, v):
    transcript, checks = [], []
    with Cluster(mode, v) as c:
        pids = {n: p.pid for n, p in c.processes.items()}
        def cli(*words, expected=0):
            result = subprocess.run([sys.executable, 'client.py', '--router', c.url, *words], capture_output=True, text=True, cwd=ROOT)
            assert result.returncode == expected, result.stderr
            assert 'Traceback' not in result.stdout+result.stderr
            transcript.append('>> User: '+' '.join(words)+'\n'+result.stdout+result.stderr)
            checks.append({'command': list(words), 'exit': result.returncode})
            return result.stdout+result.stderr
        cli('put', 'user:101', 'Apple'); cli('put', 'user:102', 'Banana')
        cli('put', 'user:101', 'Apple-2')
        assert 'Apple-2' in cli('get', 'user:101')
        cli('get', 'missing', expected=3)
        assert 'Placement only' in cli('ring', 'missing')
        assert 'Stored on' in cli('ring', 'missing', '--check')
        cli('owner', 'user:101'); cli('ring', 'user:101', '--check')
        records = dict(dataset(1000), **{'user:101': 'Apple-2', 'user:102': 'Banana'})
        for key, value in dataset(1000).items(): c.api('/put', 'POST', {'key': key, 'value': value})
        before = c.api('/stats')
        with ThreadPoolExecutor() as pool:
            future = pool.submit(c.api, '/admin/addnode', 'POST', {'id': 'D', 'addr': c.addresses['D']})
            deadline = time.monotonic()+10
            while not c.api('/admin/membership')['paused_writes']:
                assert time.monotonic() < deadline and not future.done()
                time.sleep(.001)
            try:
                c.api('/put', 'POST', {'key': 'during-join', 'value': 'blocked'})
                raise AssertionError('Write accepted during migration')
            except ApiError as exc:
                assert exc.status == 503; paused_status = exc.status
            during = c.api('/get?key=user%3A101')
            assert during['value'] == 'Apple-2'
            joined = future.result(30)
        failures = [key for key, value in records.items()
                    if c.api('/get?'+urlencode({'key': key}))['value'] != value]
        assert not failures
        inventory = c.api('/keys')
        assert len(inventory['keys']) == len(records)
        assert all(row['stored_on'] == [row['owner']] for row in inventory['keys'])
        cli('ring', 'user:101', '--check'); cli('stats'); cli('reset-counters')
        cli('placement', 'modulo' if mode == 'consistent' else 'consistent')
        cli('get', 'user:101', expected=4)
        cli('flush'); cli('vnodes', '128'); cli('put', 'user:101', 'Reloaded')
        assert 'Reloaded' in cli('get', 'user:101')
        session = subprocess.run([sys.executable, 'client.py', '--router', c.url], input='get absent\nput k v\nget k\nquit\n', text=True, capture_output=True, cwd=ROOT)
        assert session.returncode == 0 and 'NOT FOUND' in session.stderr and '[FOUND]' in session.stdout
        transcript += ['Interactive continuation:\n'+session.stdout+session.stderr]
        report = {'mode': mode, 'v': v, 'pids': pids, 'addresses': c.addresses,
            'cli_cases': checks, 'before': before, 'join': joined, 'paused_put_status': paused_status,
            'get_during_migration': during, 'verified_values': len(records), 'failures': failures,
            'physical_ownership_verified': True, 'interactive_continues_after_miss': True}
    report['owned_children_stopped'] = all(p.poll() is not None for p in c.processes.values())
    return report, '\n'.join(transcript)


def main():
    started = time.perf_counter(); rows = []
    out = ROOT/'results/framework'; out.mkdir(parents=True, exist_ok=True)
    for mode, v in [('modulo', 1), ('consistent', 1), ('consistent', 16)]:
        result, text = run(mode, v); rows.append(result)
        name = f'cli-{mode}-v{v}'
        (out/(name+'.ansi.txt')).write_text(text)
        (out/(name+'.txt')).write_text(re.sub(r'\x1b\[[0-9;]*m', '', text))
        print(f'PASS {mode} V={v}: CLI, misses, readable Get/paused Put, 1002 exact values, reconfiguration and clean shutdown.', flush=True)
    report = {'author': 'Paco', 'status': 'passed', 'cases': rows, 'seconds': time.perf_counter()-started,
              'kind': 'Automated operational rehearsal', 'human_spoken_rehearsal': 'pending'}
    (out/'rehearsal.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__': main()
