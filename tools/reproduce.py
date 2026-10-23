"""Portable reproduction using the selected interpreter, without a named venv."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.analysis import build_report, load_run
from sharedkv.config import load_config
from sharedkv.study import run_study, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configs/study.toml')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--plots', action='store_true')
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        out = args.out if args.out is not None else args.config.parent/config.experiment.output
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise ValueError('Choose a new or empty --out directory.')
        if args.plots:
            try:
                import matplotlib
            except ImportError as exc:
                raise ValueError('Install requirements-figures.txt into this interpreter before using --plots.') from exc
        tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-v'], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8')
        print(tests.stdout+tests.stderr, end='', flush=True)
        if tests.returncode:
            return tests.returncode
        run_study(config, out, args.config)
        build_report(out, plots=args.plots, require_current=True)
        load_run(out, require_current=True)
        (out/'tests.txt').write_text(tests.stdout+tests.stderr, encoding='utf-8', newline='\n')
        write_json(out/'workflow.json', {'status': 'passed', 'tests': 'passed',
            'study': 'complete', 'evidence': 'verified against current sources', 'figures': args.plots})
        print(f'Reproduction passed. Read {out/"analysis.md"}.')
        return 0
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        parser.exit(1, f'Reproduction failed: {exc}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Reproduction interrupted; owned cluster processes were stopped.\n')


if __name__ == '__main__':
    raise SystemExit(main())
