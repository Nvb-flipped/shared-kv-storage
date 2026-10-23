# Plan and interpret a study exercise

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

The framework answers a bounded question: how do placement policy and token count change physical key balance, key transfers and request concentration during one local join? It demonstrates established mechanisms. It does not seek novelty or a general optimal setting.

## Before running

1. State the question and choose a profile. Start with a small run, then increase the workload only if that helps answer it.
2. Fix the controls: initial/joining IDs, synthetic dataset size, uniform-read count, hot-read count and seed. Vary policy or V deliberately.
3. Choose repetitions and inspect `--dry-run`. Each round randomizes the requested setting order and creates a fresh cluster per setting.
4. Choose a new output directory. Keep the effective configuration and raw observations with the report.

The study supports arbitrary distinct uppercase node IDs and one join. It always uses the same deterministic key/value generator. The seed controls the uniform reads and run order, not token placement. A new seed alone is not a new ring layout. Node IDs determine tokens through SHA-256.

## Measurement and verification

A fresh cluster is the timing unit. Keys, reads and physical nodes within it are observations, not independent timing replicates. Every trial loads the synthetic records, captures the router's owner maps, adds the waiting store, independently reads every value, and checks physical inventory. The HTTP experiment client does not compute placement.

Migration counts must agree with changed owners and verified destinations. The transfer matrix conserves the original key total and its row/column margins agree with physical before/after counts. Uniform-read counters are reset after loading and verification. Extra hot-key reads must affect only that key's owner while key counts stay unchanged. Zero extra reads is a supported control.

The join timer includes preparation through old-copy cleanup and excludes later exhaustive verification. `estimated_item_bytes` is a logical serialization estimate, not measured network traffic. The workload measures request distribution; it is not a concurrent throughput or latency benchmark.

## Read the report

The report includes CV, max/min ratio, movement, every join timing, means, ranges and sample SD. Sample SD is unavailable for one trial. Max/min is unavailable when a node has zero keys; do not replace it with a misleading finite value. Per-node points describe a finite set of physical counts, not a confidence interval.

Read movement together with balance: fewer moved keys does not guarantee more equal placement. Compare a fixed ring's coverage to its measured key share before comparing either with an ideal random-layout expectation. More V need not improve every fixed-ID setting. One hot key still has one owner regardless of V.

Repetitions with fixed identities and keys measure local process/timing variation. They do not sample independent layouts or establish behavior on other machines, network links or datasets. Keep interpretation descriptive for the default small study; adding p-values cannot repair missing independent units. General claims would need a different experiment design.

## Figure design and interpretation

The visual argument is that movement, key-count spread and request concentration measure different tradeoffs. The movement plot is the main comparison; balance and per-node plots explain it, transfer matrices show destinations, and the request plot distinguishes key shares from observed traffic. Timing plots show all fresh-process repetitions and their means without inferential error bars. The source is each run's validated summary and raw trials.

The Matplotlib exports use a white background, restrained colours, redundant markers/hatching, light grids and sans-serif editable vector text. Typical comparison panels are 183 mm wide; topology-dependent panels may grow to keep labels readable. SVG/PDF are the primary line-art exports; 300 dpi PNG is a review preview, with no TIFF submission requirement for this study framework. These choices borrow scientific-figure conventions without claiming journal submission compliance.

All settings appear in movement, CV, per-node and timing plots. The request figure shows one explicitly labelled illustrative setting; the transfer figure shows modulo when present and that same setting. This avoids an unreadable grid for large V sweeps. All settings' hot-owner shares appear in the report, and full counters/matrices remain in raw JSON. Captions declare each denominator, selected setting, replicate unit and reference assumption. Run the visual QA helper and inspect original and grayscale outputs for clipping, overlap and distinguishability.

## Compare two custom profiles

Use separate output directories, retain both manifests, and explain what changed. If policies are compared, keep topology, dataset and request sequence fixed. If topology or dataset size changes, treat that as a separate exercise and use the correct denominators. Do not combine partial or incompatible runs into one summary.

The [metric definitions](metrics.md) state the mathematical assumptions. The [configuration guide](configuration.md) and [reproduction guide](reproduction.md) connect those assumptions to executable settings.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Math and metrics](metrics.md) · Next: [Measured results](results.md)
<!-- reading:end -->
