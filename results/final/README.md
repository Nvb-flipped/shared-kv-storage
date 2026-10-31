# Assessed course comparison

This directory contains fresh observations for `v0.3.1`. It uses the full `configs/study.toml` profile, with 30 independent process lifecycles and the same 1,000 records in each trial. Each trial verifies every original value and exactly one correctly placed physical copy after migration.

Start with [the course report](../../docs/report.md), then [analysis.md](analysis.md). The generated analysis includes exact node counts, movement/transfer agreement, calculated logical item sizes, actual joining-ring coverage, hot-key shares and timing summaries. The [figure guide](../../docs/figures.md) explains the population boxes and the limits of each visual comparison.

| File | Purpose |
|---|---|
| `environment.json` | Effective settings, actual randomized order, package-source hashes and per-trial digests. |
| `*-t*.json` | All raw router-returned owners, physical inventory, migration results, request counters, process IDs and exact-value checks. |
| `summary.json`, `summary.csv`, `analysis.md` | Derived numeric comparison and interpretation. |
| `figures/`, `figure-manifest.json` | Six SVG/PDF/PNG sets, six layout receipts and output hashes. |
| `figure-audit.json`, `qa/` | Portable export checks and additional rendered PDF/alignment audits. |
| `figure-review*.png`, `visual-review.json` | Original/grayscale/three color-vision sheets and the recorded visual inspection. |
| `tests.txt`, `workflow.json` | Tests executed during collection, including every plotting test with zero skips. |
| `dependencies.txt`, `provenance.json` | Actual complete Python environment and the assessed source/configuration basis. |

To audit the saved evidence, install `requirements-dev.txt`, then run:

```bash
python -m sharedkv check --input results/final --require-current-source
python tools/check_release.py
```

Those commands authenticate saved observations and source agreement. They do not pretend to read the original values from processes that have already stopped. Use the [fresh reproduction instructions](../../docs/reproduction.md) to collect new live observations.

The source preflight has no failures. Its two submission-format warnings concern TIFF and a 600 dpi raster default. This course report uses editable SVG/PDF and 300 dpi PNG; it has no journal-submission raster requirement. SVG line endings are normalized to LF for portable Git hashes without changing figure geometry or data.

Keep this assessed dataset unchanged. Use a new directory under `results/runs/` for another experiment or style exploration. Timing variation across runs is expected; fixed-source ownership, exact values, transfer conservation and workload counters must remain consistent. Repeated fixed identities are not independent token layouts, and item bytes are calculated logical sizes rather than captured network traffic.
