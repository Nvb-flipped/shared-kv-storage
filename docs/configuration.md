# Configure a study

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

Use TOML with Python 3.11 or newer; `tomllib` is in the standard library. One configuration describes topology and the controlled workload. TOML avoids an extra YAML parser and a second set of type-coercion rules for this small framework.

## Choose a profile

| Profile | Purpose |
|---|---|
| [demo.toml](../configs/demo.toml) | Interactive A/B/C cluster, waiting D, predictable ports for a second client. |
| [quick.toml](../configs/quick.toml) | Two-to-three-node comparison, six trials; a fast end-to-end exercise. |
| [study.toml](../configs/study.toml) | Original-sized three-to-four-node comparison, 30 trials. |

Copy a profile, change one question at a time, and validate before collecting data:

```bash
python -m sharedkv study --config configs/quick.toml --dry-run
python -m sharedkv study --config configs/quick.toml --keys 200 --trials 3 --out results/runs/my-comparison
python -m sharedkv report --input results/runs/my-comparison --plots
```

CLI flags override file settings. Unknown tables/keys, duplicate IDs, booleans used as numbers, invalid ranges and overlapping fixed ports are rejected before launch. No script kills a process already using a port.

## Settings

| Table and key | Meaning and constraint |
|---|---|
| `cluster.initial_nodes` | Nonempty array of distinct single uppercase IDs A–Z. |
| `cluster.joining_node` | One distinct uppercase ID; its empty process starts before the join. |
| `cluster.placement` | `modulo` or `consistent` for the interactive launcher. A study uses `experiment.modes`. |
| `cluster.vnodes` | Integer 1–1024 for the interactive launcher. A study uses `experiment.vnodes`. |
| `cluster.isolated` | `true` selects distinct OS-assigned loopback ports; recommended for trials. |
| `cluster.router_port` | Router port when `isolated=false`; otherwise ignored. |
| `cluster.storage_base_port` | First consecutive storage port when `isolated=false`; otherwise ignored. |
| `cluster.startup_timeout` | Finite positive readiness deadline per child, in seconds. |
| `experiment.keys` | Positive number of deterministic Unicode text records. |
| `experiment.uniform_reads` | Positive seeded uniform reads, sampled with replacement. |
| `experiment.additional_hot_reads` | Nonnegative extra reads to the first dataset key; zero is a control. |
| `experiment.seed` | Nonnegative seed for setting order and read sampling. It does not randomize tokens or dataset contents. |
| `experiment.trials` | Positive fresh-process repetitions per setting. |
| `experiment.modes` | Nonempty array containing `modulo`, `consistent`, or both, without duplicates. |
| `experiment.vnodes` | Nonempty array of distinct integers 1–1024. Modulo runs once per round with V=1. |
| `experiment.output` | Path relative to the TOML file's directory. |

CLI `--out` is relative to the current working directory. Absolute paths also work, but manifests record output as `.` and omit the checkout path. A nonempty directory is refused, including a failed run; retain it for inspection and choose a new path.

Each round shuffles every requested setting exactly once. Trial count is `trials × (number of consistent V settings + one if modulo is selected)`. Node counts, workloads and denominators propagate into validation, reports and figures.

## Interactive overrides

```bash
python -m sharedkv demo --config configs/demo.toml --nodes A,B --joining-node C --vnodes 8
python -m sharedkv demo --config configs/demo.toml --router-port 8100 --storage-base-port 5201
python -m sharedkv demo --config configs/demo.toml --isolated
```

Use the router URL and join command printed at startup. Configuration applies at launch. Runtime `placement` and `vnodes` commands retain the explicit flush/reload rule; editing TOML does not mutate a running cluster.

One joining node per fresh trial is supported. Multi-host deployment, node removal, durability and replication remain outside scope. Large key counts and sweeps can take substantial time; the dry run exposes the planned work.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Study use cases](use-cases.md) · Next: [Reproduction](reproduction.md)
<!-- reading:end -->
