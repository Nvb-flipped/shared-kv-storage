# Three consecutive fresh validation rounds

All three final rounds passed on the same frozen source, tests, tools, configuration, documentation and project-metadata fingerprint. Each ran in a separate Linux/WSL directory with a new virtual environment and dependency installation. No prior round's generated results, figures or passing receipts were reused. The final 37-test suite also passed on Windows with Python 3.14.3.

| Round | Runtime | Tests | Full stages | Visual inspection | Receipt |
|---|---|---:|---:|---|---|
| 1 | Linux, Python 3.14.4 | 37 passed | 17 passed | Original and grayscale, study and edge case | [JSON](round-1.json) |
| 2 | Linux, Python 3.14.4 | 37 passed | 17 passed | Original and grayscale, study and edge case | [JSON](round-2.json) |
| 3 | Linux, Python 3.14.4 | 37 passed | 17 passed | Original and grayscale, study and edge case | [JSON](round-3.json) |

Each round reran functional, migration/recovery, malformed-input, configuration, evidence-integrity and plotting-geometry tests; a six-trial study; all CLI commands across three settings with 1,002 exact values each; 28 live API response-schema checks; contract regeneration; documentation/reference and publication audits; 48 math-expression parses; one-key/zero-hot-read reports with empty nodes and a joining ID that sorts first; 36 fresh SVG/PDF/PNG exports; and wheel installation plus isolated package use outside the checkout.

An earlier sequence was reset when visual review found a clipped timing marker. Axis padding was corrected and a geometry regression added before these three final rounds. The figure source preflight has no failures. Its two raster warnings are reviewed in [figure-preflight.json](figure-preflight.json): editable SVG/PDF are primary exports; 300 dpi PNG is a preview, and this academic-study framework has no TIFF submission requirement.

The [summary](summary.json) records receipt hashes and the source fingerprint. [Round 3's worked example](../example/analysis.md) publishes raw trials, verified summaries and figures. Other machine-local logs and environments remain outside publication; receipt log hashes preserve their local identity. These receipts summarize executed checks and are not a proof over every input or environment. Math parsing checks rendering syntax; documented derivations and finite invariants provide separate evidence.

Peers can recreate a fresh complete round with `python tools/validate.py --out results/runs/my-validation` after installing both optional requirements files into a new environment. Run three rounds from separate copies/environments and inspect each round's original and grayscale sheets before counting its pass. See the [peer reproduction guide](../../docs/reproduction.md) for setup, package installation, input limits and interpretation.
