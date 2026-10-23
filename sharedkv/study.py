"""Run a controlled, local single-node-join exercise from validated settings."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random

from .cluster import Cluster
from .config import ConfigError, load_config, override
from .transport import ApiError

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, data):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schedule_for(config):
    rng = random.Random(config.seed)
    schedule = []
    for trial in range(1, config.trials+1):
        order = config.cases()
        rng.shuffle(order)
        for mode, vnodes in order:
            schedule.append({'trial': trial, 'mode': mode, 'vnodes': vnodes,
                             'file': f'{mode}-v{vnodes}-t{trial}.json'})
    return schedule


def source_hashes():
    paths = sorted((ROOT/'sharedkv').glob('*.py'))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def run_study(config, out, config_path=None):
    """A nonempty output directory is never reused or silently mixed with old runs."""
    from .experiment import run_case
    out = Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ConfigError('Output must be a new or empty directory. Choose another --out path.')
    out.mkdir(parents=True, exist_ok=True)
    snapshot = config.snapshot()
    snapshot['experiment']['output'] = '.'
    schedule = schedule_for(config.experiment)
    manifest = {
        'schema_version': 1, 'status': 'running',
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'environment': {'os': platform.system(), 'architecture': platform.machine(),
                        'python': platform.python_version()},
        'config': snapshot, 'schedule': schedule, 'completed': [],
        'source_sha256': source_hashes(),
        'config_sha256': digest(Path(config_path)) if config_path else None,
        'interpretation': 'Fixed node identities and keys; fresh-process timing repetitions, not independent layouts.',
    }
    # Exclusive creation also protects against two collectors choosing the same
    # initially empty output directory at the same time.
    with (out/'environment.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    try:
        for case in schedule:
            cluster_config = replace(config.cluster, placement=case['mode'], vnodes=case['vnodes'])
            settings = config.experiment
            with Cluster.from_config(cluster_config) as cluster:
                result = run_case(cluster.url, case['mode'], case['vnodes'], settings.keys,
                    settings.uniform_reads, settings.additional_hot_reads, settings.seed,
                    new_node=cluster.joining_node, new_address=cluster.addresses[cluster.joining_node])
                result.update(trial=case['trial'], pids={n: p.pid for n, p in cluster.processes.items()})
            result['owned_children_stopped'] = all(p.poll() is not None for p in cluster.processes.values())
            write_json(out/case['file'], result)
            manifest['completed'].append({'file': case['file'], 'sha256': digest(out/case['file'])})
            write_json(out/'environment.json', manifest)
            print(f"PASS {case['file']}: {settings.keys} exact values; "
                  f"{result['reassignment']['fraction']:.1%} reassigned.", flush=True)
        if source_hashes() != manifest['source_sha256']:
            raise RuntimeError('Sources changed during collection. Choose a new output directory and rerun.')
        manifest['status'] = 'complete'
    except BaseException as exc:
        manifest['status'] = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed'
        manifest['failure_type'] = type(exc).__name__
        raise
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(out/'environment.json', manifest)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/study.toml'))
    parser.add_argument('--out', type=Path, help='Output relative to the current working directory.')
    parser.add_argument('--keys', type=int)
    parser.add_argument('--reads', type=int)
    parser.add_argument('--hot-requests', type=int)
    parser.add_argument('--trials', type=int)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--vnodes', type=int, nargs='+')
    parser.add_argument('--modes', choices=['modulo', 'consistent'], nargs='+')
    parser.add_argument('--dry-run', action='store_true', help='Validate and print the schedule; start nothing.')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        settings = override(config.experiment, dict(keys=args.keys, uniform_reads=args.reads,
            additional_hot_reads=args.hot_requests, trials=args.trials, seed=args.seed,
            vnodes=tuple(args.vnodes) if args.vnodes is not None else None,
            modes=tuple(args.modes) if args.modes is not None else None))
        config = replace(config, experiment=settings)
        out = args.out if args.out is not None else args.config.parent/settings.output
        if args.dry_run:
            print(json.dumps({'config': config.snapshot(), 'output': str(out),
                              'schedule': schedule_for(settings)}, indent=2))
            return 0
        run_study(config, out, args.config)
        print(f'Saved {len(schedule_for(settings))} trials. Analyze with: python -m sharedkv report --input "{out}"')
        return 0
    except (ConfigError, OSError, RuntimeError, ApiError, ValueError, AssertionError) as exc:
        parser.exit(1, f'Study failed: {exc}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Study interrupted; owned child processes were stopped.\n')


if __name__ == '__main__':
    raise SystemExit(main())
