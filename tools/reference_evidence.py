"""Authenticate historical source receipts without relabeling them as current runs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def check_source(name, expected):
    current = ROOT/name
    if current.is_file() and hashlib.sha256(current.read_bytes()).hexdigest() == expected:
        return 'current'
    provenance = json.loads((ROOT/'results/framework/provenance.json').read_text(encoding='utf-8'))
    revision = provenance['source_revision']
    if not re.fullmatch('[0-9a-f]{40}', revision) or name.startswith('/') or '..' in Path(name).parts:
        raise ValueError('Invalid reference source locator.')
    try:
        data = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=ROOT, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        raise ValueError('Reference source revision unavailable; use a full Git clone to audit historical receipts.') from exc
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Reference source digest differs: {name}')
    return 'historical'
