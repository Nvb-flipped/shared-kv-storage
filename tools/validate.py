"""One fresh full validation round; inspect its original/grayscale sheets afterward."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.study import digest, source_hashes, write_json


def source_fingerprint():
    # A local ignored slide helper must not change the public-source identity.
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    roots = {'README.md', 'pyproject.toml', 'package.json', 'package-lock.json', '.gitignore', '.gitattributes', 'refined_spec.md'}
    directories = {'sharedkv', 'tests', 'tools', 'configs', 'docs', '.github'}
    paths = [ROOT/name for name in names if name and (ROOT/name).is_file() and
             (name in roots or Path(name).parts[0] in directories or
              (len(Path(name).parts) == 1 and (name.endswith(('.py', '.sh')) or name.startswith('requirements'))))]
    hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error('Choose a new or empty --out directory; validation never reuses receipts.')
    out.mkdir(parents=True, exist_ok=True)
    before = source_fingerprint()
    receipt = {'status': 'running', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'os': platform.system(), 'python': platform.python_version(),
               'source_fingerprint': before, 'package_source_sha256': source_hashes(), 'stages': []}

    def stage(name, command, cwd=ROOT, input_text=None, expected=(), forbidden=()):
        print(f'RUN {name}', flush=True)
        result = subprocess.run(command, cwd=cwd, input=input_text, capture_output=True,
                                text=True, encoding='utf-8', errors='replace')
        log = out/f'{name}.txt'
        log.write_text(result.stdout+result.stderr, encoding='utf-8', newline='\n')
        output_ok = all(token in result.stdout for token in expected) and not any(token in result.stdout+result.stderr for token in forbidden)
        receipt['stages'].append({'name': name, 'exit': result.returncode, 'output_checks': output_ok, 'log_sha256': digest(log)})
        if result.returncode or not output_ok:
            print(result.stdout+result.stderr, end='', flush=True)
            raise ValueError(f'{name} failed; read {log.name}.')
        print(f'PASS {name}', flush=True)

    python = sys.executable
    try:
        try:
            import matplotlib, PIL, pymupdf, colorspacious, jsonschema, openapi_spec_validator
        except ImportError as exc:
            raise ValueError('Install requirements-dev.txt into this interpreter before full validation.') from exc
        stage('reproduction', [python, 'tools/reproduce.py', '--config', 'configs/quick.toml', '--out', str(out/'study'), '--plots'])
        workflow = json.loads((out/'study/workflow.json').read_text(encoding='utf-8'))
        if workflow['tests_skipped']:
            raise ValueError('Full validation requires zero skipped tests; install requirements-dev.txt.')
        receipt['tests_run'], receipt['tests_skipped'] = workflow['tests_run'], workflow['tests_skipped']
        stage('cli', [python, 'tools/rehearse.py', '--out', str(out/'cli')])
        stage('api', [python, 'tools/check_contracts.py', '--out', str(out/'api')])
        stage('api-generation', [python, 'tools/api_contracts.py'])
        stage('documentation', [python, 'tools/check_project.py'])
        stage('historical-artifacts', [python, 'tools/check_artifacts.py'])
        stage('publication', [python, 'tools/check_publication.py'])
        if os.environ.get('MATHJAX_PACKAGE') or (ROOT/'node_modules/mathjax-full').is_dir():
            stage('math-rendering', ['node', 'tools/check_math.cjs', '--out', str(out/'math-validation.json')])
        edge_config = out/'edge.toml'
        edge_config.write_text('[cluster]\ninitial_nodes=["X","Y","Z"]\njoining_node="A"\n'
            '[experiment]\nkeys=1\nuniform_reads=2\nadditional_hot_reads=0\ntrials=1\n'
            'modes=["modulo","consistent"]\nvnodes=[3]\n', encoding='utf-8', newline='\n')
        stage('edge-study', [python, '-m', 'sharedkv', 'study', '--config', str(edge_config), '--out', str(out/'edge')])
        stage('edge-report', [python, '-m', 'sharedkv', 'report', '--input', str(out/'edge'), '--plots', '--require-current-source'])
        for name in ('study', 'edge'):
            stage(name+'-figure-audit', [python, 'tools/check_figures.py', '--input', str(out/name)])
            stage(name+'-visual-qa', [python, 'tools/visual_qa.py', '--input', str(out/name)])
        wheel_dir = out/'wheels'
        stage('wheel', [python, '-m', 'pip', 'wheel', '--no-deps', '--wheel-dir', str(wheel_dir), str(ROOT)])
        environment = out/'installed-env'
        venv.EnvBuilder(with_pip=True).create(environment)
        installed = environment/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        stage('install', [str(installed), '-m', 'pip', 'install', '--no-index', '--no-deps', str(next(wheel_dir.glob('*.whl')))])
        outside = out/'outside-checkout'
        outside.mkdir()
        study = outside/'run'
        stage('installed-study', [str(installed), '-I', '-m', 'sharedkv', 'study', '--config', str(ROOT/'configs/quick.toml'), '--out', str(study),
            '--keys', '6', '--reads', '8', '--hot-requests', '0', '--trials', '1', '--modes', 'consistent', '--vnodes', '2'], cwd=outside)
        stage('installed-report', [str(installed), '-I', '-m', 'sharedkv', 'report', '--input', str(study), '--require-current-source'], cwd=outside)
        stage('installed-demo', [str(installed), '-I', '-m', 'sharedkv', 'demo', '--isolated', '--nodes', 'X,Y', '--joining-node', 'Z'],
              cwd=outside, input_text='put installed-key installed-value\nget installed-key\nowner installed-key\nstats\nquit\n',
              expected=('[STORED]', '[FOUND]', 'installed-value', 'X/Y are members. Z waits', 'placement=consistent'),
              forbidden=('[REJECTED]', '[NOT FOUND]', 'Traceback', 'Usage:'))
        if source_fingerprint() != before:
            raise ValueError('Source/docs/configs changed during validation; rerun from a frozen revision.')
        receipt['status'] = 'automated_passed'
        receipt['visual_review'] = 'pending: inspect study and edge original/grayscale sheets'
        receipt['limits'] = 'Finite tests and exercised configurations; not a proof over all possible operations or environments.'
    except (OSError, ValueError, RuntimeError, StopIteration) as exc:
        receipt['status'] = 'failed'
        receipt['failure'] = str(exc)
        print(f'Validation failed: {exc}', file=sys.stderr)
    except KeyboardInterrupt:
        receipt['status'] = 'interrupted'
    finally:
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(out/'validation.json', receipt)
    return 0 if receipt['status'] == 'automated_passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
