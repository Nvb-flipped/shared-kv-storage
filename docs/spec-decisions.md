# Applying the primary specification

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

`refined_spec.md` is the primary source. Its original formatting and illustrative numbers are preserved. The framework follows its pure-client architecture, single-owner text model, runtime controls and read-available migration. These corrections make the requirements consistent.

| Specification point | Implemented decision |
|---|---|
| Normalized-hash pseudocode versus the 75% modulo expectation | Use integer SHA-256 remainder. `floor(u*N)` is range partitioning, with different movement behavior. Integer hashing also follows Paco's later clarification. |
| Delete old copies before publishing while allowing Gets | Verify, wait for in-flight old-owner Gets, publish, then delete. This closes the read gap. |
| The new token's predecessor described as the former owner | A token captures its predecessor interval; that interval previously belonged to the next old token clockwise. |
| Recover by only clearing a failed flag | Roll back unpublished staging or finish published cleanup. Unpause only after cleanup and member-health checks succeed. |
| Mode/V rebuild with no migration | Leave data in place and require explicit flush/reload before further Put/Get. Inspection remains available. |
| Unequal token counts in an equal-V example | Give every node exactly V tokens; their coverage fractions may differ. Positions and key hashes are integers. |
| Earlier record-version/replication implementation | Remove it from active source and deliverables. This primary spec excludes both. Virtual nodes supply the implemented bonus; no replication bonus is claimed. |
| Earlier 70% hot-key workload | Use 1,000 uniform reads and 500 additional hot-key reads, with cumulative denominators 1,000 and 1,500. |
| Example project5 subfolder | Keep the source at the repository root, with no project5 subfolder. A clone runs independently of the original directory on Linux, WSL or Windows. |

Two convenience endpoints keep experiments behind the router: `GET /keys` exposes every key's owner and physical hosts; `POST /admin/flush` coordinates a reset. Node removal is outside scope, so `leaving` is not an active state. IDs are single uppercase letters, matching the token display, and V is an integer from 1 to 1024. The study profile includes the specified 1/10/128 and the earlier doubling sequence; smaller or custom profiles choose other settings. Configurable topology and workload parameters preserve the same one-join protocol.

Dynamo supplies the partitioning concepts. MIT's shard lab informs the separation of transfer and configuration changes. Neither requires this course framework to implement consensus, replication, quorums or durable recovery.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Assessment map](assessment.md) · Next: [Attribution](ai-use.md)
<!-- reading:end -->
