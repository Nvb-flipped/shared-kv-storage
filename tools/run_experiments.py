"""Process orchestration only; experiment.py remains a pure HTTP client."""
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.cluster import Cluster
from experiment import run_case


def main():
    config = json.loads((ROOT/'configs/framework-experiment.json').read_text())
    out = ROOT/'results/framework'; out.mkdir(parents=True, exist_ok=True)
    cases = [('modulo', 1), *[('consistent', v) for v in config['vnodes']]]
    rng = random.Random(config['seed'])
    schedule = []
    for trial in range(1, config['trials']+1):
        order = cases.copy(); rng.shuffle(order)
        schedule += [{'trial': trial, 'mode': mode, 'v': v} for mode, v in order]
    sources = [*Path('sharedkv').glob('*.py'), Path('router.py'), Path('storage_node.py'), Path('experiment.py'), Path('tools/run_experiments.py')]
    environment = {'author': 'Paco', 'utc': datetime.now(timezone.utc).isoformat(),
        'platform': platform.platform(), 'python': platform.python_version(), 'root': str(ROOT),
        'config': config, 'schedule': schedule, 'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'timing_unit': 'fresh isolated cluster; join elapsed seconds; descriptive repetitions of a fixed placement'}
    (out/'environment.json').write_text(json.dumps(environment, indent=2)+'\n')
    for row in schedule:
        with Cluster(row['mode'], row['v']) as cluster:
            result = run_case(cluster.url, row['mode'], row['v'], config['keys'], config['uniform_reads'],
                config['additional_hot_reads'], config['seed'], new_address=cluster.addresses['D'])
            result.update(trial=row['trial'], pids={n: p.pid for n, p in cluster.processes.items()})
        result['owned_children_stopped'] = all(p.poll() is not None for p in cluster.processes.values())
        name = f"{row['mode']}-v{row['v']}-t{row['trial']}.json"
        (out/name).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(f"PASS {name}: moved {result['reassignment']['reassigned_key_count']}/{config['keys']}; all values exact; hot workload isolated.", flush=True)


if __name__ == '__main__':
    main()
