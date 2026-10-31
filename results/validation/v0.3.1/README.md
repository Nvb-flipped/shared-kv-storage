# Release validation

Both platforms passed the same frozen public source, tests, tools, configuration and documentation fingerprint. All tests ran, including five plotting tests. Every normal/edge review sheet was inspected in original, grayscale and three color-vision modes. Earlier unsuccessful attempts remain private debugging evidence and are not counted as release passes.

| Platform | Python | Tests | Skips | Full stages | Receipt |
|---|---|---:|---:|---:|---|
| Windows | 3.12.14 | 46 | 0 | 19 | [JSON](windows/validation.json) |
| WSL / Linux | 3.14.4 | 46 | 0 | 19 | [JSON](linux/validation.json) |

The complete environment is requirements-dev.txt plus the pinned optional MathJax package. Each check used a new output directory, six normal and two one-key edge trials, the complete CLI rehearsal across three settings (1,002 exact values each), 30 live HTTP schema responses, 48 rendered math expressions, 36 fresh SVG/PDF/PNG exports and installed-package use outside the checkout. The final 30-trial course comparison is separate in [results/final](../../final/README.md).

Platform folders contain compact receipts, dependency versions, stage logs, API/CLI records and the actual inspected review sheets. Their figure manifests describe local full validation outputs; duplicate individual exports and environments are not published here. Reproduce them with `python tools/validate.py --out results/runs/my-check` after the documented installation. The [evidence manifest](evidence-manifest.json) records published-file hashes and the shared source fingerprint.

Published logs redact machine-specific directory prefixes and remove terminal color codes and trailing formatting whitespace for plain-text reading. Receipts retain the original log hash and record the published file hash so the transformation is explicit. Dependency versions are actual installed versions. These finite checks support the stated course scope and do not establish every input or failure schedule.
