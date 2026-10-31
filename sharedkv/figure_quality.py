"""Portable render-time geometry gates, independent of local plotting skills."""
import math


def inspect_layout(fig, tolerance_pt=1.5):
    """Check comparable plot areas and explicit label bounds before export."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    scale = 72/fig.dpi
    axes = [ax for ax in fig.axes if ax.get_visible()]
    rectangles = [tuple(v*scale for v in ax.bbox.bounds) for ax in axes]
    if any(not all(math.isfinite(v) for v in r) or min(r[2:]) <= 0 for r in rectangles):
        raise ValueError('A figure has an empty or non-finite plot area.')
    if len(axes) > 1:
        for rect in rectangles[1:]:
            if max(abs(rect[i]-rectangles[0][i]) for i in (1, 2, 3)) > tolerance_pt:
                raise ValueError('Comparable panels differ in rendered width, height or bottom edge.')
    texts = list(fig.texts)
    for ax in axes:
        texts += [ax.title, ax.xaxis.label, ax.yaxis.label, *ax.texts]
        if ax.get_legend():
            texts += list(ax.get_legend().get_texts())
    checked = 0
    for text in texts:
        if not text.get_visible() or not text.get_text():
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.x1+1 or box.y1 > fig.bbox.y1+1:
            raise ValueError(f'Figure label leaves its canvas: {text.get_text()!r}')
        if text.get_fontsize() < 7:
            raise ValueError('A figure label is below the 7 pt course export floor.')
        checked += 1
    return {'status': 'passed', 'units': 'pt', 'tolerance_pt': tolerance_pt,
            'plot_areas_xywh': rectangles, 'explicit_text_boxes_checked': checked,
            'comparable_panels': len(axes),
            'scope': 'Rendered alignment and explicit labels; PDF and visual inspection remain separate.'}
