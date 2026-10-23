"""Audit public figure outputs, math receipts and documentation navigation."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.doc_navigation import ORDER
OUT=ROOT/'results/framework'
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    manifest=json.loads((OUT/'figure-manifest.json').read_text())
    assert manifest['source_sha256']==digest(ROOT/'tools/report.py')
    assert manifest['plot_source_sha256']==digest(ROOT/'tools/figures.py')
    assert manifest['summary_sha256']==digest(OUT/'summary.json')
    assert len(manifest['outputs'])==21
    assert all((ROOT/name).is_file() for name in manifest['outputs'])
    math=json.loads((OUT/'math-validation.json').read_text());assert math['status']=='passed'
    for row in math['source_files']: assert digest(ROOT/row['path'])==row['sha256'],row['path']
    authors=json.loads((OUT/'author-properties.json').read_text())
    expected=set(manifest['outputs'])|{p.relative_to(ROOT).as_posix() for p in (ROOT/'results/qa').glob('figures-*.png')}
    assert {r['file'] for r in authors['files']}==expected
    for row in authors['files']: assert digest(ROOT/row['file'])==row['sha256'],row['file']
    assert all('<!-- navigation:start -->' in (ROOT/'docs'/name).read_text() and '<!-- reading:start -->' in (ROOT/'docs'/name).read_text() for name in ORDER)
    audits=json.loads((OUT/'figure-qa/run-summary.json').read_text());assert all(row['exit']==0 for row in audits)
    for path in (OUT/'figure-qa').glob('*.collisions.json'):
        assert not json.loads(path.read_text())['findings']
    report={'author':'Paco','status':'passed','figure_outputs':21,'navigation_pages':len(ORDER),
        'math_expressions':math['rendered_expressions'],'author_exports':authors['checked'],
        'figure_audits':len(audits),'figure_collision_findings':0,
        'scope':'Public experiment figures, saved math checks, navigation and evidence hashes.'}
    (OUT/'artifact-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"PASS: 21 figure outputs; {len(ORDER)} documentation pages; math, author and figure-audit receipts.")
if __name__=='__main__': main()
