"""Check the actual report PDF, its derived table and its public source inputs."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha256(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def audit():
    import fitz
    from tools.build_report import results_table
    from tools.check_publication import private
    report = ROOT/'submission/report.pdf'
    source = (ROOT/'submission/report.tex').read_text(encoding='utf-8')
    require = lambda condition, message: None if condition else fail(message)
    require(r'\documentclass[12pt,a4paper]{article}' in source and r'\usepackage{lmodern}' in source,
        'The report must use A4, 12 pt Latin Modern article text.')
    require(not re.search(r'[\u3400-\u9fff]', source), 'The report source must be English.')
    require('beamer' not in source.lower(), 'The public report must not be a slide source.')
    require((ROOT/'submission/results-table.tex').read_text(encoding='utf-8') == results_table(),
        'The table differs from the source-matched raw study.')
    fonts = set()
    with fitz.open(report) as document:
        require(len(document) == 5, 'Expected four main pages and one reference page.')
        require(document.metadata.get('author') == 'Paco', 'PDF author must be Paco.')
        texts = [page.get_text() for page in document]
        require(texts[-1].startswith('References'), 'References must start on page 5.')
        require(all(not t.startswith('References') for t in texts[:4]), 'Main text page is missing.')
        for i, page in enumerate(document, 1):
            require(abs(page.rect.width-595.276) < 0.2 and abs(page.rect.height-841.890) < 0.2,
                f'Page {i} is not A4.')
            require(texts[i-1].rstrip().endswith(str(i)), f'Page {i} has no expected page number.')
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        fonts.add(span['font'])
                        require(fitz.Rect(span['bbox']) in page.rect, f'Clipped text on page {i}.')
                        require('\ufffd' not in span['text'], f'Missing glyph on page {i}.')
            for font in page.get_fonts():
                require(bool(document.extract_font(font[0])[3]), f'Unembedded font: {font[3]}.')
        body = '\n'.join(texts[:4])
        compact = re.sub(r'\s+', ' ', body)
        for token in ['30,000', '46 tests', 'TOML', '408', '54.6%', '15.4 GiB',
                'Changes after presentation feedback', 'initial mathematical derivations', 'Codex']:
            require(token in compact, 'Required report content missing: '+token)
        require('LMRoman12-Regular' in fonts, 'The main Latin Modern 12 pt font is missing.')
        require(len(re.findall(r'Consistent\s+V\s*=', texts[2])) == 9, 'The PDF must show all nine consistent settings.')
    inputs = ['submission/report.tex', 'submission/results-table.tex',
        'docs/assets/architecture/diagram.png', 'results/final/figures/requests.pdf',
        'results/final/environment.json', 'results/final/summary.csv',
        'tools/build_report.py', 'tools/check_submission.py']
    require(all(not private(name) for name in [*inputs, 'submission/report.pdf']),
        'An input is private presentation material.')
    return {'author': 'Paco', 'status': 'passed', 'main_pages': 4, 'reference_pages': 1,
        'paper': 'A4', 'body_font': 'Latin Modern, 12 TeX pt', 'fonts_embedded': True,
        'table_settings': 10, 'source_matched': True, 'author_math_attribution_present': True,
        'manual_visual_review': 'required separately; automated checks do not certify appearance',
        'pdf_sha256': sha256(report), 'input_sha256': {name: sha256(ROOT/name) for name in inputs}}


def fail(message):
    raise ValueError(message)


def main():
    try:
        receipt = audit()
        (ROOT/'submission/build-checks.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        print('PASS: four A4 main pages + one references page; Latin Modern; Paco; embedded fonts; source-matched 10-setting table.')
    except (ImportError, OSError, ValueError, KeyError) as exc:
        raise SystemExit(f'Cannot validate submission: {exc}. Use requirements-dev.txt for PDF inspection.') from exc


if __name__ == '__main__':
    main()
