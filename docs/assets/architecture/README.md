# Architecture figure

Author: Paco.

`diagram.svg` is the editable source. It contains the actual labels, component geometry and connection paths, with the two used Arimo font faces embedded. `diagram.png` is its 300 dpi preview. The figure describes the default process topology, not experimental observations.

The client and storage rectangles have equal dimensions. Headings, text anchors, process rows, router ports and connector elbows follow a shared grid. A/B/C are initially active; the running empty D remains outside membership until `addnode`. Device symbols represent software processes rather than physical hosts or replicas.

## Rebuild the exports

Run from the repository root:

```bash
python -m pip install -r requirements-diagrams.txt
python -m playwright install chromium --only-shell
python tools/export_architecture.py --out results/runs/architecture-export
```

The complete development requirements also include these Python dependencies. Minimal Linux/WSL installations may need `--with-deps` on the browser-install command to supply system libraries. The exporter runs headlessly, closes its browser, refuses nonempty output directories, and creates a vector PDF, 300 dpi PNG and rendered text checks. The local Vivid skill and private work packages are not needed. Edit the native SVG when changing the diagram.

`layout-checks.json` records the authoring geometry checks. Each export independently checks the actual SVG's component grid, port rows and connector elbows, then records those results with rendered text bounds, the font floor, label overlap and PDF structure in `export-checks.json`. These checks aid the actual visual and semantic review; neither alone establishes correctness for every future edit.

## Sources

The layout, process boundaries, ports and connections follow this project's implementation. The small terminal/server glyphs were adapted from Vivid Illustration VA-012, identified as `asplos26-008_fig1` in its [upstream collection](https://github.com/Sleepy-Avacado/FigGenie-paper-diagram-skill). The source glyphs are not claimed as original drawings.

Arimo Regular/Bold font name tables identify Apache License 2.0. Their exact copyright notice and license text are retained in [FONT-LICENSE.txt](FONT-LICENSE.txt). Unused embedded font faces were removed without changing font outlines or diagram geometry.
