"""Validate a completed study and create descriptive tables and optional plots."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

from .config import ConfigError, section, ClusterConfig, ExperimentConfig
from .metrics import balance, movement
from .study import digest, schedule_for, source_hashes, write_json
from .transport import decode_json


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    try:
        data = decode_json(path.read_text(encoding='utf-8'))
    except RecursionError as exc:
        raise ValueError(f'{path.name}: JSON nesting is too deep.') from exc
    require(isinstance(data, dict), f'{path.name}: expected a JSON object.')
    return data


def validate_trial(row, case, cluster, experiment):
    """Recompute observable invariants independently of report formatting."""
    from .experiment import dataset
    require((row['mode'], row['vnodes_per_node'], row['trial']) ==
            (case['mode'], case['vnodes'], case['trial']), 'Trial identity differs from schedule.')
    require(row['owned_children_stopped'] is True, 'A trial did not stop its child processes.')
    require(set(row['pids']) == {*cluster.initial_nodes, cluster.joining_node, 'router'} and
            len(set(row['pids'].values())) == len(cluster.initial_nodes)+2 and
            all(type(pid) is int and pid > 0 for pid in row['pids'].values()), 'Unexpected process count or identities.')
    require(row['key_count'] == experiment.keys, 'Unexpected key count.')
    records = dataset(experiment.keys)
    require(row['dataset_sha256'] == hashlib.sha256(json.dumps(records, ensure_ascii=False).encode()).hexdigest(), 'Dataset digest differs.')
    rng = random.Random(experiment.seed)
    keys = list(records)
    sequence = [rng.choice(keys) for _ in range(experiment.uniform_reads)]
    require(row['uniform_sequence_sha256'] == hashlib.sha256(json.dumps(sequence).encode()).hexdigest(), 'Read sequence digest differs.')
    require(set(row['owners_before']) == set(row['owners_after']) == set(records), 'Owner map keys differ.')
    before_nodes = set(cluster.initial_nodes)
    after_nodes = before_nodes | {cluster.joining_node}
    for stage, nodes in [('before', before_nodes), ('after', after_nodes)]:
        owners = row['owners_'+stage]
        require(set(owners.values()) <= nodes, 'Unexpected physical owner.')
        counts = dict.fromkeys(sorted(nodes), 0)
        counts.update(Counter(owners.values()))
        require(row['placement_balance_'+stage] == balance(counts), 'Balance does not match owner map.')
    require(row['reassignment'] == movement(row['owners_before'], row['owners_after']), 'Transfer matrix differs from owner changes.')
    changed = {k for k in records if row['owners_before'][k] != row['owners_after'][k]}
    migration = row['migration']
    require(len(changed) == migration['migrated'] == migration['verified'] == migration['reassigned_key_count'], 'Migration counts differ.')
    require(set(migration['reassigned_keys']) == changed, 'Acknowledged keys differ.')
    byte_count = sum(len(json.dumps({'key': k, 'value': records[k]}, ensure_ascii=False).encode()) for k in changed)
    require(migration['estimated_item_bytes'] == byte_count, 'Logical item-size estimate differs.')
    require(type(migration['seconds']) in (float, int) and math.isfinite(migration['seconds']) and migration['seconds'] >= 0, 'Invalid join time.')
    verify = row['verification']
    require(verify['checked'] == experiment.keys and not verify['failures'] and not verify['physical_failures'], 'Value verification failed.')
    inventory = row['physical_inventory']['keys']
    require(len(inventory) == experiment.keys and {r['key'] for r in inventory} == set(records), 'Physical inventory differs.')
    require(all(r['stored_on'] == [r['owner']] and r['owner'] == row['owners_after'][r['key']] for r in inventory), 'Incorrect physical ownership.')
    if row['mode'] == 'consistent':
        require(all(row['owners_after'][k] == cluster.joining_node for k in changed), 'A consistent join moved keys among old nodes.')
        old_tokens = row['ring_before']['tokens']
        new_tokens = row['ring_after']['tokens']
        require(len(new_tokens) == len(after_nodes)*case['vnodes'], 'Incorrect token count.')
        require([t for t in new_tokens if t['node'] != cluster.joining_node] == old_tokens, 'Old tokens changed.')
    workload = row['request_balance']
    require(workload['uniform_reads'] == experiment.uniform_reads and workload['additional_hot_reads'] == experiment.additional_hot_reads, 'Workload settings differ.')
    require(set(workload['before_hot']) == set(workload['after_hot']) == after_nodes, 'Workload nodes differ.')
    require(sum(workload['before_hot'].values()) == experiment.uniform_reads, 'Background request total differs.')
    expected_reads = dict.fromkeys(sorted(after_nodes), 0)
    expected_reads.update(Counter(row['owners_after'][k] for k in sequence))
    require(workload['before_hot'] == expected_reads, 'Background routing counters differ from the recorded read sequence.')
    hot = workload['hot_key_owner']
    require(workload['hot_key'] == next(iter(records)), 'Hot key differs from the first dataset key.')
    require(hot == row['owners_after'][workload['hot_key']], 'Hot owner differs.')
    require(all(workload['after_hot'][n]-workload['before_hot'][n] ==
                (experiment.additional_hot_reads if n == hot else 0) for n in after_nodes), 'Hot requests were not isolated.')
    require(workload['ratio_after_hot'] == balance(workload['after_hot'])['max_min_ratio'], 'Request ratio differs.')


def load_run(directory, require_current=False):
    try:
        return _load_run(Path(directory), require_current)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as exc:
        raise ValueError(f'Malformed study evidence ({type(exc).__name__}): {exc}') from exc


def _load_run(directory, require_current):
    directory = Path(directory)
    manifest = read_json(directory/'environment.json')
    require(manifest['schema_version'] == 1 and manifest['status'] == 'complete', 'Study is incomplete or uses an unsupported schema.')
    cluster = section(ClusterConfig, manifest['config']['cluster'], 'cluster')
    experiment = section(ExperimentConfig, manifest['config']['experiment'], 'experiment')
    expected = schedule_for(experiment)
    schedule = manifest['schedule']
    # The actual order is evidence. Do not require another Python version to
    # reproduce random.shuffle's implementation to analyze a recorded run.
    identity = lambda row: (row['trial'], row['mode'], row['vnodes'], row['file'])
    require(sorted(map(identity, schedule)) == sorted(map(identity, expected)), 'Schedule does not match the effective configuration.')
    require([r['trial'] for r in schedule] == sorted(r['trial'] for r in schedule), 'Trial rounds are interleaved.')
    completed = manifest['completed']
    require([r['file'] for r in completed] == [r['file'] for r in schedule], 'Missing, duplicate or reordered trial receipts.')
    require({p.name for p in directory.glob('*-t*.json')} == {r['file'] for r in schedule}, 'Missing or unexpected trial files.')
    rows = []
    for case, receipt in zip(schedule, completed):
        path = directory/case['file']
        require(digest(path) == receipt['sha256'], f"Trial digest differs: {case['file']}")
        row = read_json(path)
        validate_trial(row, case, cluster, experiment)
        rows.append(row)
    current = manifest['source_sha256'] == source_hashes()
    require(not require_current or current, 'Run sources differ from this checkout; collect a new run.')
    return manifest, rows, current


def summarize(manifest, trials):
    settings = section(ExperimentConfig, manifest['config']['experiment'], 'experiment')
    rows = []
    for mode, v in settings.cases():
        group = sorted((r for r in trials if (r['mode'], r['vnodes_per_node']) == (mode, v)), key=lambda r: r['trial'])
        first = group[0]
        for item in group[1:]:
            require(item['owners_before'] == first['owners_before'] and item['owners_after'] == first['owners_after'], 'A supposedly fixed layout changed between repetitions.')
        times = [r['migration']['seconds'] for r in group]
        rows.append({k: first[k] for k in ('mode', 'vnodes_per_node', 'key_count',
            'placement_balance_before', 'placement_balance_after', 'request_balance', 'reassignment')})
        rows[-1]['join_seconds'] = dict(values=times, mean=statistics.mean(times),
            sample_sd=statistics.stdev(times) if len(times) > 1 else None, minimum=min(times), maximum=max(times))
        rows[-1]['estimated_item_bytes'] = first['migration']['estimated_item_bytes']
    return rows


def display(value, digits=3):
    return 'n/a' if value is None else f'{value:.{digits}f}'


def build_report(directory, plots=False, require_current=False):
    directory = Path(directory)
    manifest, trials, current = load_run(directory, require_current)
    rows = summarize(manifest, trials)
    cluster = manifest['config']['cluster']
    experiment = manifest['config']['experiment']
    n = len(cluster['initial_nodes'])
    write_json(directory/'summary.json', {'schema_version': 1, 'config': manifest['config'],
        'current_sources_match': current, 'trial_count': len(trials), 'rows': rows})
    with (directory/'summary.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['mode', 'vnodes', 'keys', 'trials', 'CV_before', 'CV_after', 'max_min_after', 'moved_fraction', 'join_mean_seconds', 'join_sample_sd_seconds', 'join_min_seconds', 'join_max_seconds', 'estimated_item_bytes'])
        for row in rows:
            writer.writerow([row['mode'], row['vnodes_per_node'], row['key_count'], len(row['join_seconds']['values']),
                row['placement_balance_before']['cv'], row['placement_balance_after']['cv'],
                row['placement_balance_after']['max_min_ratio'], row['reassignment']['fraction'],
                row['join_seconds']['mean'], row['join_seconds']['sample_sd'], row['join_seconds']['minimum'], row['join_seconds']['maximum'], row['estimated_item_bytes']])
    lines = ['# Local study results', '',
        f"{len(trials)} fresh-process trials; {experiment['keys']} {'key' if experiment['keys'] == 1 else 'keys'}; {n} initial nodes and one join to {cluster['joining_node']}.", '',
        'Question: how do placement policy and token count affect movement, key balance, and concentration of reads?', '',
        '| Policy | V | CV before | CV after | Max/min after | Moved | Join mean (s) | Sample SD (s) | Min–max (s) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        timing = row['join_seconds']
        lines.append(f"| {row['mode']} | {row['vnodes_per_node']} | {row['placement_balance_before']['cv']:.3f} | "
            f"{row['placement_balance_after']['cv']:.3f} | {display(row['placement_balance_after']['max_min_ratio'])} | "
            f"{row['reassignment']['fraction']:.1%} | {timing['mean']:.3f} | {display(timing['sample_sd'])} | {timing['minimum']:.3f}–{timing['maximum']:.3f} |")
    label = lambda row: row['mode']+f" V={row['vnodes_per_node']}"
    smallest_cv = min(r['placement_balance_after']['cv'] for r in rows)
    best = ', '.join(label(r) for r in rows if r['placement_balance_after']['cv'] == smallest_cv)
    lines += ['', '## Observed comparisons', '',
        f"The smallest post-join key-count CV among the exercised settings is {smallest_cv:.3f} ({best}). This ranks these fixed layouts only; movement and timing remain separate tradeoffs."]
    consistent = [r for r in rows if r['mode'] == 'consistent']
    modulo = next((r for r in rows if r['mode'] == 'modulo'), None)
    if consistent:
        fractions = [r['reassignment']['fraction'] for r in consistent]
        if max(fractions) == 0:
            lines += ['No consistent-hash setting moved a key in this finite dataset.']
        else:
            lines += [f"Consistent-hash settings moved {min(fractions):.1%}–{max(fractions):.1%} of keys; every changed owner is the joining node."]
    if modulo:
        lines += [f"Modulo moved {modulo['reassignment']['fraction']:.1%} of keys. Its transfer matrix shows whether moves also occurred between old nodes."]
    for row in rows:
        workload = row['request_balance']
        owner = workload['hot_key_owner']
        before_share = workload['before_hot'][owner]/experiment['uniform_reads']
        after_share = workload['after_hot'][owner]/(experiment['uniform_reads']+experiment['additional_hot_reads'])
        lines += [f"{label(row)}: the hot key belongs to {owner}; that node's share of observed reads changes from {before_share:.1%} to {after_share:.1%}, while its stored-key share remains {row['placement_balance_after']['shares'][owner]:.1%}."]
    if experiment['additional_hot_reads'] == 0:
        lines += ['No extra hot reads were requested, so the two request-count distributions coincide.']
    lines += ['', '## Reading these results', '',
        'Every trial checked the original values and exactly one correctly placed physical copy. Recorded transfer counts agree with changed owners. These checks apply to the exercised runs and the stated no-data-loss assumptions.', '',
        f"The workload sends {experiment['uniform_reads']} sampled uniform reads, then {experiment['additional_hot_reads']} extra reads to the first dataset key. All added reads reach that key's owner; key counts stay fixed. This measures request distribution, not throughput."]
    if consistent:
        lines += [f"The ideal exchangeable-token model predicts mean movement of 1/{n+1} for consistent hashing across random layouts. The observations use fixed IDs; differences from this reference are expected."]
    if modulo:
        lines += [f"Inserting one sorted ID gives the uniform-residue modulo reference {n}/{n+1}. It is an expectation, not an exact finite-key target."]
    lines += ['', 'Repeated processes keep the same placement and dataset. Timing means, ranges and sample SD describe this local execution; they are not confidence intervals over layouts, hardware, networks, or production workloads. One trial has no sample SD, shown as n/a. An empty-node max/min ratio is also n/a.', '',
        'Increasing V need not improve every individual fixed layout. The single-owner design cannot split one hot key. Estimated serialized item bytes exclude HTTP framing, verification and cleanup traffic.', '',
        f"Source hashes match this checkout: {current}. Raw trials and environment.json remain the evidence; the summary is derived from them. Hashes detect accidental changes, not malicious rewriting of both data and receipts."]
    if plots:
        from .plotting import make_plots
        outputs = make_plots(rows, manifest['config'], directory/'figures')
        import matplotlib
        write_json(directory/'figure-manifest.json', {'backend': 'Matplotlib '+matplotlib.__version__,
            'outputs': {p.relative_to(directory).as_posix(): digest(p) for p in outputs},
            'summary_sha256': digest(directory/'summary.json')})
        lines += ['', '## Figures', '']
        captions = {
            'movement': 'Every setting; finite-key moved fractions with ideal-model references. References are expectations under the assumptions above.',
            'balance': 'Every setting; population CV across physical nodes before and after joining. These points describe fixed placements, not replicate uncertainty.',
            'node-loads': 'Every setting and physical node after joining; the reference line is equal key counts.',
            'requests': 'Illustrative full node distribution: consistent V=16 when present, otherwise the first consistent setting or modulo. Each series uses its own stated total; all settings are reported in the text and raw data.',
            'transfers': 'Illustrative modulo matrix when present and the same request-figure setting. Each cell is a count and fraction of all original keys, including stayed keys on the diagonal. Every setting has a raw matrix.',
            'join-time': f"Every setting and all {experiment['trials']} fresh-process timing repetitions; circles are individual observations and open diamonds are means. No inferential error bars are used.",
        }
        for name in ('movement', 'balance', 'node-loads', 'requests', 'transfers', 'join-time'):
            lines += [f'![{name}](figures/{name}.svg)', '', captions[name], '']
    # Keep separate observations readable as paragraphs in Markdown renderers.
    formatted = []
    for line in lines:
        if formatted and line and formatted[-1] and not line.startswith(('|', '#', '![')) and not formatted[-1].startswith(('|', '#', '![')):
            formatted.append('')
        formatted.append(line)
    (directory/'analysis.md').write_text('\n'.join(formatted)+'\n', encoding='utf-8', newline='\n')
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--plots', action='store_true', help='Also export figures; requires requirements-figures.txt.')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--require-current-source', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.check_only:
            _, rows, current = load_run(args.input, args.require_current_source)
            print(f'PASS: {len(rows)} trials; values, owners, counters and digests; current sources match: {current}.')
        else:
            rows = build_report(args.input, args.plots, args.require_current_source)
            print(f'Generated analysis.md, summary.json and summary.csv for {len(rows)} settings.')
        return 0
    except (ConfigError, OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        parser.exit(1, f'Cannot analyze study: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
