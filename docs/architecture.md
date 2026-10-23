# Framework architecture

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

<!-- contents:start -->
On this page: [Configuration and study lifecycle](#configuration-and-study-lifecycle) · [State and ownership](#state-and-ownership) · [Migration with readable Gets](#migration-with-readable-gets) · [Failure and recovery](#failure-and-recovery) · [Runtime controls and observation](#runtime-controls-and-observation)
<!-- contents:end -->

The system is the network of processes. `sharedkv/cli.py` and `sharedkv/experiment.py` implement the two HTTP clients; the original top-level scripts delegate to them. Neither imports the router, membership table or placement module. The router computes ownership on demand, and each storage process holds only its own `key -> text value` dictionary.

```text
CLI client -------- HTTP ----> Router :8000 ---- HTTP ----> A :5101
Experiment client ------------>     |                    > B :5102
                                   |                    > C :5103
                                   +--------------------> D :5104 (joins)
```

`sharedkv/transport.py` provides bounded JSON messages and consistent errors. `storage.py` holds local values. `router.py` manages membership, counters and migration, using integer placement from `placement.py`. `terminal.py` formats responses without choosing owners. `cluster.py` launches processes; clients do not import it. Runtime code uses only Python's standard library.

## Configuration and study lifecycle

`sharedkv/config.py` validates TOML before launch; CLI flags override the relevant settings. The demo has predictable ports, while isolated trials ask the OS for distinct loopback ports. Selection and binding are separate operations, so an external process can still race for a port; startup then fails and cleans up owned children instead of stopping another application.

The diagram shows the default topology. Initial IDs, joining ID, ports and readiness deadline are configurable. `Cluster` starts each store and the router with the same Python interpreter, verifies responding PIDs, and closes owned children on normal exit, startup failure or interruption. It launches modules rather than absolute source-file paths, so a wheel installation also works.

The orchestrator records the effective settings and randomized schedule before collection. Each trial uses fresh processes and stops them before saving its completed receipt. Failed/interrupted manifests retain completed cases and cannot be analyzed as complete. `sharedkv/analysis.py` validates observations before deriving summaries; `plotting.py` is imported only when figures are requested. Reporting never changes membership or recollects measurements.

## State and ownership

In the demo, A/B/C start as members and D is a waiting independent process, registered only when it joins. Custom profiles choose another initial set and one waiting ID. IDs sort lexicographically. The router has no persistent key/value cache or global key-to-owner table. Migration keeps a temporary list of changed keys and expected value digests.

`membership_version` starts at 1 and increases when a verified join is published. `placement_revision` increases on mode/V changes. Records have no versions. Put replaces the current text value and acknowledges its single owner. [Metric definitions](metrics.md) retain the placement, CV, transfer-matrix and workload mathematics.

## Migration with readable Gets

1. Validate an unused ID/address, matching storage identity and empty destination. Pause writes and register the candidate as `joining`.
2. Keep the old map active. Enumerate keys, check old physical ownership and compare old/new owners inside the router.
3. Copy changed keys while retaining sources. Count acknowledged writes and retain original-value digests.
4. Read every changed destination and compare its digest. Failure leaves writes paused.
5. Wait for in-flight old-owner Gets, then publish the verified map and membership version together. New Gets use the new map.
6. Delete obsolete sources, mark the migration idle and resume writes. Return counts, elapsed seconds and a labeled item-size estimate.

Phases are `idle -> preparing -> migrating -> verifying -> done -> idle`, with `failed` on an error after preparation. A mutation guard excludes Put, another join, reconfiguration and flush. Put receives 503; competing administrative changes receive 409. A separate read gate protects each Get through its storage response and the short publication step. Gets remain available during copying and verification. This is a centralized teaching protocol, not Dynamo's full online availability protocol.

## Failure and recovery

Before publication, recovery removes staged destination copies, retains the old map and removes the failed candidate registration. Staging is recorded before copying so a lost acknowledgment can be rolled back. After publication, recovery finishes source cleanup and retains the new map. Unpause only after cleanup and member-health checks succeed. Recovery does not recreate data lost in a crashed storage process.

An unreachable-node request marks it `down` and returns an error. The node remains in placement; there is no failure detector or automatic eviction. Stores and router are volatile. Router/laptop failure, lost storage contents after restart and external direct writes to stores are outside the correctness assumptions.

## Runtime controls and observation

Mode/V changes rebuild placement without migrating data. If data exists, `reload_required` rejects Put/Get until explicit `flush` and reload. A partially failed flush retains that guard. Changing mode alone never deletes values.

During migration, physical counts can include staged copies. Use idle snapshots before and after a join for balance comparisons. Client request counters include forwarded Put/Get attempts and misses, and exclude inventory, migration and ring checks. [API contracts](api.md) define the interfaces. [Specification decisions](spec-decisions.md) explain corrections to the supplied pseudocode.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Reproduction](reproduction.md) · Next: [API reference](api.md)
<!-- reading:end -->
