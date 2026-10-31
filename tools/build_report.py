"""Build the four-page course report from the saved, source-matched study."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def results_table():
    from sharedkv.analysis import load_run, summarize
    manifest, trials, _ = load_run(ROOT/'results/final', require_current=True)
    rows = summarize(manifest, trials)
    lines = [r'\begin{center}', r'\captionof{table}{All 1,000-key settings; three fresh-process timings per fixed layout. Join duration is mean $\pm$ sample SD. Reassigned, copied and verified counts agree.}',
        r'\label{tab:results}', r'\vspace{3pt}', r'{\fontsize{10.5}{12.5}\selectfont',
        r'\setlength{\tabcolsep}{5pt}', r'\begin{tabular}{@{}lr r r r@{}}',
        r'\toprule', r'Setting & After A/B/C/D & CV & Moved & Join (s) \\', r'\midrule']
    for row in rows:
        # Counts come directly from the matching raw trial, not a hand-entered table.
        mode, vnodes = row['mode'], row['vnodes_per_node']
        raw = next(t for t in trials if t['mode'] == mode and t['vnodes_per_node'] == vnodes)
        counts = raw['placement_balance_after']['key_counts']
        name = 'Modulo' if mode == 'modulo' else f'Consistent $V={vnodes}$'
        values = '/'.join(str(counts[n]) for n in ['A', 'B', 'C', 'D'])
        lines.append(f"{name} & {values} & {row['placement_balance_after']['cv']:.3f} & "
            f"{100*row['reassignment']['fraction']:.1f}\\% & "
            f"${row['join_seconds']['mean']:.3f} \\pm {row['join_seconds']['sample_sd']:.3f}$ \\\\")
    return '\n'.join([*lines, r'\bottomrule', r'\end{tabular}}', r'\end{center}', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=ROOT/'.runtime/report-build')
    args = parser.parse_args()
    compiler = shutil.which('pdflatex')
    if not compiler:
        parser.exit(1, 'pdflatex is required only to rebuild the report. Install TeX Live with Latin Modern.\n')
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    try:
        (ROOT/'submission/results-table.tex').write_text(results_table(), encoding='utf-8', newline='\n')
        command = [compiler, '-interaction=nonstopmode', '-halt-on-error', '-no-shell-escape',
            '-file-line-error', '-output-directory='+str(build), 'report.tex']
        for run in range(2):
            result = subprocess.run(command, cwd=ROOT/'submission', stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=90)
            (build/f'pass-{run+1}.txt').write_bytes(result.stdout)
            if result.returncode:
                parser.exit(1, f'LaTeX failed; inspect {build}/pass-{run+1}.txt.\n')
        log = (build/'report.log').read_text(encoding='utf-8', errors='replace')
        forbidden = ['Overfull', 'undefined references', 'undefined citations', 'Missing character:']
        if any(warning in log for warning in forbidden):
            parser.exit(1, f'Layout/reference warning; inspect {build}/report.log.\n')
        shutil.copyfile(build/'report.pdf', ROOT/'submission/report.pdf')
        print('Built submission/report.pdf; run tools/check_submission.py before submission.')
    except (OSError, ValueError, KeyError, StopIteration, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f'Cannot build report: {exc}\n')


if __name__ == '__main__':
    main()
