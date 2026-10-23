"""Build current tables and shared documentation/Beamer plots from real trials."""
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib
from tools.figures import make_figures
from tools.doc_navigation import update_page


def main():
    out = ROOT/'results/framework'; config = json.loads((ROOT/'configs/framework-experiment.json').read_text())
    rows = []
    for mode, v in [('modulo', 1), *[('consistent', v) for v in config['vnodes']]]:
        trials = [json.loads((out/f'{mode}-v{v}-t{t}.json').read_text()) for t in range(1, 4)]
        row = {k: val for k, val in trials[0].items() if k not in ('owners_before', 'owners_after', 'physical_inventory')}
        for trial in trials:
            assert trial['verification']['failures'] == trial['verification']['physical_failures'] == []
            assert trial['placement_balance_after'] == row['placement_balance_after']
        times = [t['migration']['seconds'] for t in trials]
        row['join_seconds'] = {'mean': statistics.mean(times), 'sample_sd': statistics.stdev(times), 'minimum': min(times), 'maximum': max(times)}
        rows.append(row)
    summary = {'author': 'Paco', 'config': config, 'rows': rows}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    with (out/'summary.csv').open('w', newline='') as stream:
        writer = csv.writer(stream); writer.writerow(['mode', 'V', 'ratio_before', 'ratio_after', 'CV_after', 'moved', 'moved_fraction', 'mean_join_seconds', 'sample_sd_seconds', 'estimated_item_bytes'])
        for r in rows: writer.writerow([r['mode'], r['vnodes_per_node'], r['placement_balance_before']['max_min_ratio'], r['placement_balance_after']['max_min_ratio'], r['placement_balance_after']['cv'], r['reassignment']['reassigned_key_count'], r['reassignment']['fraction'], r['join_seconds']['mean'], r['join_seconds']['sample_sd'], r['migration']['estimated_item_bytes']])
    outputs = make_figures(rows)
    def label(r): return 'Modulo' if r['mode'] == 'modulo' else 'Consistent V='+str(r['vnodes_per_node'])
    def counts(r, stage): return '/'.join(str(n) for n in r['placement_balance_'+stage]['key_counts'].values())
    comparison = ['| Setting | Before A/B/C | After A/B/C/D | Max/min after | CV after | Reassigned | Value failures |', '|---|---|---|---:|---:|---:|---:|']
    for r in rows:
        comparison.append(f"| {label(r)} | {counts(r, 'before')} | {counts(r, 'after')} | {r['placement_balance_after']['max_min_ratio']:.3f} | {r['placement_balance_after']['cv']:.3f} | {r['reassignment']['reassigned_key_count']} ({r['reassignment']['fraction']:.1%}) | 0 |")
    readme = ROOT/'README.md'
    text = readme.read_text()
    text = re.sub(r'<!-- comparison:start -->.*?<!-- comparison:end -->', '<!-- comparison:start -->\n'+'\n'.join(comparison)+'\n<!-- comparison:end -->', text, flags=re.S)
    readme.write_text(text)
    lines = ['# Measured framework results', '', 'Thirty fresh WSL clusters: modulo and nine consistent-hash settings, three runs each. The same 1,000 key/value pairs and uniform-read sequence are used throughout. Order is randomized within each round using seed 3010. Placement repeats are deterministic; timing repeats are not independent token-layout samples.', '', *comparison, '',
        '![Reassigned keys](../figures/movement.svg)', '', '![Physical balance](../figures/balance.svg)', '',
        'More V does not guarantee improvement at every step for these fixed IDs. The random-ring 25% reference averages over equal-capacity random layouts, not this particular ring.', '',
        '![All four node counts](../figures/node-loads.svg)', '',
        'The L01 box view contains four physical node counts at each V, with every node marked. The dotted reference is 250 keys per node. It is a finite population description, not uncertainty over machines or token layouts.', '',
        '![Key shares](../figures/key-shares.svg)', '', '## Same keys, additional hot traffic', '',
        '| Setting | Hot owner | Uniform A/B/C/D (1,000 reads) | After extra hot reads (1,500 reads) | Request max/min after |', '|---|---|---|---|---:|']
    for r in rows:
        w = r['request_balance']; before = '/'.join(str(n) for n in w['before_hot'].values()); after = '/'.join(str(n) for n in w['after_hot'].values())
        lines.append(f"| {label(r)} | {w['hot_key_owner']} | {before} | {after} | {w['ratio_after_hot']:.3f} |")
    lines += ['', 'All 500 additional requests reach the hot key’s owner, and key counts remain unchanged. Counters reset after loading, migration and exhaustive verification; inventory and migration do not enter client counters.', '',
        '![Request shares](../figures/requests.svg)', '', '![Transfer matrices](../figures/transfers.svg)', '',
        'Matrix rows are old owners and columns are new owners. Cell percentages divide by all 1,000 original keys. Modulo may move keys between old nodes; a fixed-token consistent join sends every changed key to D.', '',
        '## Membership cost and verification', '', '| Setting | Acknowledged / verified | Join mean ± sample SD (s) | Observed range (s) | Estimated serialized item bytes |', '|---|---:|---:|---:|---:|']
    for r in rows:
        t = r['join_seconds']; m = r['migration']
        lines.append(f"| {label(r)} | {m['migrated']} / {m['verified']} | {t['mean']:.3f} ± {t['sample_sd']:.3f} | {t['minimum']:.3f}–{t['maximum']:.3f} | {m['estimated_item_bytes']:,} |")
    lines += ['', 'Counts and elapsed seconds are measured. Item bytes are calculated from UTF-8 JSON logical items, not captured network traffic. The timer includes preparation through source cleanup and excludes the independent exhaustive read afterward. No artificial demonstration pause is used. Standard deviations describe three local runs, not confidence intervals or WAN performance.', '',
        'Every run verifies all 1,000 original values and checks one physical host matching the router’s owner. Reassigned counts equal acknowledged and verified destination counts. During migration, the separate rehearsal demonstrates readable Gets and rejected Puts. No replication result is claimed.', '',
        '![Every join timing](../figures/join-cost.svg)', '', 'Each circle is one fresh run; the diamond marks its mean. All thirty timings are shown. Repeated runs use the same deterministic layout.', '', '## Reproduce and trace', '', '`bash tools/reproduce.sh` regenerates the evidence. Raw cases, dataset/request digests, process PIDs, randomized schedule and source hashes are in `results/framework/`. The [API reference](api.md), [math definitions](metrics.md) and [scope map](scope.md) explain contracts and assumptions. Legacy results are excluded from the active tree and retained only in local Git history.', '']
    (ROOT/'docs/results.md').write_text('\n'.join(lines))
    (out/'figure-manifest.json').write_text(json.dumps({'author': 'Paco', 'backend': 'Matplotlib '+matplotlib.__version__, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'summary_sha256': hashlib.sha256((out/'summary.json').read_bytes()).hexdigest(), 'plot_source_sha256': hashlib.sha256((ROOT/'tools/figures.py').read_bytes()).hexdigest(), 'outputs': outputs}, indent=2)+'\n')
    update_page(ROOT/'docs/results.md')
    print('Generated comparison table, results and seven shared figure sets.')


if __name__ == '__main__': main()
