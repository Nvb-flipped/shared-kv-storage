"""Audit saved evidence, source hashes, equations/links and the final project scope."""
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.metrics import movement
from tools.reference_evidence import check_source


def main():
    out = ROOT/'results/framework'
    environment = json.loads((out/'environment.json').read_text(encoding='utf-8'))
    for name, digest in environment['source_sha256'].items():
        check_source(name, digest)
    files = list(out.glob('*-t*.json')); assert len(files) == 30
    datasets, sequences = set(), set()
    for file in files:
        row = json.loads(file.read_text(encoding='utf-8')); count = row['key_count']
        assert row['owned_children_stopped']
        assert len(set(row['pids'].values())) == 5
        assert row['verification']['checked'] == count == 1000
        assert row['verification']['failures'] == row['verification']['physical_failures'] == []
        assert row['reassignment'] == movement(row['owners_before'], row['owners_after'])
        moved = row['reassignment']['reassigned_key_count']
        assert moved == row['migration']['migrated'] == row['migration']['verified']
        matrix = row['reassignment']['matrix_counts']
        for node in row['placement_balance_before']['key_counts']:
            assert sum(matrix[node].values()) == row['placement_balance_before']['key_counts'][node]
        for node in row['placement_balance_after']['key_counts']:
            assert sum(r.get(node, 0) for r in matrix.values()) == row['placement_balance_after']['key_counts'][node]
        if row['mode'] == 'consistent':
            assert moved == row['placement_balance_after']['key_counts']['D']
            assert all(old == new or new == 'D' for key, old in row['owners_before'].items() for new in [row['owners_after'][key]])
            ring = row['ring_after']; assert len(ring['tokens']) == 4*row['vnodes_per_node']
            assert all(type(t['pos']) is int for t in ring['tokens'])
        workload = row['request_balance']; hot = workload['hot_key_owner']
        assert sum(workload['before_hot'].values()) == 1000 and sum(workload['after_hot'].values()) == 1500
        assert all(workload['after_hot'][n]-workload['before_hot'][n] == (500 if n == hot else 0) for n in workload['after_hot'])
        assert all(r['stored_on'] == [r['owner']] for r in row['physical_inventory']['keys'])
        datasets.add(row['dataset_sha256']); sequences.add(row['uniform_sequence_sha256'])
    assert len(datasets) == len(sequences) == 1
    rehearsal = json.loads((out/'rehearsal.json').read_text(encoding='utf-8'))
    assert rehearsal['status'] == 'passed' and len(rehearsal['cases']) == 3
    for case in rehearsal['cases']:
        assert case['verified_values'] == 1002 and not case['failures']
        assert case['paused_put_status'] == 503 and case['get_during_migration']['value'] == 'Apple-2'
        assert case['owned_children_stopped'] and case['physical_ownership_verified']
    from tools.doc_navigation import ORDER
    docs = [ROOT/'README.md', *[ROOT/'docs'/name for name in ORDER]]
    links = blocks = 0
    for file in docs:
        text = file.read_text(encoding='utf-8')
        assert not re.search(r'[\u3400-\u9fff]', text), f'Maintained documentation must be English: {file.name}'
        assert '\\operatorname' not in text
        assert text.count('```') % 2 == 0 and text.count('\n$$\n') % 2 == 0, file
        blocks += text.count('\n$$\n')//2
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
            if '://' in target or target.startswith('#'): continue
            assert (file.parent/target.split('#')[0]).resolve().exists(), (file, target)
            links += 1
    assert blocks >= 10
    for name in ('kvstore', 'web', 'experiments', 'scripts'):
        assert not (ROOT/name).exists(), f'Remove superseded system directory: {name}'
    assert not (ROOT/'docs/console-openapi.json').exists()
    tests = (out/'tests.txt').read_text(encoding='utf-8'); assert 'OK' in tests
    test_count = int(re.search(r'Ran (\d+) tests', tests)[1]); assert test_count >= 14
    assert json.loads((out/'api-audit.json').read_text(encoding='utf-8'))['status'] == 'passed'
    report = {'author': 'Paco', 'status': 'passed', 'trials': 30, 'tests': test_count,
        'identical_dataset_and_uniform_sequence': True, 'verified_values_per_trial': 1000,
        'migration_readable_and_writes_rejected': True, 'rehearsal_cases': 3,
        'maintained_markdown_files': len(docs), 'local_links': links, 'math_blocks': blocks,
        'reference_source_hashes_verified': True, 'reference_kind': 'historical fixed-layout course exercise',
        'legacy_system_removed': True,
        'scope': 'Single-owner text storage, integer placement, runtime configuration, virtual nodes, no web or replication'}
    (out/'project-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS: historical receipts for {test_count} tests and 30 trials; values/owners; migration rehearsal; {blocks} math blocks and current documentation links.')


if __name__ == '__main__': main()
