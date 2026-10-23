# Shared KV Storage

A small, configurable framework for studying key placement, single-owner migration and request skew with real local processes. It is intended for coursework, lab exercises and systems learning. Author: Paco.

One router coordinates independent in-memory text stores. A pure HTTP client performs Put/Get and inspection; a study driver collects controlled comparisons. Established modulo and consistent-hashing mechanisms make the behavior easy to connect to the mathematics.

[Study use cases](docs/use-cases.md) · [Configuration](docs/configuration.md) · [Architecture](docs/architecture.md) · [Math and metrics](docs/metrics.md) · [Documentation map](docs/README.md)

## Start an interactive cluster

Python 3.11+ is sufficient; the runtime has no third-party dependencies. Run from a fresh clone on Linux, WSL or Windows:

```bash
git clone https://github.com/Nvb-flipped/shared-kv-storage.git
cd shared-kv-storage
python -m sharedkv demo --config configs/demo.toml
```

Use `python3` where that names your Python 3 interpreter. The demo starts A/B/C as members, an empty waiting D, a router, and a separate client prompt. Readiness messages include the router URL and exact join command. The launcher cleans up only the processes it owns. Occupied ports fail safely; use configuration or CLI flags to choose another range.

```text
put user:101 Apple
get user:101
owner user:101
ring user:101 --check
stats
addnode D 127.0.0.1:5104
get user:101
membership
quit
```

The default demo profile uses the address shown above; use the printed command for a modified topology. Another terminal can attach with `python -m sharedkv client --router http://127.0.0.1:8000`. The [demo guide](docs/demo.md) explains misses, counters, reconfiguration and HTTP clients. `bash run_cluster.sh` and the standalone Python scripts remain available.

## Configure a comparison

[configs/quick.toml](configs/quick.toml) is a small two-to-three-node exercise. [configs/study.toml](configs/study.toml) runs the original-sized 30-trial comparison. Copy either file to choose node IDs, placement policies, token counts, keys, read counts, extra hot reads, repetitions and seed. Ports and readiness deadlines are configurable too.

```bash
python -m sharedkv study --config configs/quick.toml --dry-run
python -m sharedkv study --config configs/quick.toml --keys 200 --out results/runs/my-study
python -m sharedkv check --input results/runs/my-study --require-current-source
python -m sharedkv report --input results/runs/my-study
```

TOML is parsed with the standard library. CLI flags override file settings; invalid settings are rejected before launch. A nonempty output directory is never overwritten. New runs stay in Git-ignored `results/runs/` and contain their own effective settings, schedule, source hashes, raw observations, summaries and explanation. See [configuration semantics](docs/configuration.md).

The numeric report needs no plotting packages. To export six figure sets as SVG/PDF/PNG, install `requirements-figures.txt` into your chosen Python environment and add `--plots` to the report command. Figures derive node labels, totals, timing points and axis ranges from the run.

## What the exercises show

- **Movement:** compare changed owners and actual acknowledged transfers when one node joins.
- **Placement balance:** compare every node's key counts, max/min ratio and population CV across token settings.
- **Request skew:** send uniform reads, then extra reads to one hot key; key balance stays fixed while request counts change.
- **Migration behavior:** examine verified publication, paused writes, readable Gets and explicit failure recovery.

Every trial reads all original values after joining and checks exactly one correctly placed physical copy. It compares changed owners with acknowledged and verified copies. Repeated processes keep the same node identities and dataset: they describe local timing variability, not independent random layouts or universal performance. The [experiment guide](docs/experiment-design.md) gives a practical checklist and interpretation limits.

## Reproduce and verify

```bash
python -m unittest -v
python tools/reproduce.py --config configs/quick.toml --out results/runs/reproduced
```

Reproduction uses the selected interpreter throughout. It requires no sudo, credentials, private material, original source directory or pre-existing virtual environment. Optional figures use `--plots`. The [reproduction guide](docs/reproduction.md) covers setup, evidence validation, packaging, privacy checks and historical results.

[Original measured results](docs/results.md) are preserved as a historical course comparison, with their own source provenance. New runs never overwrite those reference measurements. The small [current worked example](results/example/analysis.md) illustrates the configurable workflow; it is a learning example, not a performance baseline.

## System boundaries

The framework is a local teaching system: volatile stores, one router, one owner per key, sequential study requests and loopback HTTP. It has no replication, consensus, authentication, TLS, persistence, node removal or automatic failure eviction. It is useful for an experimental text lookup exercise; it should not hold valuable data or serve a network application.

Migration pauses Put, copies and verifies destinations, waits for in-flight old-owner Gets, publishes the new map, then removes old copies. Recovery rolls back staging before publication or finishes cleanup afterward. It cannot restore storage contents lost in a crash. Runtime mode/V changes leave data in place and require explicit flush/reload.

## Code and extension map

| Area | Responsibility |
|---|---|
| `sharedkv/placement.py`, `router.py`, `storage.py`, `transport.py` | Ownership, coordination, local values and bounded HTTP. |
| `sharedkv/config.py`, `cluster.py` | Validated settings and owned-process lifecycle. |
| `sharedkv/experiment.py`, `study.py` | Pure HTTP exercise and configured trial orchestration. |
| `sharedkv/analysis.py`, `plotting.py` | Evidence checks, descriptive reports and optional figures. |
| `tests/` | HTTP, migration, failure, configuration and bounded invariant tests. |
| `docs/`, `configs/`, `results/` | Learning guides, example profiles and traceable observations. |

`python -m sharedkv --help` lists workflows. An optional `python -m pip install .` provides the `sharedkv` console command; source-checkout commands do not need installation. See [extension boundaries](docs/use-cases.md) before adding policies or workloads.

The design applies [Dynamo §4.2](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf); [MIT's shard lab](https://pdos.csail.mit.edu/6.5840/labs/lab-shard1.html) is a transfer/configuration reference. The [scope map](docs/scope.md), [specification decisions](docs/spec-decisions.md), [API contracts](docs/api.md), and [attribution](docs/ai-use.md) document the course scope and assistance.
