"""Config boundaries, portable workflows, evidence integrity and finite invariants."""
from dataclasses import replace
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sharedkv.analysis import build_report, load_run
from sharedkv.config import ClusterConfig, ConfigError, ExperimentConfig, StudyConfig, load_config
from sharedkv.metrics import balance, token_coverage
from sharedkv.placement import Placement, SPACE
from sharedkv.study import run_study, schedule_for, write_json

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_shipped_profiles_and_help(self):
        for name in ('demo', 'quick', 'study'):
            load_config(ROOT/f'configs/{name}.toml')
        result = subprocess.run([sys.executable, '-m', 'sharedkv', 'study', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--dry-run', result.stdout)

    def test_rejects_unknown_settings_and_wrong_types(self):
        for text in ('[clustr]\nvnodes=4', '[cluster]\nvnode=4', '[experiment]\ntrials=true',
                     '[cluster]\nisolated="yes"', '[experiment]\nvnodes=16', '[cluster]\ninitial_nodes="AB"'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'invalid.toml'
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ConfigError):
                    load_config(path)

    def test_topology_and_port_bounds(self):
        for settings in ({'initial_nodes': ()}, {'initial_nodes': ('A', 'A')},
                         {'joining_node': 'A'}, {'joining_node': 'node1'},
                         {'router_port': 0}, {'storage_base_port': 65534},
                         {'isolated': False, 'storage_base_port': 7999},
                         {'startup_timeout': float('nan')}, {'vnodes': True}):
            with self.subTest(settings=settings), self.assertRaises(ConfigError):
                ClusterConfig(**settings)

    def test_study_bounds_and_schedule(self):
        for settings in ({'keys': 0}, {'trials': 0}, {'vnodes': (1, 1)}, {'vnodes': (1025,)},
                         {'modes': ()}, {'modes': ('other',)}, {'additional_hot_reads': -1}):
            with self.subTest(settings=settings), self.assertRaises(ConfigError):
                ExperimentConfig(**settings)
        config = ExperimentConfig(trials=2, vnodes=(2, 8))
        schedule = schedule_for(config)
        self.assertEqual(schedule, schedule_for(config))
        self.assertEqual(len(schedule), 6)
        for trial in (1, 2):
            self.assertEqual({(r['mode'], r['vnodes']) for r in schedule if r['trial'] == trial},
                             {('modulo', 1), ('consistent', 2), ('consistent', 8)})

    def test_dry_run_overrides_and_config_relative_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'settings.toml'
            path.write_text('[experiment]\noutput="nested/run"\n', encoding='utf-8')
            result = subprocess.run([sys.executable, '-m', 'sharedkv', 'study', '--config', str(path),
                                     '--keys', '7', '--trials', '1', '--dry-run'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['config']['experiment']['keys'], 7)
            self.assertEqual(Path(data['output']), path.parent/'nested/run')
            self.assertFalse((path.parent/'nested').exists())

    def test_refuses_to_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp)/'keep.txt'
            sentinel.write_text('keep', encoding='utf-8')
            with self.assertRaisesRegex(ConfigError, 'new or empty'):
                run_study(StudyConfig(ClusterConfig(), ExperimentConfig()), tmp)
            self.assertEqual(sentinel.read_text(), 'keep')


class FiniteInvariantTests(unittest.TestCase):
    def test_recorded_ring_coverage_counts_wraparound_and_single_position(self):
        self.assertEqual(token_coverage([{'node': 'B', 'pos': 20}, {'node': 'A', 'pos': 80}], 100),
                         {'A': 60, 'B': 40})
        self.assertEqual(token_coverage([{'node': 'A', 'pos': 0}], 100), {'A': 100})
        with self.assertRaises(ValueError):
            token_coverage([{'node': 'A', 'pos': 80}, {'node': 'B', 'pos': 20}], 100)

    def test_modulo_uniform_residue_expectation_for_every_insertion_position(self):
        # Exact enumeration of the CRT sample space, not sampled key hashes.
        for n in range(1, 26):
            for insertion in range(n+1):
                old = list(range(n))
                new = old[:insertion]+['new']+old[insertion:]
                stayed = sum(old[h % n] == new[h % (n+1)] for h in range(n*(n+1)))
                self.assertEqual(stayed, n)

    def test_membership_permutations_and_fixed_token_joins(self):
        # Bounded generated cases, not a claim of exhaustive SHA-256 coverage.
        keys = [f'key-{i}' for i in range(80)] + ['λ/🍎', 'edge']
        for v in (1, 2, 8):
            reference = Placement('ABC', 'consistent', v)
            for order in itertools.permutations('ABC'):
                ring = Placement(order, 'consistent', v)
                self.assertEqual([ring.owner(k) for k in keys], [reference.owner(k) for k in keys])
            joined = Placement('ABCD', 'consistent', v)
            self.assertEqual(sum(s['hash_units'] for s in joined.view()['node_shares'].values()), SPACE)
            self.assertTrue(all(joined.owner(k) in (reference.owner(k), 'D') for k in keys))
        self.assertEqual(Placement('A', 'consistent', 1).view()['node_shares']['A']['hash_units'], SPACE)

    def test_empty_nodes_have_no_finite_ratio(self):
        self.assertIsNone(balance({'A': 0, 'B': 1})['max_min_ratio'])
        for counts in ({}, {'A': -1}, {'A': True}):
            with self.assertRaises(ValueError):
                balance(counts)


class StudyIntegrationTests(unittest.TestCase):
    def test_custom_topology_single_trial_zero_hot_and_evidence_tamper(self):
        config = StudyConfig(ClusterConfig(initial_nodes=('X',), joining_node='Y'),
            ExperimentConfig(keys=3, uniform_reads=4, additional_hot_reads=0, trials=1,
                             modes=('consistent',), vnodes=(2,)))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'relocated run'
            run_study(config, out)
            self.assertTrue(all(b'\r\n' not in p.read_bytes() for p in out.glob('*.json')))
            rows = build_report(out, require_current=True)
            report = (out/'analysis.md').read_text(encoding='utf-8')
            self.assertIn('Placement and transfer evidence', report)
            self.assertIn('Copied / verified', report)
            self.assertIn('Joining-node hash-space coverage', report)
            self.assertIn('X=3', report)
            self.assertIn('not measured network traffic', report)
            self.assertIsNone(rows[0]['join_seconds']['sample_sd'])
            self.assertIn('n/a', (out/'analysis.md').read_text(encoding='utf-8'))
            manifest = json.loads((out/'environment.json').read_text())
            self.assertNotIn(str(ROOT), json.dumps(manifest))
            manifest['status'] = 'failed'
            write_json(out/'environment.json', manifest)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                load_run(out)
            manifest['status'] = 'complete'
            receipt = manifest['completed'].pop()
            write_json(out/'environment.json', manifest)
            with self.assertRaisesRegex(ValueError, 'Missing'):
                load_run(out)
            manifest['completed'].append(receipt)
            write_json(out/'environment.json', manifest)
            case_path = out/manifest['schedule'][0]['file']
            row = json.loads(case_path.read_text())
            row['migration']['verified'] += 1
            write_json(case_path, row)
            with self.assertRaisesRegex(ValueError, 'digest'):
                load_run(out)
            manifest['completed'][0]['sha256'] = hashlib.sha256(case_path.read_bytes()).hexdigest()
            write_json(out/'environment.json', manifest)
            with self.assertRaisesRegex(ValueError, 'Migration counts'):
                load_run(out)


if __name__ == '__main__':
    unittest.main()
