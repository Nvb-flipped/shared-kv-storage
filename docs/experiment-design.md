# Experiment design

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

The question is how placement changes physical balance, transferred keys and request concentration when a fourth node joins. The unit for timing is one fresh five-process cluster. Individual keys and reads within a cluster are observations, not independent timing replicates.

Every case uses the same 1,000 deterministic key/value pairs, the same uniform-read sequence and a three-to-four-node join. The treatments are modulo and consistent hashing with V=1,2,4,8,10,16,32,64,128. Three rounds create 30 fresh trials. Settings are randomized within each round using Python's seeded generator; the executed schedule and Python version are saved, not inferred from the seed alone.

Controls include the single router, sequential HTTP driver, stable A/B/C/D identities, loopback transport, dataset, request count and exact-value verification. No artificial teaching delay or unrelated demonstration is run during measured trials. The source root is WSL's Linux filesystem. Four stores run from startup, but only A/B/C belong to the original placement.

The response measures are before/after counts, max/min ratio, population CV, changed-owner fraction, acknowledged and verified copies, elapsed join time and a calculated logical item size. Every value is independently read after join, and physical inventories must contain exactly one correctly placed copy. The comparison uses actual router responses; the experiment client does not calculate placement.

After loading and verification, reset counters and send 1,000 uniform reads. Then add 500 requests to the first dataset key without changing stored keys. Compare cumulative 1,000/1,500-read counts and unchanged key counts. This isolates the effect of extra hot traffic. It is a request-distribution experiment, not a throughput benchmark.

Stable token identities make placement deterministic across the three repeats. Means and sample standard deviations describe local join-time variation; they do not provide independent layout samples or generalize to WAN capacity. The L01 node-load boxplot summarizes four physical nodes per setting and shows every point. Its boxes are descriptive summaries, not confidence intervals. The max/min ratio needs a positive minimum; JSON uses null for undefined/infinite cases.

The project is a course comparison of established mechanisms. It does not seek novelty, fit a universal optimal V or claim full Dynamo behavior. The [metric definitions](metrics.md) separate random-layout expectations, fixed-ring coverage, actual owner changes and measured transfer evidence.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Math and metrics](metrics.md) · Next: [Measured results](results.md)
<!-- reading:end -->
