"""Package public source, report and experiment evidence for UM submission."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from tools.check_submission import audit
    from tools.check_publication import main as publication_check, private
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    target = args.out.resolve()
    if target.exists():
        parser.error('Choose a new output path; existing archives are never overwritten.')
    try:
        audit()
        publication_check()
        paths = sorted(set(subprocess.check_output(['git', 'ls-files', '--cached', '--others',
            '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').rstrip('\0').split('\0')))
        hashes = {}
        for name in paths:
            file = ROOT/name
            parts = PurePosixPath(name).parts
            if private(name) or '..' in parts or PurePosixPath(name).is_absolute() or file.is_symlink():
                raise ValueError('Nonpublic or unsafe archive path: '+name)
            if not file.is_file():
                raise ValueError('Missing public file: '+name)
            hashes[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        for name in ['README.md', 'submission/report.pdf', 'submission/report.tex',
                'configs/study.toml', 'results/final/environment.json', 'tools/reproduce.py']:
            if name not in hashes:
                raise ValueError('Required submission file is missing: '+name)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents overwriting a concurrently created archive.
        with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in paths:
                archive.write(ROOT/name, name)
            archive.writestr('SUBMISSION_MANIFEST.json', json.dumps({'author': 'Paco',
                'runtime_release': 'v0.3.1', 'report_pages': '4 main + 1 references',
                'files_sha256': hashes}, indent=2)+'\n')
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != len(hashes)+1:
                raise ValueError('Archive integrity check failed.')
            for name, expected in hashes.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ValueError('Archive hash mismatch: '+name)
        print(f'PASS: {len(hashes)} public files; verified CRC and SHA-256; {target.stat().st_size/1024/1024:.1f} MiB.')
    except (OSError, ValueError, ImportError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'Cannot package submission: {exc}\n')


if __name__ == '__main__':
    main()
