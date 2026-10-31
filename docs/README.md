# Documentation map

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

Start with the [project README](../README.md). These routes connect a learning goal to settings, observations and interpretation.

| Goal | Route |
|---|---|
| Try a lab exercise | [Use cases](use-cases.md) → [Demo](demo.md) → [Configuration](configuration.md) |
| Run a personal comparison | [Configuration](configuration.md) → [Experiment design](experiment-design.md) → [Reproduction](reproduction.md) |
| Understand behavior | [Architecture](architecture.md) → [Math and metrics](metrics.md) → [API](api.md) → [HTTP clients](api-client.md) |
| Read assessed results | [Course report](report.md) → [Final run](../results/final/) → [Figure guide](figures.md) |
| Compare earlier examples | [Earlier worked example](../results/example/analysis.md) → [Historical reference](results.md) |
| Check course scope | [Assessment map](assessment.md) → [Requirements map](scope.md) → [Specification decisions](spec-decisions.md) → [Attribution](ai-use.md) |

## Repository responsibilities

| Location | Responsibility |
|---|---|
| `sharedkv/` | Runtime, HTTP clients, validated configuration, process lifecycle, study collection, evidence validation and reporting. |
| `client.py`, `experiment.py` | Compatibility wrappers for packaged HTTP clients; no placement decisions. |
| `router.py`, `storage_node.py` | Independent server module entry points. |
| `configs/*.toml` | Demo, quick exercise and course-sized study profiles. |
| `tests/` | API behavior, migration/failure boundaries, config validation and finite invariant checks. |
| `results/runs/` | Ignored local runs; effective settings, schedule, raw trials and derived artifacts. |
| `results/final/` | Assessed full comparison, raw trials, figures, hashes and provenance. |
| `results/example/` | Earlier small worked example at its recorded source version. |
| `results/framework/`, `figures/`, `results/qa/` | Historical reference measurements, figures and receipts. |
| `tools/reproduce.py`, `reproduce.sh` | Current complete workflow using the selected interpreter. |
| `tools/run_experiments.py`, `report.py` | Compatibility wrappers around the current package workflows. |
| `tools/check_project.py`, `check_artifacts.py` | Historical receipt authentication and current documentation checks. |
| `tools/api_contracts.py`, `check_contracts.py` | Schema generation and optional live contract validation. |
| `tools/check_figures.py`, `visual_qa.py` | PDF/export/layout checks and five visual review sheets. |
| `tools/check_release.py`, `check_publication.py` | Assessed evidence/source agreement and publication/privacy checks. |

Runtime and numeric reports are dependency-free. `requirements-dev.txt` provides every test, plotting, PDF, color-vision and API dependency. Core-only test runs may skip optional tests; the full validator rejects all skips. A source checkout needs no installation; an optional package installation supplies the `sharedkv` console command. Local agent skills, virtual environments and private course/presentation files are not distributed or required.

## Follow a result to its evidence

For a new run, read `analysis.md`, then `summary.json` or `summary.csv`, and finally the raw `*-t*.json` files. `environment.json` records the actual schedule, effective configuration, source hashes and per-trial digests. `python -m sharedkv check --input RUN` independently recomputes observable invariants. Source matching is reported separately and can be required explicitly.

The historical example has a different provenance contract: its receipts refer to the public revision pinned in `results/framework/provenance.json`. They must not be represented as new tests or new timing results. The [reproduction guide](reproduction.md) explains both paths.

<!-- reading:start -->
[Documentation map](README.md) · Next: [Study use cases](use-cases.md)
<!-- reading:end -->
