#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results/framework
python3 -m unittest -v 2>&1 | tee results/framework/tests.txt
python3 tools/run_experiments.py | tee results/framework/experiment-run.txt
python3 tools/rehearse.py | tee results/framework/rehearsal.txt
python3 tools/api_contracts.py
.venv-figures/bin/python tools/report.py
python3 tools/doc_navigation.py
.venv-figures/bin/python tools/visual_qa.py
.venv-figures/bin/python tools/author_metadata.py --check --report results/framework/author-properties.json
if .venv-figures/bin/python -c 'import openapi_spec_validator' >/dev/null 2>&1; then
    .venv-figures/bin/python tools/check_contracts.py | tee results/framework/api-audit.txt
fi
if [[ -n "${MATHJAX_PACKAGE:-}" ]]; then
    node tools/check_math.cjs
fi
python3 tools/check_project.py
