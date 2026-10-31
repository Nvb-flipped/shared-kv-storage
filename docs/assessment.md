# Assessment and evidence map

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

This project follows the CISC3010 Project 5 scope. It implements established partitioning mechanisms; novelty, production deployment and full Dynamo replication are not goals. The presentation was already delivered before this maintenance pass. The repository work below concerns the remaining implementation, experiment, report and reproduction evidence. Private slides are not rebuilt or committed.

## Rubric

| Criterion | Weight | Evidence to inspect |
|---|---:|---|
| Working system and correctness evidence | 30% | Independent store/router PIDs, both placement policies, real join transfers, exact-value/physical-owner checks and deterministic concurrency/recovery tests. See [architecture](architecture.md), [scope](scope.md) and `tests/`. |
| Experimental design and interpretation | 25% | Same dataset and request sequence, fresh-process timing repetitions, randomized setting order, hot-key control, descriptive limits and actual-ring coverage. See [experiment design](experiment-design.md), [metrics](metrics.md) and [course report](report.md). |
| Presentation and individual understanding | 25% | Already delivered. Delivery and individual understanding are assessed by the instructor; they cannot be certified from repository tests. |
| Reproducibility and documentation | 10% | An immutable version, complete development requirements, fresh output directories, source/raw/export hashes, zero-skipped-test validation and installed-package exercises. See [reproduction](reproduction.md). |
| Report quality and connection to the reading | 10% | A bounded question, traceable tables/figures, clear measurement terminology, interpretation and limitations, Dynamo/MIT connections and [AI-use disclosure](ai-use.md). |

## Required scope

| Requirement | Implementation and verification |
|---|---|
| Client/router and at least three independent storage processes | The default demo starts four stores and one router. A/B/C are active and D waits. Managed startup checks owned process identities and shutdown. |
| Put and Get | Plain text overwrite/read through HTTP. Tests include Unicode, empty values, misses, proper error envelopes and CLI continuation/exit codes. |
| Modulo and consistent hashing | Stable integer SHA-256, sorted-ID remainder and clockwise tokens with wraparound. Boundary and finite invariant tests cover the definitions. |
| Key owners and node counts | `owner`, `keys`, `stats` and `ring`; inventory distinguishes routed owner from actual physical hosts. |
| Add a node and transfer reassigned keys | Copy, destination verification, protected publication and source cleanup. Changed-owner counts must equal acknowledged and verified copies. |
| Pause writes during migration | Explicit 503 response. Deterministic tests also exercise readable Gets, in-flight reads, lost acknowledgments and recovery boundaries. |
| Same keys for balance and movement | Every setting uses the same deterministic records and seeded background read sequence. |
| Verify every value after migration | Exhaustive original-value reads plus exactly one physical owner per key, after source cleanup. |
| Frequently accessed key | Reset counters after verification, sample background reads, add hot reads, and require unchanged key counts and exact owner-specific counter deltas. |
| Optional extension | Virtual nodes, including V=1/10/128 and the doubling sweep. The supplied rubric specifies virtual nodes or replication; no replication bonus is claimed. |

## Review findings addressed

The maintenance pass adds the missing HTTP 408 contracts and live schema checks, rejects duplicate canonical initial addresses, extends terminal styles to custom uppercase IDs, reports exact counts/transfers/logical sizes, and compares observed movement with actual ring coverage. Figures use lighter fills, outlined marks, finite-population boxes and explicit denominators. Full development validation includes all plotting tests and rejects skips.

The independent closure review also led to an identity-checked status probe after transient failures and a direct demo-to-final-results route. The final release check authenticates saved evidence; the Git tag is verified separately during publication.

Presentation-only findings from the earlier review are closed from this maintenance scope because delivery is complete, not because the old private builder was repaired. Evidence of a completed presentation is the user's confirmation; no new claim about its awarded score is made.

## Submission snapshot

Use the `v0.3.1` tag for the assessed runtime and `results/final/` for raw trials, figures and provenance. The [UM report](../submission/report.pdf) supplies four main pages and one reference page; the [submission guide](../submission/README.md) covers its LaTeX source and source-archive packaging. These are later documentation additions to the same measured runtime. The longer [course report](report.md) retains evidence links. The [platform validation evidence](../results/validation/v0.3.1/README.md) records actual dependency versions and source hashes. Keep later exploratory runs under ignored `results/runs/` rather than silently replacing the assessed dataset.

Passing finite checks supports the stated local single-owner system. It does not establish all possible failure schedules, restore volatile data after a crash, or guarantee an instructor's grade.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Requirements and evidence](scope.md) · Next: [Spec decisions](spec-decisions.md)
<!-- reading:end -->
