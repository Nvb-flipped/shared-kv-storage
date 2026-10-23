"""Figures for local study runs; all denominators and ranges come from run data."""
from pathlib import Path


def make_plots(rows, config, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    nodes = sorted(rows[0]['placement_balance_after']['key_counts'])
    old_nodes = sorted(rows[0]['placement_balance_before']['key_counts'])
    labels = [r['mode']+(f" V={r['vnodes_per_node']}" if r['mode'] == 'consistent' else '') for r in rows]
    colors = ['#2878a5', '#d98324', '#39856f', '#9b63a3', '#69764b', '#bb5f62']
    markers = ['o', 's', '^', 'D', 'v', 'P']
    outputs = []
    height = max(3.5, 1.8+.38*len(rows))

    def save(fig, name):
        fig.canvas.draw()
        for path in (directory/f'{name}.svg', directory/f'{name}.pdf', directory/f'{name}.png'):
            metadata = {'Creator': 'Paco'} if path.suffix == '.svg' else {'Author': 'Paco'}
            fig.savefig(path, dpi=300, metadata=metadata)
            outputs.append(path)
        plt.close(fig)

    def grid(ax, axis='x'):
        ax.set_axisbelow(True)
        ax.grid(axis=axis, color='#e2e7eb', linewidth=.6)
        ax.spines[['top', 'right']].set_visible(False)

    with plt.rc_context({'font.size': 10, 'font.family': 'sans-serif',
                         'font.sans-serif': ['DejaVu Sans'], 'svg.fonttype': 'none',
                         'pdf.fonttype': 42, 'axes.linewidth': .8, 'legend.frameon': False,
                         'axes.labelcolor': '#243547', 'text.color': '#243547'}):
        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        values = [r['reassignment']['fraction'] for r in rows]
        ax.barh(labels, values, color=[colors[1] if r['mode'] == 'modulo' else colors[0] for r in rows], height=.6)
        for i, (value, row) in enumerate(zip(values, rows)):
            ax.text(min(value+.015, .85), i, f"{value:.1%} ({row['reassignment']['reassigned_key_count']})", va='center', fontsize=9)
        if any(r['mode'] == 'consistent' for r in rows):
            ax.axvline(1/len(nodes), linestyle='--', color='#667788', label='Ideal random-ring mean')
        if any(r['mode'] == 'modulo' for r in rows):
            ax.axvline(len(old_nodes)/len(nodes), linestyle=':', color='#667788', label='Uniform modulo expectation')
        ax.set(xlim=(0, 1.05), xlabel='Fraction of original keys reassigned')
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.invert_yaxis(); grid(ax)
        ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.18), fontsize=8, ncols=2)
        save(fig, 'movement')

        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        y = list(range(len(rows)))
        for stage, offset, marker, color in [('before', -.1, 'o', colors[0]), ('after', .1, 's', colors[1])]:
            ax.scatter([r['placement_balance_'+stage]['cv'] for r in rows], [i+offset for i in y],
                       marker=marker, color=color, label=f'{stage}: {len(old_nodes) if stage == "before" else len(nodes)} nodes')
        max_cv = max(r['placement_balance_'+stage]['cv'] for r in rows for stage in ('before', 'after')) or .1
        ax.set(yticks=y, yticklabels=labels, xlabel='Population CV of physical key counts', xlim=(-.04*max_cv, 1.1*max_cv))
        ax.invert_yaxis(); grid(ax); ax.legend()
        save(fig, 'balance')

        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        for j, node in enumerate(nodes):
            offset = (j-(len(nodes)-1)/2)*.6/max(1, len(nodes))
            ax.scatter([r['placement_balance_after']['key_counts'][node] for r in rows], [i+offset for i in y],
                color=plt.get_cmap('tab20')((j % 20)/19), marker=markers[j % len(markers)], label=node, s=35)
        ax.axvline(config['experiment']['keys']/len(nodes), color='#667788', linestyle=':', label='Equal key counts')
        max_count = max(count for r in rows for count in r['placement_balance_after']['key_counts'].values())
        ax.set(yticks=y, yticklabels=labels, xlabel='Keys per node after join (every physical node shown)', xlim=(-.04*max_count, 1.1*max_count))
        ax.invert_yaxis(); grid(ax)
        ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.18), ncols=min(len(nodes)+1, 7), fontsize=8)
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
        for j, (data, name) in enumerate(zip(series, names)):
            ax.bar([i+(j-1)*.25 for i in range(len(nodes))], [data[n] for n in nodes],
                   width=.23, color=colors[j], hatch=['', '//', '..'][j], label=name)
        ax.set(xticks=range(len(nodes)), xticklabels=nodes, ylim=(0, 1), ylabel='Share of the stated total', xlabel='Physical node',
               title=f"{example['mode']} V={example['vnodes_per_node']}; hot owner {workload['hot_key_owner']}")
        ax.yaxis.set_major_formatter(PercentFormatter(1)); grid(ax, 'y')
        ax.legend(fontsize=8)
        save(fig, 'requests')

        examples = [r for r in rows if r['mode'] == 'modulo'][:1]
        if example not in examples:
            examples.append(example)
        fig, axes = plt.subplots(1, len(examples), squeeze=False,
            figsize=(max(7.2, len(examples)*len(nodes)*.8), max(3.5, len(old_nodes)*.65+1.7)), layout='constrained')
        maximum = max(max(cell.values()) for r in examples for cell in r['reassignment']['matrix_counts'].values())
        for ax, row in zip(axes[0], examples):
            matrix = [[row['reassignment']['matrix_counts'].get(a, {}).get(b, 0) for b in nodes] for a in old_nodes]
            ax.imshow(matrix, cmap='Blues', vmin=0, vmax=maximum, aspect='auto')
            for i in range(len(old_nodes)):
                for j in range(len(nodes)):
                    value = matrix[i][j]
                    ax.text(j, i, f"{value}\n{value/row['key_count']:.1%}", ha='center', va='center',
                            color='white' if value > maximum*.55 else '#243547', fontsize=8)
            ax.set(xticks=range(len(nodes)), xticklabels=nodes, yticks=range(len(old_nodes)), yticklabels=old_nodes,
                   xlabel='New owner', ylabel='Old owner', title=f"{row['mode']} V={row['vnodes_per_node']}")
        save(fig, 'transfers')

        fig, ax = plt.subplots(figsize=(7.2, height), layout='constrained')
        for i, row in enumerate(rows):
            times = row['join_seconds']['values']
            offset = [(j-(len(times)-1)/2)*.5/max(1, len(times)-1) for j in range(len(times))]
            ax.scatter(times, [i+d for d in offset], s=25, color=colors[0])
            ax.plot(row['join_seconds']['mean'], i, marker='D', markerfacecolor='none', color=colors[1], markersize=7)
        max_time = max(t for r in rows for t in r['join_seconds']['values']) or 1e-6
        ax.set(yticks=y, yticklabels=labels, xlabel='Measured join time (s); circles = trials, diamonds = means', xlim=(-.04*max_time, 1.1*max_time))
        ax.invert_yaxis(); grid(ax)
        save(fig, 'join-time')
    return outputs
