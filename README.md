# Shared KV Storage

A small, configurable framework for studying key placement, single-owner migration and request skew with real local processes. It is intended for coursework, lab exercises and systems learning. Author: Paco.

One router coordinates independent in-memory text stores. A pure HTTP client performs Put/Get and inspection; a study driver collects controlled comparisons. Established modulo and consistent-hashing mechanisms make the behavior easy to connect to the mathematics.

[Study use cases](docs/use-cases.md) · [Configuration](docs/configuration.md) · [Architecture](docs/architecture.md) · [Math and metrics](docs/metrics.md) · [Documentation map](docs/README.md)

## Project structure

```text
.
├── README.md                           # Start, project map and common commands
├── refined_spec.md                     # Supplied primary specification
├── pyproject.toml                      # Package metadata and console entry point
├── package.json                        # Optional Markdown math check
├── package-lock.json                   # Pinned math-renderer dependencies
├── requirements-dev.txt                # Complete test, API and figure-QA environment
├── requirements-figures.txt            # Optional plotting dependencies
├── requirements-contracts.txt          # Optional API validators
├── client.py                           # Standalone HTTP client entry point
├── router.py                           # Standalone router entry point
├── storage_node.py                     # Standalone storage entry point
├── experiment.py                       # Standalone experiment entry point
├── run_cluster.sh                      # WSL/Linux launcher wrapper
├── sharedkv/                           # Runtime and experiment package
│   ├── __init__.py                     # Package definition
│   ├── __main__.py                     # Workflow command dispatcher
│   ├── cli.py                          # HTTP client and interactive prompt
│   ├── config.py                       # Validated TOML profiles
│   ├── cluster.py                      # Owned process startup and shutdown
│   ├── placement.py                    # Integer modulo and consistent hashing
│   ├── router.py                       # Membership and verified migration
│   ├── storage.py                      # Local in-memory text values
│   ├── transport.py                    # Bounded HTTP requests and responses
│   ├── experiment.py                   # One live comparison trial
│   ├── study.py                        # Dataset, schedule and repeated trials
│   ├── metrics.py                      # Balance, movement and ring coverage
│   ├── analysis.py                     # Evidence checks and numeric reports
│   ├── plotting.py                     # Data-derived scientific figures
│   ├── figure_quality.py               # Rendered layout checks
│   └── terminal.py                     # Formatted and colored CLI output
├── configs/                            # Demo, quick-check and course-study profiles
├── tests/                              # System, boundary, study and plotting tests
├── docs/                               # Reading map, design, API, math and assessment
├── results/                            # Recorded observations and validation evidence
│   ├── final/                          # Assessed course comparison and provenance
│   ├── example/                        # Earlier small worked example
│   ├── framework/                      # Authenticated historical measurements
│   ├── validation/                     # Platform receipts and inspected figures
│   └── runs/                           # New local runs; ignored by Git
├── figures/                            # Historical reference plots
├── tools/                              # Reproduction, documentation and export checks
└── .github/                            # Repository automation
    └── workflows/                      # Continuous integration
        └── tests.yml                   # Cross-platform tests and figure checks
```

Start with the [documentation map](docs/README.md) when moving between design, API, experiment and reproduction material. Generated trial filenames are grouped under their run directory rather than listed individually. Private slides, lecture material, skills, caches and virtual environments are excluded from the public project.

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

For the complete development check, install all dependencies into one environment. This includes the plotting tests and PDF/color-vision checks; it does not add dependencies to the KV runtime.

```bash
python -m venv .venv
# WSL/Linux
.venv/bin/python -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
.venv/bin/python tools/validate.py --out results/runs/full-check
```

On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Full validation rejects skipped tests. It checks real CLI/API behavior, installed-package use outside the checkout, rendered figure geometry, metadata and color-vision review sheets. Inspect those sheets as described in the [figure guide](docs/figures.md).

The smaller, dependency-free workflow remains available:

```bash
python -m unittest -v
python tools/reproduce.py --config configs/quick.toml --out results/runs/reproduced
```

Reproduction uses the selected interpreter throughout. It requires no sudo, credentials, private material, original source directory or pre-existing virtual environment. Optional figures use `--plots`. The [reproduction guide](docs/reproduction.md) covers setup, evidence validation, packaging, privacy checks and historical results.

[Course results and interpretation](docs/report.md) identify the final comparison and its raw observations. The [assessment map](docs/assessment.md) connects each criterion to implementation and evidence. [Original measured results](docs/results.md) remain historical reference material. The earlier [small worked example](results/example/analysis.md) illustrates the workflow at its recorded source version. New runs never overwrite either reference dataset.

For an assessed snapshot, use the immutable `v0.3.1` tag rather than assuming that a future `main` still contains the same source. The [reproduction guide](docs/reproduction.md) gives the exact workflow and explains what must agree and why timings may differ.

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
