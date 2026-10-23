# Study use cases and extension boundaries

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

Shared KV Storage is an executable framework for learning how placement choices affect a running storage system. Its applications are lab exercises, assignment comparisons, HTTP client practice and controlled local demonstrations. It does not seek a new research result or provide a production database.

## Three guided exercises

| Exercise | Change | Observe | Explain |
|---|---|---|---|
| Membership growth | Compare policies with the same topology and keys. | Owner changes, acknowledged transfers and old/new owner matrices. | Modulo can move keys among old nodes; fixed-token consistent hashing only captures intervals for the joining node. |
| Placement balance | Sweep V with fixed node identities and keys. | Every node's key count, population CV and max/min ratio. | More tokens can improve balance across layouts, but a deterministic sequence need not improve monotonically. |
| A hot item | Compare zero extra reads with positive `additional_hot_reads`. | Counters before/after hot traffic; unchanged key inventory. | Key balance and request balance differ; one key still has one owner. |

Begin with `configs/quick.toml`. Write down the question, controls and expected qualitative behavior before running it. Use `configs/study.toml` for the course-sized comparison. The [configuration guide](configuration.md) explains personal profiles.

## Practice building a client

Launch the demo and use the [API](api.md) to store a small text lookup table. Inspect each key's owner before and after a join. This is useful for learning router-mediated requests and observing migration. Values disappear when storage processes stop.

## Explore failure semantics

The migration tests demonstrate a lost copy acknowledgment, an in-flight old-owner Get, and a cleanup failure after publication. Read [architecture.md](architecture.md) alongside `tests/test_framework.py`. Recovery respects whether the new ownership map has been published; it cannot reconstruct values lost in a storage-process crash. Passing one injected-failure scenario does not establish behavior for every distributed failure.

## Make a bounded extension

- `Placement` maps keys to single physical owners and exposes token coverage.
- `Router` owns membership, counters, forwarding and verified migration.
- `Storage` holds local text values and knows no peers.
- `Cluster` owns subprocess startup, readiness and cleanup.
- The study driver uses HTTP and records observations for separate analysis.

Appropriate extensions include another single-owner placement policy, a seeded read distribution, or a key-size exercise. A policy needs an ownership definition, registration in validation/CLI choices, invariant tests and migration behavior. A workload needs recorded parameters, a reproducible sequence and correct denominators. There is no plugin loader or promised public subclass API.

Replication, consensus, WAN benchmarking and availability guarantees would change the learning objective and require a separate design.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Documentation map](README.md) · Next: [Configuration](configuration.md)
<!-- reading:end -->
