"""Figures for local study runs; all denominators and ranges come from run data."""
from pathlib import Path
import json
from .figure_quality import inspect_layout
from .terminal import COLORS


def make_plots(rows, config, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.ticker import PercentFormatter
    from PIL import Image

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    nodes = sorted(rows[0]['placement_balance_after']['key_counts'])
    old_nodes = sorted(rows[0]['placement_balance_before']['key_counts'])
    labels = [r['mode']+(f" V={r['vnodes_per_node']}" if r['mode'] == 'consistent' else '') for r in rows]
    colors = ['#7BB6D7', '#E6B16D', '#8AC6AF', '#BD9BCE', '#B6C59A', '#D9A0A0']
    edge = '#526979'
    markers = ['o', 's', '^', 'D', 'v', 'P']
    outputs = []
    height = max(3.5, 1.8+.38*len(rows))

    def save(fig, name):
        layout = inspect_layout(fig)
        (directory/f'{name}.layout.json').write_text(json.dumps(layout, indent=2)+'\n', encoding='utf-8', newline='\n')
        exif = Image.Exif()
        exif[315] = 'Paco'
        exif[40093] = 'Paco\0'.encode('utf-16le')
        for path in (directory/f'{name}.svg', directory/f'{name}.pdf', directory/f'{name}.png'):
            metadata = {'Creator': 'Paco'} if path.suffix == '.svg' else {'Author': 'Paco'}
            options = {'pil_kwargs': {'exif': exif.tobytes()}} if path.suffix == '.png' else {}
            fig.savefig(path, dpi=300, facecolor='white', metadata=metadata, **options)
            outputs.append(path)
        plt.close(fig)

    def grid(ax, axis='x'):
        ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False)
        ax.spines[['bottom', 'left']].set_color('#8A969F')
        ax.tick_params(color='#8A969F', width=.6, length=3)

    with plt.rc_context({'font.size': 9, 'font.family': 'sans-serif',
                         'font.sans-serif': ['DejaVu Sans'], 'svg.fonttype': 'none',
                         'pdf.fonttype': 42, 'axes.linewidth': .8, 'legend.frameon': False,
                         'axes.labelcolor': '#243547', 'text.color': '#243547'}):
        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        values = [r['reassignment']['fraction'] for r in rows]
        ax.barh(labels, values, color=[colors[1] if r['mode'] == 'modulo' else colors[0] for r in rows],
                edgecolor=edge, linewidth=.6, height=.55)
        for i, (value, row) in enumerate(zip(values, rows)):
            ax.text(1.03, i, f"{value:.1%} ({row['reassignment']['reassigned_key_count']})", va='center', fontsize=8)
        if any(r['mode'] == 'consistent' for r in rows):
            ax.axvline(1/len(nodes), linestyle='--', color='#667788', label='Ideal random-ring mean')
        if any(r['mode'] == 'modulo' for r in rows):
            ax.axvline(len(old_nodes)/len(nodes), linestyle=':', color='#667788', label='Uniform modulo expectation')
        ax.set(xlim=(0, 1.31), xticks=[0, .25, .5, .75, 1], xlabel='Reassigned keys / original keys')
        ax.spines['bottom'].set_bounds(0, 1)
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.invert_yaxis(); grid(ax)
        ax.legend(loc='lower center', bbox_to_anchor=(.5, 1.02), fontsize=8, ncols=2)
        save(fig, 'movement')

        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        y = list(range(len(rows)))
        for i, row in enumerate(rows):
            ax.plot([row['placement_balance_before']['cv'], row['placement_balance_after']['cv']],
                    [i-.1, i+.1], color='#CCD4DA', linewidth=.8, zorder=0)
        for stage, offset, marker, color in [('before', -.1, 'o', colors[0]), ('after', .1, 's', colors[1])]:
            ax.scatter([r['placement_balance_'+stage]['cv'] for r in rows], [i+offset for i in y],
                       marker=marker, color=color, edgecolor=edge, linewidth=.65, s=35,
                       label=f'{stage}: {len(old_nodes) if stage == "before" else len(nodes)} nodes')
        max_cv = max(r['placement_balance_'+stage]['cv'] for r in rows for stage in ('before', 'after')) or .1
        ax.set(yticks=y, yticklabels=labels, xlabel='Population CV of physical key counts', xlim=(-.07*max_cv, 1.12*max_cv))
        ax.invert_yaxis(); grid(ax)
        ax.legend(loc='lower center', bbox_to_anchor=(.5, 1.02), ncols=2, fontsize=8)
        save(fig, 'balance')

        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        # These boxes describe the finite node population, not timing uncertainty.
        ax.boxplot([list(r['placement_balance_after']['key_counts'].values()) for r in rows],
                   positions=y, orientation='horizontal', widths=.55, whis=(0, 100), showfliers=False,
                   patch_artist=True, manage_ticks=False,
                   boxprops={'facecolor': '#EEF3F6', 'edgecolor': '#A5AFB8', 'linewidth': .8},
                   medianprops={'color': '#7E8E99', 'linewidth': 1},
                   whiskerprops={'color': '#A5AFB8', 'linewidth': .8},
                   capprops={'color': '#A5AFB8', 'linewidth': .8})
        for j, node in enumerate(nodes):
            offset = (j-(len(nodes)-1)/2)*.6/max(1, len(nodes))
            ax.scatter([r['placement_balance_after']['key_counts'][node] for r in rows], [i+offset for i in y],
                color=COLORS[node], edgecolor=edge, linewidth=.65,
                marker=markers[j % len(markers)] if len(nodes) <= 8 else chr(36)+node+chr(36), label=node, s=35, zorder=3)
        ax.axvline(config['experiment']['keys']/len(nodes), color='#667788', linestyle=':', label='Equal key counts')
        max_count = max(count for r in rows for count in r['placement_balance_after']['key_counts'].values())
        ax.set(yticks=y, yticklabels=labels, xlabel='Keys per node after join (every physical node shown)', xlim=(-.07*max_count, 1.12*max_count))
        ax.invert_yaxis(); grid(ax)
        ax.legend(loc='lower center', bbox_to_anchor=(.5, 1.02), ncols=min(len(nodes)+1, 7), fontsize=8)
        save(fig, 'node-loads')

        consistent = [r for r in rows if r['mode'] == 'consistent']
        example = next((r for r in consistent if r['vnodes_per_node'] == 16), (consistent or rows)[0])
        workload = example['request_balance']
        background = workload['uniform_reads']
        total = background+workload['additional_hot_reads']
        series = [example['placement_balance_after']['shares'],
                  {n: c/background for n, c in workload['before_hot'].items()},
                  {n: c/total for n, c in workload['after_hot'].items()}]
        fig, ax = plt.subplots(figsize=(max(7.2, .45*len(nodes)), 4.5), layout='constrained')
        names = [f"Keys ({config['experiment']['keys']})", f'Uniform reads ({background})', f'Uniform + hot ({total})']
        from matplotlib.lines import Line2D
        request_markers = ('o', 's', '^')
        for j, (data, name) in enumerate(zip(series, names)):
            positions = [i+(j-1)*.25 for i in range(len(nodes))]
            ax.bar(positions, [data[n] for n in nodes],
                   width=.23, color=colors[j], edgecolor=edge, linewidth=.6, label=name)
            ax.scatter(positions, [data[n] for n in nodes], marker=request_markers[j], s=27,
                       facecolor=colors[j], edgecolor=edge, linewidth=.7, zorder=3, clip_on=False)
            if len(nodes) <= 6:
                for x, node in zip(positions, nodes):
                    label = f'{data[node]:.1%}'.replace('.0%', '%')
                    ax.text(x, data[node]+.025, label, ha='center', va='bottom', fontsize=8)
        ax.set(xticks=range(len(nodes)), xticklabels=nodes, ylim=(0, 1.13), yticks=[0, .25, .5, .75, 1], ylabel='Share of the stated total', xlabel='Physical node',
               title=f"{example['mode']} V={example['vnodes_per_node']}; hot owner {workload['hot_key_owner']}")
        ax.yaxis.set_major_formatter(PercentFormatter(1)); grid(ax, 'y')
        ax.legend(handles=[Line2D([], [], linestyle='none', marker=request_markers[j],
            markerfacecolor=colors[j], markeredgecolor=edge, label=name) for j, name in enumerate(names)],
            fontsize=8, loc='upper right')
        save(fig, 'requests')

        examples = [r for r in rows if r['mode'] == 'modulo'][:1]
        if example not in examples:
            examples.append(example)
        fig, axes = plt.subplots(1, len(examples), squeeze=False,
            figsize=(max(7.2, len(examples)*len(nodes)*.8), max(3.5, len(old_nodes)*.65+1.7)), layout='constrained')
        maximum = max(max(cell.values()) for r in examples for cell in r['reassignment']['matrix_counts'].values())
        cmap = LinearSegmentedColormap.from_list('light_transfer', ['#FAFCFD', '#DFEDF4', '#B8D7E7', '#8DBBD4'])
        for panel, (ax, row) in enumerate(zip(axes[0], examples)):
            matrix = [[row['reassignment']['matrix_counts'].get(a, {}).get(b, 0) for b in nodes] for a in old_nodes]
            ax.imshow(matrix, cmap=cmap, vmin=0, vmax=maximum or 1, aspect='auto')
            for i in range(len(old_nodes)):
                for j in range(len(nodes)):
                    value = matrix[i][j]
                    ax.text(j, i, f"{value}\n{value/row['key_count']:.1%}", ha='center', va='center',
                            color='#263746', fontsize=8)
            ax.set(xticks=range(len(nodes)), xticklabels=nodes, yticks=range(len(old_nodes)), yticklabels=old_nodes,
                   xlabel='New owner', ylabel='Old owner', title=f"{chr(97+panel)}  {row['mode']} V={row['vnodes_per_node']}")
        fig.supxlabel(f'Cell labels: count and percentage of all {example["key_count"]:,} original keys', fontsize=8)
        save(fig, 'transfers')

        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        for i, row in enumerate(rows):
            times = row['join_seconds']['values']
            offset = [(j-(len(times)-1)/2)*.5/max(1, len(times)-1) for j in range(len(times))]
            ax.scatter(times, [i+d for d in offset], s=27, color=colors[0], edgecolor=edge, linewidth=.65,
                       label='Fresh-process trial' if i == 0 else None)
            ax.plot(row['join_seconds']['mean'], i, marker='D', markerfacecolor='none',
                    color='#A97538', markersize=7, label='Mean' if i == 0 else None)
        max_time = max(t for r in rows for t in r['join_seconds']['values']) or 1e-6
        ax.set(yticks=y, yticklabels=labels, xlabel='Measured join time (s)', xlim=(-.07*max_time, 1.12*max_time))
        ax.invert_yaxis(); grid(ax)
        ax.legend(loc='lower center', bbox_to_anchor=(.5, 1.02), ncols=2, fontsize=8)
        save(fig, 'join-time')
    return outputs
