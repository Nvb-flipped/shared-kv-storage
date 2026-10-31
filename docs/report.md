# Sharded key-value storage course report

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

<!-- contents:start -->
On this page: [Question and scope](#question-and-scope) · [Connection to the reading](#connection-to-the-reading) · [Design and correctness](#design-and-correctness) · [Experimental method](#experimental-method) · [Results](#results) · [Reproduction and evidence](#reproduction-and-evidence) · [Changes after presentation feedback](#changes-after-presentation-feedback) · [Limits and interpretation](#limits-and-interpretation)
<!-- contents:end -->

The [UM report PDF](../submission/report.pdf) presents this material in four main pages plus one reference page, using 12 pt Latin Modern. Its [LaTeX source and submission guide](../submission/README.md) provide the build and packaging commands. This Markdown page retains the longer reading route and evidence links.



## Question and scope

How do modulo and consistent hashing differ when one storage node joins, and how does the number of virtual nodes affect the balance/movement tradeoff? A second question separates placement from demand: can evenly distributed keys still produce concentrated requests?

The framework answers these questions with independent local storage processes and HTTP requests. It is a single-owner, volatile text store coordinated by one router. It implements established mechanisms for CISC3010 Project 5, with virtual nodes as the optional extension. The presentation was already delivered; this report covers the assessed software, measurements and reproduction evidence.

## Connection to the reading

[Dynamo, section 4.2](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf) motivates incremental scaling through consistent hashing. A physical host occupies multiple token positions to reduce the coverage variability of one position. This project implements that partitioning idea using stable integer SHA-256 tokens.

Several decisions simplify Dynamo. A central router owns the configuration, every key has one owner, and writes pause during migration. There is no replication, quorum, vector clock, gossip or automatic data repair. The project therefore does not claim Dynamo's availability or durability. Full replication is outside the primary specification.

[MIT 6.5840 Lab 5](https://pdos.csail.mit.edu/6.5840/labs/lab-shard1.html) is an advanced reference for separating data transfer from configuration publication. This router copies and verifies reassigned values, protects in-flight reads while publishing, then removes old copies. The lab's Raft-replicated groups and controller recovery are not additional minimum requirements here.

## Design and correctness

The default cluster has independent A/B/C stores, an empty waiting D and a router. The CLI is a pure HTTP client. Stores know only local values. Modulo indexes sorted IDs using an integer remainder. Consistent hashing selects the first token clockwise at or after the key hash, wrapping at the end.

A successful join performs real destination writes and read-back checks. Changed owners must equal acknowledged copies and verified destinations. After publication and cleanup, the experiment reads every original value and requires exactly one physical copy at the routed owner. Computing a new mapping alone is insufficient.

Puts receive 503 during migration. Gets use the old map during copying and verification; publication waits for in-flight old-owner reads before cleanup. Deterministic barrier tests exercise these overlaps, lost acknowledgments and cleanup recovery. Ordinary misses return a proper error and CLI exit code, while the interactive prompt continues. Duplicate canonical initial addresses are rejected so several names cannot masquerade as independent stores.

The [architecture](architecture.md) and [API reference](api.md) define the protocol. Recovery cleans staging or finishes cleanup; it cannot reconstruct volatile data lost in a storage crash.

## Experimental method

The complete profile uses the same 1,000 deterministic key/value pairs for every setting. A/B/C grow to A/B/C/D. The settings are modulo and consistent hashing with V=1,2,4,8,10,16,32,64,128. Each runs in three fresh clusters; order is randomized within each round using seed 3010.

Every trial verifies all original values and physical hosts after joining. Counters then reset. The driver sends 1,000 seeded uniform reads followed by 500 extra reads to the first key. It requires unchanged key counts and exactly 500 additional requests at that key's owner. Inspection and migration are excluded from workload counters.

A fresh cluster is the timing unit. Restarting the same IDs does not produce a new token layout. Means, ranges and sample SD describe local timing variability; keys, tokens and node points are not independent timing repetitions. No confidence interval across layouts is claimed.

The join timer covers preparation through source cleanup, excluding later exhaustive verification. Copy counts and seconds are measured. Estimated item bytes are calculated logical UTF-8 JSON sizes, excluding HTTP framing, verification and deletion traffic. [Metrics](metrics.md) defines every denominator and empty-data convention.

## Results

The final comparison is under `results/final/`. Its [analysis](../results/final/analysis.md) includes physical counts, movement/transfer agreement, logical sizes, actual ring coverage, hot-owner shares and every timing observation. Raw trials and source digests remain the primary evidence.

<!-- final-results:start -->
| Setting | After A/B/C/D (keys) | CV after | Reassigned | Copied / verified | Join mean (s) |
|---|---|---:|---:|---:|---:|
| Modulo | 246/247/254/253 | 0.014 | 743 (74.3%) | 743 / 743 | 2.767 |
| Consistent V=1 | 119/351/469/61 | 0.666 | 61 (6.1%) | 61 / 61 | 0.239 |
| Consistent V=2 | 268/404/184/144 | 0.398 | 144 (14.4%) | 144 / 144 | 0.534 |
| Consistent V=4 | 189/390/315/106 | 0.439 | 106 (10.6%) | 106 / 106 | 0.433 |
| Consistent V=8 | 171/213/455/161 | 0.480 | 161 (16.1%) | 161 / 161 | 0.596 |
| Consistent V=10 | 244/216/319/221 | 0.165 | 221 (22.1%) | 221 / 221 | 0.868 |
| Consistent V=16 | 296/245/270/189 | 0.158 | 189 (18.9%) | 189 / 189 | 0.768 |
| Consistent V=32 | 294/286/239/181 | 0.180 | 181 (18.1%) | 181 / 181 | 0.679 |
| Consistent V=64 | 287/327/218/168 | 0.245 | 168 (16.8%) | 168 / 168 | 0.667 |
| Consistent V=128 | 267/298/210/225 | 0.139 | 225 (22.5%) | 225 / 225 | 0.874 |

All 30 trials passed every original-value and physical-owner check. The timing column is newly measured on this WSL machine; it is not copied from the historical reference.
<!-- final-results:end -->

Movement must be interpreted with balance. A fixed consistent ring may move few keys because the new node captures little hash space, while retaining a poor distribution. Increasing V can improve coverage balance but need not improve every step for fixed IDs. Modulo can balance counts well while moving keys between old nodes.

The ideal three-to-four modulo reference is 75% under uniform residues. The ideal consistent-hash mean is 25% across exchangeable random layouts with equal token counts. A particular ring's joining-node coverage is a separate conditional quantity. The coverage table makes that distinction explicit rather than treating 25% as a pass/fail target.

One hot key still has one owner regardless of V. Its additional reads concentrate at that owner while key counts remain fixed. This experiment measures request distribution, not concurrent throughput or production latency.

## Reproduction and evidence

Use the immutable `v0.3.1` source tag and install `requirements-dev.txt` for the complete check. Full validation executes every test, including real SVG/PDF/PNG exports, rather than counting skipped plotting tests as a complete pass. It also exercises both OpenAPI contracts, real timeout errors, CLI continuation, isolated package installation, custom IDs and a one-key/empty-node edge case.

The [reproduction guide](reproduction.md) gives the commands. The [assessment map](assessment.md) maps each criterion to evidence. The [figure guide](figures.md) explains source data, geometry checks and grayscale/color-vision sheets. Runtime and numeric reports still need no third-party packages.

Historical measurements retain their original provenance and are not relabelled as fresh results. New timings need not equal previous timings; controlled placement and verification invariants must agree. Actual dependency versions and raw outputs are retained with validation evidence.

## Changes after presentation feedback

The comparison baseline is the 23 October public revision `a245768`. Following presentation feedback, the project gained TOML profiles, one workflow entry point, clearer dependency installation and configurable workloads. API handling now covers more malformed requests and stalled bodies. A fresh source-matched comparison, explicit actual-ring coverage, an aligned architecture diagram and documentation navigation make the result easier to inspect and reproduce. Hashing, virtual nodes, migration and the original comparison already existed at the baseline; these are not claimed as later additions.

Paco chose the experimental settings, directed the flexible framework design and specified API refinements for exception cases. The initial mathematical derivations were completed by Paco; Codex helped refine notation, formalize the exposition and qualify the assumptions. Implementation, debugging, tests and documentation also received Codex assistance, recorded in the [assistance statement](ai-use.md).

## Limits and interpretation

The observations support the configured local join under documented assumptions. They do not establish behavior across independent random layouts, arbitrary failure schedules, WANs or other machines. No universal optimum V is inferred. Values are synthetic, requests are sequential, and storage/configuration are volatile.

Within this scope, every minimum system and experiment requirement is directly testable. Virtual nodes provide a concrete extension without unrelated production features. Assistance and primary-source attribution are recorded in [AI-use disclosure](ai-use.md).

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Experiment design](experiment-design.md) · Next: [Figure guide](figures.md)
<!-- reading:end -->
