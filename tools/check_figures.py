"""Check final figure hashes, PDF text geometry, author metadata and panel layouts."""
import argparse
from itertools import combinations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.analysis import read_json, require
from sharedkv.study import digest, write_json


def pdf_findings(path):
    import pymupdf
    findings, sizes = [], []
    with pymupdf.open(path) as document:
        if len(document) != 1:
            findings.append('Expected a single-page figure.')
        if document.metadata.get('author') != 'Paco':
            findings.append('PDF author is not Paco.')
        for page in document:
            spans = [span for block in page.get_text('dict')['blocks'] if 'lines' in block
                     for line in block['lines'] for span in line['spans'] if span['text'].strip()]
            if not spans:
                findings.append('No selectable figure text.')
            for span in spans:
                sizes.append(span['size'])
                if span['size'] < 5:
                    findings.append('A rendered glyph run is smaller than 5 pt.')
                box = pymupdf.Rect(span['bbox'])
                if not (page.rect+(-.75, -.75, .75, .75)).contains(box):
                    findings.append('Figure text is clipped by the page.')
            for first, second in combinations(spans, 2):
                a, b = pymupdf.Rect(first['bbox']), pymupdf.Rect(second['bbox'])
                overlap = a & b
                if overlap.width > .75 and overlap.height > .75:
                    findings.append('Overlapping text: '+repr(first['text'])+' / '+repr(second['text']))
    return {'file': path.name, 'findings': sorted(set(findings)),
            'minimum_font_pt': min(sizes) if sizes else None}


def audit(directory):
    from PIL import Image
    directory = Path(directory)
    manifest = read_json(directory/'figure-manifest.json')
    require(digest(directory/'summary.json') == manifest['summary_sha256'], 'Figure summary hash differs.')
    reports, images = [], []
    for name, expected in manifest['outputs'].items():
        path = directory/name
        require(digest(path) == expected, 'Figure digest differs: '+name)
        if path.suffix == '.pdf':
            reports.append(pdf_findings(path))
        elif path.suffix == '.png':
            with Image.open(path) as image:
                require(image.info.get('Author') == 'Paco' and image.getexif().get(315) == 'Paco',
                        'PNG author metadata differs: '+name)
                require(min(image.info.get('dpi', (0, 0))) >= 299, 'PNG is not a 300 dpi export: '+name)
                images.append({'file': name, 'size_px': list(image.size)})
        elif path.suffix == '.svg':
            text = path.read_text(encoding='utf-8')
            require('<text' in text and 'Paco' in text, 'SVG text or author metadata is missing: '+name)
    layouts = manifest.get('layouts', {})
    require(len(layouts) == 6, 'Six current render-time layout receipts are required.')
    for name, expected in layouts.items():
        require(digest(directory/name) == expected, 'Layout receipt hash differs: '+name)
        require(read_json(directory/name)['status'] == 'passed', 'Panel layout did not pass: '+name)
    return {'status': 'failed' if any(row['findings'] for row in reports) else 'passed',
            'pdf_figures': reports, 'png_exports': images, 'layout_receipts': len(layouts),
            'verified_export_hashes': len(manifest['outputs']),
            'scope': 'Export integrity, selectable PDF text, 5 pt floor, page bounds and text overlap. Visual review and color-vision checks are separate.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.input)
        write_json(args.input/'figure-audit.json', report)
        if report['status'] != 'passed':
            parser.exit(1, 'Figure checks failed; read figure-audit.json.\n')
        print(f"PASS: {report['verified_export_hashes']} exports, six PDFs and six layouts; text geometry and author metadata.")
    except (ImportError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'Cannot audit figures: {exc}. Install requirements-dev.txt for all checks.\n')


if __name__ == '__main__':
    main()
