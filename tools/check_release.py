"""Audit the assessed course evidence against the current package sources."""
import argparse
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.analysis import load_run, read_json, require
from sharedkv.study import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'results/final')
    args = parser.parse_args()
    try:
        from tools.check_figures import audit
        manifest, trials, current = load_run(args.input, require_current=True)
        provenance = read_json(args.input/'provenance.json')
        package = tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']
        require(provenance['release_tag'] == 'v'+package['version'], 'Release tag and package version differ.')
        require(provenance['source_sha256'] == manifest['source_sha256'], 'Release source map differs.')
        require(provenance['config_sha256'] == digest(ROOT/'configs/study.toml'), 'Assessed profile differs.')
        settings = manifest['config']['experiment']
        topology = manifest['config']['cluster']
        require(topology['initial_nodes'] == ['A', 'B', 'C'] and topology['joining_node'] == 'D', 'Assessed topology differs.')
        require((settings['keys'], settings['uniform_reads'], settings['additional_hot_reads'], settings['trials']) ==
                (1000, 1000, 500, 3), 'Assessed workload differs.')
        require(settings['vnodes'] == [1, 2, 4, 8, 10, 16, 32, 64, 128] and
                settings['modes'] == ['modulo', 'consistent'], 'Assessed settings differ.')
        require(len(trials) == 30, 'Thirty assessed trials are required.')
        workflow = read_json(args.input/'workflow.json')
        require(workflow['status'] == 'passed' and workflow['tests_skipped'] == 0, 'Release tests did not all execute.')
        figures = audit(args.input)
        require(figures['status'] == 'passed', 'Release figure geometry or metadata failed.')
        visual = read_json(args.input/'visual-review.json')
        require(visual['manual_review'] == 'completed', 'Final visual review has not been recorded.')
        for mode, row in visual['sheets'].items():
            require(digest(args.input/row['file']) == row['sha256'], 'A reviewed sheet has changed: '+mode)
        require(set(visual['sheets']) == {'original', 'grayscale', 'protanomaly', 'deuteranomaly', 'tritanomaly'},
                'Five visual review modes are required.')
        print(f"PASS saved evidence (declared release {provenance['release_tag']}; Git tag not resolved): "
              f"30 source-matched trials; 30,000 exact-value checks; "
              f"{workflow['tests_run']} tests with zero skips; figure and review hashes.")
    except (OSError, ImportError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Cannot audit release: {exc}. Use the complete requirements-dev.txt environment.\n')


if __name__ == '__main__':
    main()
