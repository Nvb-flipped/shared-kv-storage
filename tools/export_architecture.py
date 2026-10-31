"""Export the native architecture SVG headlessly and check rendered text geometry."""
import argparse
from itertools import combinations
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def check_grid(root):
    elements = {e.get('data-asset-key'):e for e in root.iter() if e.get('data-asset-key')}
    def box(key):
        return tuple(float(elements[key].get(k)) for k in ('x','y','width','height'))
    def route(key):
        return [tuple(map(float,p.split(','))) for p in elements[key].get('points').split()]
    clients = [box(n+'-boundary') for n in ('cli','experiment')]
    stores = [box('store-'+n+'-boundary') for n in 'abcd']
    router, active = box('router-boundary'), box('active-enclosure')
    incoming = [route(n+'-to-router') for n in ('cli','experiment')]
    outgoing = [route('router-to-'+n) for n in 'abc']
    join = route('router-to-d-join')
    centers = [b[1]+b[3]/2 for b in stores]
    checks = {
        'equal_client_and_store_dimensions':len({b[2:] for b in clients+stores})==1,
        'client_column_aligned':clients[0][0]==clients[1][0],
        'store_column_aligned':len({b[0] for b in stores})==1,
        'store_rows_regular':len({centers[i+1]-centers[i] for i in range(3)})==1,
        'client_rows_match_outer_active_stores':[b[1]+b[3]/2 for b in clients]==[centers[0],centers[2]],
        'client_elbows_share_axis':incoming[0][1][0]==incoming[1][1][0],
        'active_store_elbows_share_axis':outgoing[0][1][0]==outgoing[2][1][0],
        'client_connections_anchor_on_edges':all(r[0]==(b[0]+b[2],b[1]+b[3]/2) for r,b in zip(incoming,clients)),
        'router_inputs_anchor_on_left_edge':all(r[-1][0]==router[0] for r in incoming),
        'router_outputs_anchor_on_right_edge':all(r[0][0]==router[0]+router[2] for r in outgoing),
        'store_connections_anchor_on_edges':all(r[-1]==(b[0],b[1]+b[3]/2) for r,b in zip(outgoing,stores)),
        'join_anchors_on_waiting_store':join[-1]==(stores[3][0],centers[3]),
        'router_input_output_rows_match':[r[-1][1] for r in incoming]==[outgoing[0][0][1],outgoing[2][0][1]],
        'router_output_rows_regular':outgoing[1][0][1]-outgoing[0][0][1]==outgoing[2][0][1]-outgoing[1][0][1],
        'outer_router_and_membership_bounds_align':router[1::2]==active[1::2],
        'join_uses_router_center_axis':join[0]==(router[0]+router[2]/2,router[1]+router[3]) and join[1][0]==join[0][0],
        'waiting_store_outside_active_enclosure':stores[3][1]>active[1]+active[3],
        'all_connection_segments_orthogonal':all(a[0]==b[0] or a[1]==b[1] for r in incoming+outgoing+[join] for a,b in zip(r,r[1:])),
    }
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error('Choose a new or empty output directory.')
    BrowserError = RuntimeError
    try:
        import pymupdf
        from PIL import Image, PngImagePlugin
        from playwright.sync_api import sync_playwright, Error as BrowserError
        source = ROOT/'docs/assets/architecture/diagram.svg'
        svg = source.read_text(encoding='utf-8')
        root = ET.fromstring(svg)
        width = float(root.get('width').removesuffix('pt'))
        height = float(root.get('height').removesuffix('pt'))
        author = root.get('data-author')
        if author != 'Paco':
            raise ValueError('The native source must identify Paco as author.')
        grid = check_grid(root)
        if not all(grid.values()):
            raise ValueError('Source grid failed: '+', '.join(k for k,v in grid.items() if not v))
        out.mkdir(parents=True, exist_ok=True)
        html = (f'<style>@page{{size:{width}pt {height}pt;margin:0}}'
                f'html,body{{margin:0;background:white}}svg{{display:block;width:{width}pt;height:{height}pt}}</style>'+svg)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(html)
                page.evaluate('document.fonts.ready')
                geometry = page.evaluate('''() => {
                  const r=document.querySelector('svg').getBoundingClientRect();
                  return {canvas:[r.width,r.height],texts:[...document.querySelectorAll('text')].map(e=>{
                    const b=e.getBoundingClientRect(),m=e.getScreenCTM();
                    return {text:e.textContent,box:[b.left-r.left,b.top-r.top,b.right-r.left,b.bottom-r.top],
                      font_pt:parseFloat(getComputedStyle(e).fontSize)*Math.hypot(m.c,m.d)*72/96};
                  })}; }''')
                page.pdf(path=str(out/'diagram.pdf'), print_background=True, prefer_css_page_size=True)
            finally:
                browser.close()
        findings = []
        for item in geometry['texts']:
            x0, y0, x1, y1 = item['box']
            if x0 < -.5 or y0 < -.5 or x1 > geometry['canvas'][0]+.5 or y1 > geometry['canvas'][1]+.5:
                findings.append('Clipped text: '+item['text'])
            if item['font_pt'] < 8:
                findings.append('Text smaller than 8 pt: '+item['text'])
        for a, b in combinations(geometry['texts'], 2):
            overlap_x = min(a['box'][2],b['box'][2])-max(a['box'][0],b['box'][0])
            overlap_y = min(a['box'][3],b['box'][3])-max(a['box'][1],b['box'][1])
            if overlap_x > .75 and overlap_y > .75:
                findings.append('Overlapping labels: '+a['text']+' / '+b['text'])
        with pymupdf.open(out/'diagram.pdf') as doc:
            if len(doc) != 1 or doc[0].get_images():
                findings.append('Expected one vector PDF page without raster images.')
            metadata = doc.metadata
            metadata['author'] = author
            doc.set_metadata(metadata)
            doc.saveIncr()
            pix = doc[0].get_pixmap(dpi=300, alpha=False)
            image = Image.frombytes('RGB', (pix.width,pix.height), pix.samples)
            info = PngImagePlugin.PngInfo(); info.add_text('Author',author)
            exif = Image.Exif(); exif[315] = author; exif[40093] = (author+'\0').encode('utf-16le')
            image.save(out/'diagram.png', dpi=(300,300), pnginfo=info, exif=exif.tobytes())
        report = {'author':author, 'status':'failed' if findings else 'passed',
                  'source':'docs/assets/architecture/diagram.svg',
                  'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                  'print_size_pt':[width,height], 'text_labels':len(geometry['texts']),
                  'minimum_font_pt':min(t['font_pt'] for t in geometry['texts']),
                  'grid_checks':grid, 'findings':findings,
                  'scope':'Actual SVG grid/routes, rendered text bounds, font floor, label overlap and PDF structure; semantic review is separate.'}
        (out/'export-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        if findings:
            raise ValueError('Rendered geometry failed; read export-checks.json.')
        print('PASS: architecture SVG exported to vector PDF and 300 dpi PNG; all rendered labels checked.')
    except (ImportError, OSError, ValueError, BrowserError) as exc:
        parser.exit(1, f'Architecture export failed: {exc}. Install requirements-diagrams.txt and Chromium headless shell.\n')


if __name__ == '__main__':
    main()
