"""Reject private slide material and likely credentials in Git's index/history.

Run after staging and before pushing. Local ignored files are never opened.
This is a focused guard, not a guarantee that every possible secret is detected.
"""
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FIGURES = {'balance', 'join-cost', 'key-shares', 'movement', 'node-loads', 'requests', 'transfers'}
EXAMPLE_FIGURES = {'movement', 'balance', 'node-loads', 'requests', 'transfers', 'join-time'}
SLIDE_EXTENSIONS = {'.ppt', '.pptx', '.pptm', '.pot', '.potx', '.potm', '.pps', '.ppsx', '.odp', '.key', '.tex', '.sty', '.cls'}
PRIVATE_FILES = {'docs/presentation.md', 'tools/build_beamer.py', 'tools/presentation_rings.py'}
PATTERNS = {
    'GitHub token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'private key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'AWS access key': re.compile(rb'(?:AKIA|ASIA)[A-Z0-9]{16}'),
    'URL credential': re.compile(rb'https?://[^\s/:@]+:[^\s/@]+@'),
}
LOCAL_PATH = re.compile(rb'(?:/' + rb'home' + rb'/[^/\s"\x27]+/|[A-Za-z]:[\\/]Users[\\/][^\\/\s"\x27]+[\\/])')
PASSWORD = re.compile(rb'(?i)\b(?:password|passwd|sudo_password)\s*[:=]\s*["\x27][^"\x27\s]{4,}["\x27]')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def private(path):
    value = path.lower()
    p = PurePosixPath(value)
    if value.startswith(('presentation/', 'reference-material/', 'docs/requirements/', '.runtime/', '.agents/', '.codex/')):
        return True
    if value in PRIVATE_FILES or p.suffix in SLIDE_EXTENSIONS:
        return True
    public_figure = (p.parent.as_posix() == 'figures' and p.stem in FIGURES) or (p.parent.as_posix() in {'results/example/figures', 'results/final/figures'} and p.stem in EXAMPLE_FIGURES)
    if p.suffix == '.pdf' and not public_figure:
        return True
    if any(part.startswith(('slides-', 'slide-')) for part in p.parts):
        return True
    if p.name.startswith('.env') and p.name != '.env.example':
        return True
    if p.suffix in {'.pem', '.p12', '.pfx'} or p.name.startswith(('id_rsa', 'id_ed25519')):
        return True
    return False


def main():
    git('rev-parse', '--git-dir')
    errors, blobs = set(), {}

    def inspect_tree(data, label):
        for row in filter(None, data.split(b'\0')):
            header, raw_path = row.split(b'\t', 1)
            fields = header.split()
            path = raw_path.decode('utf-8')
            if private(path):
                errors.add(f'{label}: private path {path}')
            if fields[0] == b'120000' or fields[0] == b'160000':
                errors.add(f'{label}: review link/submodule {path}')
            oid = fields[2] if len(fields) == 3 and fields[1] == b'blob' else fields[1]
            blobs.setdefault(oid.decode(), path)

    inspect_tree(git('ls-files', '--stage', '-z'), 'index')
    commits = git('rev-list', '--all').decode().splitlines()
    for commit in commits:
        inspect_tree(git('ls-tree', '-rz', '--full-tree', commit), commit[:12])
    # One Git process keeps this inexpensive on Windows as well as Linux.
    batch = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT,
        input=''.join(oid+'\n' for oid in blobs).encode(), stdout=subprocess.PIPE, check=True).stdout
    offset = 0
    for oid, path in blobs.items():
        end = batch.index(b'\n', offset)
        header = batch[offset:end].split()
        assert header[0].decode() == oid and header[1] == b'blob'
        size = int(header[2])
        data = batch[end+1:end+1+size]
        offset = end+size+2
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                errors.add(f'{path}: possible {label}')
    if errors:
        raise SystemExit('Publication check failed:\n' + '\n'.join(sorted(errors)))
    # Include edits and new publishable files before staging; never scan ignored skills or environments.
    paths = git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split(b'\0')
    for raw_path in filter(None, paths):
        path = raw_path.decode('utf-8')
        file = ROOT/path
        if not file.is_file():
            continue
        if private(path):
            errors.add(f'working tree: private path {path}')
        data = file.read_bytes()
        for label, pattern in [*PATTERNS.items(), ('machine-specific home path', LOCAL_PATH), ('password assignment', PASSWORD)]:
            if pattern.search(data):
                errors.add(f'{path}: possible {label}')
    if errors:
        raise SystemExit('Publication check failed:\n' + '\n'.join(sorted(errors)))
    print(f'PASS: index and {len(commits)} reachable commits; {len(blobs)} unique blobs; no slide material or matched credential patterns.')


if __name__ == '__main__':
    main()
