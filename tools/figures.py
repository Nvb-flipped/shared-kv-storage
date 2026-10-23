"""Shared documentation/Beamer plots from the recorded framework trials."""
import json
import os
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib.ticker import PercentFormatter
from tools.author_metadata import apply, inspect

ROOT = Path(__file__).resolve().parents[1]
INK, BLUE, ORANGE, GRID = '#253449', '#4389ad', '#b77838', '#e1e7ed'
FILLS = ['#c5e2f2', '#f8dfa3', '#c9eadc', '#e0d9f1']
MARKERS = ['o', 's', '^', 'D']


def make_figures(rows):
    """No sampling, exclusions, smoothing or new benchmark runs."""
    outputs = []
    qa = ROOT/'results/framework/figure-qa'; qa.mkdir(parents=True, exist_ok=True)
    directory = ROOT/'figures'; directory.mkdir(exist_ok=True)
    optional = os.environ.get('NATURE_FIGURE_SCRIPTS')
    if optional: sys.path.insert(0, optional)
    with plt.rc_context({'font.family': 'sans-serif', 'font.sans-serif': ['DejaVu Sans', 'Arial'], 'font.size': 17,
            'axes.labelsize': 17, 'axes.titlesize': 17, 'xtick.labelsize': 15, 'ytick.labelsize': 15, 'text.color': INK,
            'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK,
            'axes.edgecolor': '#8b99a6', 'axes.linewidth': .7,
            'axes.spines.top': False, 'axes.spines.right': False,
            'pdf.fonttype': 42, 'svg.fonttype': 'none', 'figure.facecolor': 'white',
            'legend.frameon': False, 'legend.fontsize': 14}):
        def save(fig, name):
            fig.canvas.draw()
            if optional:
                from audit_panel_alignment import require_matplotlib_panel_alignment
                require_matplotlib_panel_alignment(fig, json_out=qa/(name+'.alignment.json'),
                    tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True)
            else:
                axes = [a for a in fig.axes if a.get_visible()]
                if len(axes) == 2:
                    a, b = [a.get_position() for a in axes]
                    assert abs(a.y0-b.y0)*fig.get_figheight()*72 < 1.5
                    assert abs(a.width-b.width)*fig.get_figwidth()*72 < 1.5
                (qa/(name+'.alignment.json')).write_text(json.dumps({'status': 'local geometry checked',
                    'external_skill_audit': 'not requested', 'axes': len(axes)}, indent=2)+'\n')
            for suffix in ('.svg', '.pdf', '.png'):
                path = directory/(name+suffix)
                fig.savefig(path, dpi=300, metadata={'Creator': 'Paco'} if suffix == '.svg' else {'Author': 'Paco'})
                apply(path); inspect(path); outputs.append(path.relative_to(ROOT).as_posix())
            plt.close(fig)

        def horizontal(ax):
            ax.set_axisbelow(True); ax.grid(axis='x', color=GRID, linewidth=.7)
            ax.spines['left'].set_visible(False); ax.tick_params(axis='y', length=0, pad=10)

        labels = ['Modulo']+['V='+str(r['vnodes_per_node']) for r in rows[1:]]
        rings = rows[1:]; x = list(range(len(rings)))
        fig, ax = plt.subplots(figsize=(9.4, 4.8)); fig.subplots_adjust(left=.14, right=.78, bottom=.16, top=.91)
        for i, r in enumerate(rows):
            value = r['reassignment']['fraction']; color = ORANGE if i == 0 else BLUE
            ax.hlines(i, 0, value, color=FILLS[1] if i == 0 else FILLS[0], linewidth=9)
            ax.plot(value, i, marker='s' if i == 0 else 'o', color=color, markersize=7)
            ax.text(1.025, i, f'{value:.1%}  ({r["reassignment"]["reassigned_key_count"]})', transform=ax.get_yaxis_transform(), va='center', fontsize=15)
        ax.axvline(.25, color='#99a6b1', linewidth=1, linestyle='--')
        ax.axvline(.75, color='#99a6b1', linewidth=1, linestyle=':')
        ax.text(.25, 1.035, '25% ring model', transform=ax.get_xaxis_transform(), ha='center', fontsize=13)
        ax.text(.75, 1.035, '75% modulo model', transform=ax.get_xaxis_transform(), ha='center', fontsize=13)
        ax.set(yticks=range(len(rows)), yticklabels=labels, xlim=(0, 1.02), xlabel='Original keys reassigned (%)')
        ax.invert_yaxis(); ax.xaxis.set_major_formatter(PercentFormatter(1)); horizontal(ax); save(fig, 'movement')

        fig, ax = plt.subplots(figsize=(9.4, 4.5)); fig.subplots_adjust(left=.10, right=.96, bottom=.19, top=.84)
        for stage, marker, color, style, name in [('before', 'o', BLUE, '--', 'Before join: 3 nodes'), ('after', 's', ORANGE, '-', 'After join: 4 nodes')]:
            ax.plot(x, [r['placement_balance_'+stage]['cv'] for r in rings], marker=marker,
                    color=color, linestyle=style, linewidth=1.7, markersize=7, label=name)
        ax.set(xticks=x, xticklabels=[str(r['vnodes_per_node']) for r in rings], ylim=(0, .75),
               ylabel='Relative spread (CV)', xlabel='Tokens per physical node (V; categorical settings)')
        ax.set_axisbelow(True); ax.grid(axis='y', color=GRID, linewidth=.7)
        fig.legend(loc='upper center', bbox_to_anchor=(.53, .99), ncols=2); save(fig, 'balance')

        fig, ax = plt.subplots(figsize=(9.4, 4.5)); fig.subplots_adjust(left=.10, right=.96, bottom=.18, top=.83)
        loads = [list(r['placement_balance_after']['key_counts'].values()) for r in rings]
        boxes = ax.boxplot(loads, positions=x, widths=.55, patch_artist=True, showfliers=False,
            medianprops={'color': INK, 'linewidth': 1.5}, boxprops={'edgecolor': '#8296a7'},
            whiskerprops={'color': '#8296a7'}, capprops={'color': '#8296a7'})
        for box in boxes['boxes']: box.set_facecolor('#f0f5f9')
        for j, node in enumerate('ABCD'):
            ax.scatter([i-.15+j*.10 for i in x], [r['placement_balance_after']['key_counts'][node] for r in rings],
                s=48, marker=MARKERS[j], facecolor=FILLS[j], edgecolor=INK, linewidth=.9, label=node, zorder=4)
        ax.axhline(250, color='#8c9ca8', linestyle=':', linewidth=1)
        ax.set(xticks=x, xticklabels=[str(r['vnodes_per_node']) for r in rings], ylim=(0, 520),
            ylabel='Keys per node after join', xlabel='Tokens per physical node (V)')
        fig.legend(loc='upper center', bbox_to_anchor=(.54, .99), ncols=4, title='Physical node')
        ax.set_axisbelow(True); ax.grid(axis='y', color=GRID, linewidth=.7); save(fig, 'node-loads')

        fig, ax = plt.subplots(figsize=(9.4, 5)); fig.subplots_adjust(left=.14, right=.94, bottom=.14, top=.88)
        left = [0.]*len(rows)
        for j, node in enumerate('ABCD'):
            shares = [r['placement_balance_after']['shares'][node] for r in rows]
            bars = ax.barh(range(len(rows)), shares, left=left, height=.72, color=FILLS[j], edgecolor='white', linewidth=1, label=node)
            for bar, share, start in zip(bars, shares, left):
                ax.text(start+share/2, bar.get_y()+bar.get_height()/2, f'{share:.1%}', ha='center', va='center', fontsize=12)
            left = [a+b for a, b in zip(left, shares)]
        ax.set(yticks=range(len(rows)), yticklabels=labels, xlim=(0, 1), xlabel='All stored keys (%)')
        ax.invert_yaxis(); ax.xaxis.set_major_formatter(PercentFormatter(1)); ax.tick_params(axis='y', length=0)
        fig.legend(loc='upper center', bbox_to_anchor=(.54, 1), ncols=4, title='Physical node; left-to-right order is A, B, C, D')
        save(fig, 'key-shares')

        example = next(r for r in rings if r['vnodes_per_node'] == 16)
        fig, ax = plt.subplots(figsize=(9.4, 5)); fig.subplots_adjust(left=.10, right=.86, bottom=.14, top=.75)
        distributions = [example['placement_balance_after']['shares'],
            {n: c/1000 for n, c in example['request_balance']['before_hot'].items()},
            {n: c/1500 for n, c in example['request_balance']['after_hot'].items()}]
        names = ['1,000 keys', '1,000 uniform reads', '1,500 reads: uniform + hot']
        for j, (data, label) in enumerate(zip(distributions, names)):
            yy = [i+(j-1)*.28 for i in range(4)]
            ax.barh(yy, [data[n] for n in 'ABCD'], height=.20, color=FILLS[j], edgecolor='#8296a7', linewidth=.55)
            ax.scatter([data[n] for n in 'ABCD'], yy, marker=MARKERS[j], color=FILLS[j], edgecolor=INK, linewidth=.8, s=32, label=label, zorder=3)
            for i, n in enumerate('ABCD'): ax.text(1.025, yy[i], f'{data[n]:.1%}', transform=ax.get_yaxis_transform(), va='center', fontsize=13)
        ax.axvline(.25, color='#9ca8b2', linestyle=':', linewidth=.8)
        ax.set(yticks=range(4), yticklabels=list('ABCD'), xlim=(0, .65), xlabel='Share of the stated total (%)')
        ax.invert_yaxis(); ax.xaxis.set_major_formatter(PercentFormatter(1)); horizontal(ax)
        fig.legend(loc='upper center', bbox_to_anchor=(.53, 1), ncols=1)
        save(fig, 'requests')

        fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.5)); fig.subplots_adjust(left=.07, right=.98, bottom=.17, top=.88, wspace=.27)
        maximum = max(max(row.values()) for r in (rows[0], example) for row in r['reassignment']['matrix_counts'].values())
        cmap = LinearSegmentedColormap.from_list('light_transfer', ['#ffffff', '#f8d5b4'])
        for ax, row, label in zip(axes, (rows[0], example), ('Modulo', 'Consistent V=16')):
            matrix = [[row['reassignment']['matrix_counts'][a].get(b, 0) for b in 'ABCD'] for a in 'ABC']
            ax.imshow(matrix, vmin=0, vmax=maximum, cmap=cmap, aspect='equal')
            for i in range(3):
                for j in range(4):
                    value = matrix[i][j]; ax.text(j, i, f'{value}\n{value/1000:.1%}', ha='center', va='center', fontsize=14)
                    if i == j: ax.add_patch(Rectangle((j-.5, i-.5), 1, 1, facecolor='none', edgecolor='#7e91a1', linewidth=1.3))
            ax.set(xticks=range(4), xticklabels=list('ABCD'), yticks=range(3), yticklabels=list('ABC'), xlabel='New owner', ylabel='Old owner')
            ax.set_title(label, pad=12); ax.tick_params(length=0)
        save(fig, 'transfers')

        fig, ax = plt.subplots(figsize=(9.4, 4.8)); fig.subplots_adjust(left=.14, right=.82, bottom=.16, top=.88)
        for i, row in enumerate(rows):
            v = row['vnodes_per_node']; mode = row['mode']
            times = [json.loads((ROOT/f'results/framework/{mode}-v{v}-t{trial}.json').read_text())['migration']['seconds'] for trial in (1, 2, 3)]
            ax.hlines(i, min(times), max(times), color='#a6b6c4', linewidth=2)
            ax.scatter(times, [i-.15, i, i+.15], s=24, facecolor=FILLS[0], edgecolor=BLUE, linewidth=.8)
            mean = row['join_seconds']['mean']; ax.plot(mean, i, marker='D', markersize=5, color=ORANGE)
            ax.text(1.025, i, f'{mean:.3f}', transform=ax.get_yaxis_transform(), va='center', fontsize=15)
        ax.set(yticks=range(len(rows)), yticklabels=labels, xlim=(0, 3.1), xlabel='Measured join time (seconds)')
        ax.invert_yaxis(); horizontal(ax)
        fig.text(.5, .965, 'Three fresh runs per setting; diamond and numeric label = mean', ha='center', fontsize=13)
        save(fig, 'join-cost')
    return outputs
