# UM submission

The final report is [report.pdf](report.pdf): four A4 pages of main text, figures and table, followed by one reference page. The main text uses Latin Modern at 12 pt; captions and the comparison table use smaller type. There is no separate title page. All report text is English.

The report explains the question, Dynamo connection, architecture, implementation, API boundaries, correctness evidence, experiment, results, interpretation, limitations, changes after presentation feedback, personal contributions and AI assistance. It summarizes the documentation rather than reproducing the full API specification or every raw observation. The [documentation map](../docs/README.md) leads to those details.

The PDF includes clickable GitHub links at relevant passages and an extended-material index on page 4. Detailed API definitions, derivations, experiment protocol, complete results, reproduction instructions and assistance notes are pinned to revision `3f5da8a`; the corresponding repository link remains printed in the references. Core methods, results and limitations remain in the report itself.

## Rebuild

From the project root, with Python 3.11+ and an existing TeX Live installation:

```bash
python tools/build_report.py
python tools/check_submission.py
```

The compiler needs `pdflatex`, Latin Modern, geometry, AMS math, graphicx, booktabs, microtype, caption, titlesec and hyperref. These are included in a full TeX Live installation. For a smaller installation, install the corresponding packages using its package manager. No shell escape, network access, local skill or private slide material is used. PDF inspection uses PyMuPDF from `requirements-dev.txt`.

The builder checks the saved study against the current runtime, regenerates [results-table.tex](results-table.tex) directly from the raw observations, and runs two bounded compiler passes. Logs stay under ignored `.runtime/report-build/`. The report uses the public architecture PNG and the existing data-derived request figure; the assets are not copied from presentation slides. The output is authored by Paco. [Build checks](build-checks.json) record actual page/font/data checks; visual review is a separate inspection of the rendered pages.

The final raw observations belong to runtime `v0.3.1`. The report's architecture and submission notes are later documentation refinements. Rebuilding a different runtime requires collecting and validating a new matching study; do not relabel the existing timings.

The [submission verification receipt](validation.json) records a fresh test of an extracted source archive without `.git`: 46 tests, zero skips, six new 60-key trials and 18 checked exports. Rebuilding the report from that archive produced the same five-page text and rendered pixels. All five final report pages were inspected visually. These workflow checks supplement the assessed 30-trial data; they are not additional observations in its comparison table.

## Submit

Upload two attachments: `report.pdf` for direct reading and one source ZIP containing the top-level README, runtime, configurations, tests, raw results, plotting/reproduction scripts and report source. This preserves the directory structure within the submission limit of 20 attachments and 200 MB per file. The PDF also stays inside the source archive to keep that package self-contained. Build the archive after the report checks pass:

```bash
python tools/package_submission.py --out results/runs/um-submission.zip
```

The packager includes public project files, adds a file/hash manifest, and excludes Git internals, environments, caches, local skills and every private presentation file. It refuses to overwrite an existing archive and verifies its contents before completing. Packaging requires a Git checkout to enumerate the public files; running the submitted system does not. The top-level [README](../README.md) supplies setup, dependency groups, startup, sample inputs, hardware guidance and troubleshooting. Reference-only Git-history audits require a full clone; the current reproduction workflow also works from the source archive.

## Changes and contributions

The historical baseline is the 23 October public revision `a245768`. The supplied feedback areas are TOML configuration, one entry point, dependency installation, configurable workloads, timeout handling, fresh source-matched evidence, actual ring coverage, an architecture diagram, documentation navigation and reproducibility. These areas are reflected in the report; hashing, virtual nodes and migration already existed at the baseline.

Paco selected the experimental settings, directed the flexible framework design, specified API exception handling and completed the initial mathematical derivations. Codex assisted with implementation and checks and helped refine/formalize the mathematical exposition. The report and [assistance statement](../docs/ai-use.md) retain that distinction. No implementation from Dynamo or the MIT lab was copied.
