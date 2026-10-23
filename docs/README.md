# Documentation map

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

Start with the [project README](../README.md#start-in-wsl) to launch a cluster. Each page below has one job and links to the next page in a suggested reading order.

## Choose a route

| Your goal | Read in this order |
|---|---|
| Try the system | [Start in WSL](../README.md#start-in-wsl) → [CLI demonstration](demo.md) |
| Understand the design | [Architecture](architecture.md) → [Math and metrics](metrics.md) |
| Write another client | [API reference](api.md) → [Router OpenAPI](openapi.json), [storage OpenAPI](storage-openapi.json) |
| Evaluate the comparison | [Experiment design](experiment-design.md) → [Results](results.md) → [Metric definitions](metrics.md) |
| Check course coverage | [Requirements and evidence](scope.md) → [Specification decisions](spec-decisions.md) |
| Reproduce the evidence | [Reproduction commands](../README.md#optional-artifacts-and-reproduction) → [Reporting tools](../tools/) |

## Repository overview

```text
shared-kv-storage/
├── README.md                     Setup and everyday use
├── refined_spec.md               Supplied primary specification
├── client.py                     Pure HTTP CLI; interactive or one command
├── router.py                     Router process entry point
├── storage_node.py               Storage process entry point
├── experiment.py                 HTTP experiment driver
├── run_cluster.sh                Managed cluster and interactive prompt
├── sharedkv/                     Routing, placement, storage and terminal display
├── tests/                        Behavior, migration and failure cases
├── configs/                      Controlled experiment settings
├── docs/                         Guides, explanations and API contracts
├── results/framework/            Raw trials, summaries and validation receipts
├── results/qa/                   Figure review sheets
├── figures/                      Seven experiment plots in SVG, PDF and PNG
├── tools/                        Reproduction, reporting and audit scripts
└── .github/workflows/            Tests and publication checks
```

The Python runtime and unit tests need no third-party packages. Plotting and contract validation have separate optional requirements. Virtual environments and `.runtime/` are local working directories. Slides, presentation code, speaker notes and supplied lecture files are intentionally absent from the public repository.

Browse: [Runtime](../sharedkv/) · [Tests](../tests/) · [Raw evidence](../results/framework/) · [Figures](../figures/) · [Tools](../tools/)

## Document responsibilities

| File | What it answers |
|---|---|
| [Project README](../README.md) | How do I run, use and reproduce the project? |
| [Architecture](architecture.md) | Which process owns each responsibility, and how does migration work? |
| [API](api.md) | What requests, responses, errors and retry behavior can a client expect? |
| [Math and metrics](metrics.md) | What do the symbols and denominators mean? |
| [Experiment design](experiment-design.md) | What is controlled, repeated and verified? |
| [Results](results.md) | What did the recorded trials show, and what do they not establish? |
| [Demonstration](demo.md) | What commands show the complete system? |
| [Scope](scope.md), [spec decisions](spec-decisions.md) | Where is each requirement implemented? |
| [Attribution](ai-use.md) | Who authored the project, and which tools and sources helped? |

## Follow a result to its evidence

A figure in [results.md](results.md) is generated from `results/framework/summary.json`, which summarizes thirty `*-t*.json` trials. Each trial records owner maps, counters, process IDs and exact-value verification. `environment.json` records the runtime-source hashes and randomized run order. These are recorded observations from the original WSL machine; a fresh run on another PC will have different PIDs and timings.

`tools/report.py` rebuilds the tables and figures. `tools/check_project.py` checks saved observations against the runtime source and documented links. `tools/check_artifacts.py` checks figure, math and author receipts. `tools/check_publication.py` checks the Git index and reachable history before publication. The [experiment design](experiment-design.md) explains the limits of the repeated runs.

<!-- reading:start -->
[Documentation map](README.md) · Next: [Architecture](architecture.md)
<!-- reading:end -->
