"""Optional geometry regression: zero loads and close timing points stay visible."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sharedkv.metrics import balance, movement


@unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Optional Matplotlib is not installed.')
class PlotGeometryTests(unittest.TestCase):
    def test_explicit_off_canvas_text_and_unequal_panels_are_rejected(self):
        import matplotlib.pyplot as plt
        from sharedkv.figure_quality import inspect_layout
        fig, ax = plt.subplots()
        ax.text(2, 2, 'outside', transform=ax.transAxes)
        with self.assertRaisesRegex(ValueError, 'leaves its canvas'):
            inspect_layout(fig)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2)
        box = axes[1].get_position()
        axes[1].set_position([box.x0, box.y0, box.width*.75, box.height])
        with self.assertRaisesRegex(ValueError, 'Comparable panels'):
            inspect_layout(fig)
        plt.close(fig)

    def test_markers_have_space_at_zero_and_with_nearly_identical_times(self):
        from sharedkv.plotting import make_plots
        owners = {'k1': 'A', 'k2': 'A'}
        row = {'mode': 'consistent', 'vnodes_per_node': 2, 'key_count': 2,
            'placement_balance_before': balance({'A': 2}),
            'placement_balance_after': balance({'A': 2, 'B': 0}),
            'reassignment': movement(owners, owners),
            'request_balance': {'uniform_reads': 2, 'additional_hot_reads': 0,
                'before_hot': {'A': 2, 'B': 0}, 'after_hot': {'A': 2, 'B': 0}, 'hot_key_owner': 'A'},
            'join_seconds': {'values': [1.0, 1.001], 'mean': 1.0005}}
        config = {'cluster': {'joining_node': 'B'}, 'experiment': {'keys': 2}}
        for times in ([1.0, 1.001], [0.0, 0.0]):
            sample = deepcopy(row)
            sample['join_seconds'] = {'values': times, 'mean': sum(times)/len(times)}
            with self.subTest(times=times), tempfile.TemporaryDirectory() as tmp, \
                 patch('matplotlib.figure.Figure.savefig', autospec=True) as save:
                make_plots([sample], config, tmp)
                checked = set()
                for call in save.call_args_list:
                    fig, path = call.args[:2]
                    name = Path(path).stem
                    if name not in {'balance', 'node-loads', 'join-time'} or name in checked:
                        continue
                    checked.add(name)
                    ax = fig.axes[0]
                    for collection in ax.collections:
                        for x, y in collection.get_offsets():
                            pixel_x = ax.transData.transform((x, y))[0]
                            self.assertGreaterEqual(pixel_x-ax.bbox.xmin, 6)
                            self.assertGreaterEqual(ax.bbox.xmax-pixel_x, 6)
                    if name == 'join-time':
                        for line in ax.lines:
                            for x, y in zip(*line.get_data()):
                                pixel_x = ax.transData.transform((x, y))[0]
                                self.assertGreaterEqual(pixel_x-ax.bbox.xmin, 6)
                                self.assertGreaterEqual(ax.bbox.xmax-pixel_x, 6)
                self.assertEqual(checked, {'balance', 'node-loads', 'join-time'})


@unittest.skipUnless(importlib.util.find_spec('matplotlib') and importlib.util.find_spec('pymupdf'),
                     'Complete figure checks require requirements-dev.txt.')
class FigureExportTests(unittest.TestCase):
    def test_dominant_node_percentage_labels_do_not_overlap(self):
        from sharedkv.plotting import make_plots
        from tools.check_figures import pdf_findings
        owners = {'k': 'A'}
        row = {'mode': 'consistent', 'vnodes_per_node': 3, 'key_count': 1,
            'placement_balance_before': balance({'A': 1, 'B': 0, 'C': 0}),
            'placement_balance_after': balance({'A': 1, 'B': 0, 'C': 0, 'D': 0}),
            'reassignment': movement(owners, owners),
            'request_balance': {'uniform_reads': 2, 'additional_hot_reads': 0,
                'before_hot': {'A': 2, 'B': 0, 'C': 0, 'D': 0},
                'after_hot': {'A': 2, 'B': 0, 'C': 0, 'D': 0}, 'hot_key_owner': 'A'},
            'join_seconds': {'values': [0.01], 'mean': 0.01}}
        with tempfile.TemporaryDirectory() as tmp:
            make_plots([row], {'experiment': {'keys': 1}}, tmp)
            self.assertEqual(pdf_findings(Path(tmp)/'requests.pdf')['findings'], [])

    def test_real_exports_preserve_metadata_text_and_data_manifest(self):
        from sharedkv.plotting import make_plots
        from sharedkv.study import digest, write_json
        from tools.check_figures import audit
        root = Path(__file__).resolve().parents[1]
        # This saved small fixture exercises exporting, not new collection.
        summary = json.loads((root/'results/example/summary.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = make_plots(summary['rows'], summary['config'], out/'figures')
            write_json(out/'summary.json', summary)
            write_json(out/'figure-manifest.json', {
                'outputs': {p.relative_to(out).as_posix(): digest(p) for p in paths},
                'layouts': {p.relative_to(out).as_posix(): digest(p) for p in (out/'figures').glob('*.layout.json')},
                'summary_sha256': digest(out/'summary.json')})
            result = audit(out)
            self.assertEqual(result['status'], 'passed', result['pdf_figures'])
            self.assertEqual(result['verified_export_hashes'], 18)

    def test_pdf_collision_audit_rejects_an_actual_overlap(self):
        import pymupdf
        from tools.check_figures import pdf_findings
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.pdf'
            with pymupdf.open() as document:
                page = document.new_page()
                page.insert_text((40, 60), 'First label', fontsize=10)
                page.insert_text((42, 60), 'Second label', fontsize=10)
                document.set_metadata({'author': 'Paco'})
                document.save(path)
            self.assertTrue(any('Overlapping text' in item for item in pdf_findings(path)['findings']))


if __name__ == '__main__':
    unittest.main()
