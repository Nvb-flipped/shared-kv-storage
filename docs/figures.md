# Figure design and validation

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

<!-- contents:start -->
On this page: [Reading the six figures](#reading-the-six-figures) · [Visual choices](#visual-choices) · [Rebuild and check](#rebuild-and-check)
<!-- contents:end -->

The figures explain three different effects: how many keys move, how those keys are spread across physical nodes, and how one hot key concentrates requests. Timing is a separate local cost. A visually small movement is not automatically a balanced placement, and a balanced key count is not a balanced request workload.

## Reading the six figures

| Figure | Encoding and interpretation |
|---|---|
| `movement` | Every setting's reassigned fraction and exact count. The modulo and random-ring reference lines are ideal-model expectations, not required finite-sample outcomes. Numeric labels occupy a separate column so reference lines do not cross them. |
| `balance` | Paired before/after population CV. Marker shape identifies the stage; the thin connector links the two observations for the same setting. These are descriptive quantities, not confidence intervals. |
| `node-loads` | A population boxplot with every physical node marked. The box spans the interquartile range, the median is shown, and whiskers include the full minimum/maximum. It describes the finite node population, not independent trials. |
| `requests` | Key, background-read and combined-read shares for the explicitly named illustrative setting. Different totals are printed in the legend. Light fills, outlines and distinct bar-top markers provide redundant cues. All settings remain in the report and raw observations. |
| `transfers` | Old owners form rows and new owners form columns. Cells contain counts and percentages of all original keys, including stayed keys on the diagonal. Comparable panels share a light sequential scale and equal plot-area geometry. |
| `join-time` | Every fresh-process timing is a circle; the open diamond is its setting's mean. No timing observation is hidden, and no confidence interval over token layouts is implied. |

The report also gives the joining node's exact ring coverage. It is calculated from recorded integer intervals and is distinct from both finite-key movement and the random-layout mean. This comparison is available without installing plotting packages.

## Visual choices

The style borrows restrained typography, direct labels, RGB output and accessible color choices from the [Nature figure guide](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/) and its [panel export guidance](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/). This is a course report, not a journal submission or a claim of publisher certification.

Plots use white backgrounds, light blue/orange/green fills, clear outlines and consistent sans-serif text. The transfer scale has no dark navy endpoint. Node marks use stable colors with distinct shapes and letters; large memberships may repeat hues, so color is never the only identifier. Terminal colors use the same stable node mapping and preserve letters, patterned bars, counts and percentages.

SVG and PDF retain selectable text. PNG is exported at 300 dpi. Main panels are about 183 mm wide, with topology-dependent expansion when needed. The exported size, rather than the size of an on-screen preview, determines legibility. The font floor and panel geometry are checked on the actual outputs. No decorative 3-D, synthetic uncertainty, smoothing or generated data is used.

## Rebuild and check

Install `requirements-dev.txt` for every check below. `requirements-figures.txt` is sufficient just to generate plots.

```bash
python -m sharedkv report --input results/runs/my-study --plots --require-current-source
python tools/check_figures.py --input results/runs/my-study
python tools/visual_qa.py --input results/runs/my-study
```

The numeric report is derived from validated raw trials. `figure-manifest.json` records hashes of the summary, all 18 exports and six render-time layout receipts. The figure checker verifies those hashes, author metadata, a 5 pt PDF glyph floor, selectable text, page bounds and text overlap. Geometry tests also confirm that known clipping, unequal comparable panels and overlapping PDF labels are rejected.

The visual helper writes original, grayscale, protanomaly, deuteranomaly and tritanomaly contact sheets. Open every sheet and inspect the individual figures at their intended size. Confirm that all node marks, text, denominators and timing points remain legible. Simulations aid review; neither a palette name nor a passing geometric check proves accessibility for every viewer.

Full `tools/validate.py` runs these checks on a normal study and a one-key, zero-extra-hot-read edge case. It requires every test to execute. Review receipts should name the exact source, inputs, inspected outputs and remaining limits; a passing old receipt must not be relabelled as a fresh run.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Course report](report.md) · Next: [Historical results](results.md)
<!-- reading:end -->
