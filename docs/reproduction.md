# Reproduce from a fresh clone

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

Core runtime, tests, study collection, integrity checks and numeric reports require only Python 3.11+. No sudo, credentials, local skills, private lecture files, original directory, database or cloud service is required. Linux, WSL and Windows use the same Python commands. For WSL timing exercises, use its Linux filesystem; interpreter and filesystem differences remain part of the local environment.

## Core workflow

```bash
git clone https://github.com/Nvb-flipped/shared-kv-storage.git
cd shared-kv-storage
python -m unittest -v
python tools/reproduce.py --config configs/quick.toml --out results/runs/first-check
```

Use `python3` if that is your Python 3 command. `reproduce.py` uses its own interpreter for children, runs the unit/integration tests, collects fresh trials, creates reports and verifies evidence against current source hashes. It writes `tests.txt` and `workflow.json` after those stages succeed. Repeated invocations need different output directories.

On WSL/Linux, `bash tools/reproduce.sh --config configs/quick.toml --out results/runs/another-check` is a wrapper. `PYTHON` can select an interpreter. No named virtual environment is assumed.

## Optional figures

Create any virtual environment and install [requirements-figures.txt](../requirements-figures.txt) into that interpreter. On Linux/WSL:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-figures.txt
.venv/bin/python tools/reproduce.py --config configs/study.toml --out results/runs/full-comparison --plots
```

On Windows use `.venv\Scripts\python.exe`. Export is headless and needs neither GUI nor TeX. Six figure sets appear under the run's `figures/`, in SVG, PDF and PNG. The Matplotlib version and output hashes are recorded. Compatible dependency ranges make installation portable; timings and rendered bytes need not match another machine. Historical `requirements-figures.lock` describes the original reference environment and is not required by the current workflow.

For a completed run:

```bash
python -m sharedkv check --input results/runs/first-check
python -m sharedkv report --input results/runs/first-check --plots
python tools/visual_qa.py --input results/runs/first-check
```

Validation covers completeness, raw hashes, configuration/schedule agreement, owner maps, migration counts, physical copies, data/read digests and hot-request counter differences. `--require-current-source` also requires source hashes to match this checkout. Without it, reports label whether sources match. Recorded checks establish only what was exercised, under the stated assumptions.

## Output and privacy

New runs live in Git-ignored `results/runs/`. They contain effective settings, actual order, a portable environment description, raw observations, source hashes, summaries and interpretation. Failed/interrupted runs retain their status and completed cases; analysis refuses incomplete runs. Automatic resume is absent to avoid mixing sources or environments.

Manifests omit usernames, hostnames, absolute checkout paths, environment dumps and credentials. Raw responses contain synthetic keys/values, loopback addresses and transient PIDs. Use synthetic data and review output before sharing it.

`python tools/check_publication.py` checks tracked history for known credential patterns and current publishable files for those patterns, quoted password assignments and machine-specific home paths. Ignored environments and skills are excluded. This focused check cannot recognize every kind of private information.

If `mathjax-full` 3.2.2 is already installed, set `MATHJAX_PACKAGE` to its package directory and run `node tools/check_math.cjs` for an optional current-formula parsing check. It writes `.runtime/math-validation.json` by default; `--out` selects another receipt. This optional tool does not overwrite historical math receipts during ordinary use.

## Install the package for another working directory

Installation is optional. From this checkout, install into a chosen virtual environment with `python -m pip install .`. The environment then provides `sharedkv` and `python -m sharedkv`; core dependencies remain empty. Configuration files and documentation stay in the checkout, so copy a TOML profile into your exercise directory and supply `--config` explicitly when working elsewhere:

```bash
sharedkv study --config settings.toml --out run --keys 20 --trials 1
sharedkv check --input run --require-current-source
sharedkv report --input run
sharedkv demo --isolated
```

Use the virtual environment's Python/console command. A config's output path is relative to that config; explicit `--out` is relative to the current directory. The installed launcher starts its own package modules, independent of the source checkout's name or location.

## Additional functional checks

`python tools/rehearse.py --out results/runs/cli-check` exercises all CLI commands, interactive continuation after a missing key, three placement settings, reconfiguration, complete value verification and process shutdown. Concurrent migration and failure recovery use deterministic integration tests rather than a timing-sensitive rehearsal poll.

Optional API checks require `python -m pip install -r requirements-contracts.txt`, then `python tools/check_contracts.py --out results/runs/api-check`. These validate both OpenAPI documents and real success/error responses. Both tools refuse nonempty output directories and keep their current receipts separate from historical evidence.

## Full validation rounds

For the broader maintainer check, install both optional requirements files into a fresh environment, then run `python tools/validate.py --out results/runs/validation-1`. It reruns tests, a new six-trial study, every CLI command, live API schemas, documentation/reference audits, publication scanning, edge-case reports/figures, wheel installation and an isolated installed-package exercise outside the checkout. Inspect both original and grayscale sheets under `study/` and `edge/`; its receipt deliberately leaves visual review pending.

For three consecutive validation rounds, use three fresh checkout copies and virtual environments, rerun dependency installation, and choose new output directories. Never copy earlier raw runs, generated figures or passing receipts into a new round. Validate the same frozen source/docs/configuration fingerprint. Count a pass only after fresh automated checks and visual inspection; a failure or source change resets the sequence. Different operating systems add portability coverage. Passing finite checks does not establish correctness for every possible input or environment.

## Published reference evidence

The [original measured comparison](results.md) remains in `results/framework/` and `figures/`. It is historical evidence, not a fresh run of the current version. `provenance.json` pins its public source revision. Personal directory prefixes were redacted without changing measurements; old math-rendering receipts refer to documentation at that revision.

With a full Git clone, optional reference audits are:

```bash
python tools/check_project.py
python tools/check_artifacts.py
```

A shallow clone or source archive can run the current workflow but may lack Git objects for historical authentication. Current reproduction never requires those objects or private files. Optional live API-contract checks use `requirements-contracts.txt`. The separate `tools/rehearse.py` retains the original A/B/C-to-D CLI exercise and is not a configurable timing trial.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Configuration](configuration.md) · Next: [Architecture](architecture.md)
<!-- reading:end -->
