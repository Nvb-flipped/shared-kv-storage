"""Optional geometry regression: zero loads and close timing points stay visible."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sharedkv.metrics import balance, movement


@unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Optional Matplotlib is not installed.')
class PlotGeometryTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
