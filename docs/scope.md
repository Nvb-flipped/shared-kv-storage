# Requirements and evidence

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

The primary spec is [refined_spec.md](../refined_spec.md), applied with the [documented correctness decisions](spec-decisions.md). The current framework has one owner, plain text values, integer hashing and a pure CLI client. Replication and record versions are excluded.

| Requirement | Implementation and evidence |
|---|---|
| Independent processes | `storage_node.py`, `router.py` and `sharedkv/cluster.py`; four storage PIDs and a distinct router PID in every raw trial and rehearsal. |
| Put/Get through a router | `/put` and `/get`; `client.py` only calls HTTP and formats responses. Storage holds plain text values. Tests cover overwrite, empty text, Unicode and misses. |
| Modulo and consistent hashing | Router-only `sharedkv/placement.py`; integer SHA-256 remainder or first clockwise integer token. Fixed-membership and token-order tests. |
| Runtime mode and V controls | `/admin/placement` and `/admin/vnodes`; no implicit migration/deletion. Populated data requires flush/reload. Tests cover the guard and reloading. |
| Owners, key counts and traffic | `owner`, `keys`, `stats` and `/ring`; routed versus physical hosts, counts, shares and separate inspection probes. |
| Node registration and membership version | `addnode D 127.0.0.1:5104` with the quickstart port range; validated identity/address/empty destination, version 1 to 2 after verification. |
| Actual reassigned-key transfer | Router copy/verify/publication/cleanup protocol; both modulo many-to-many and consistent-to-D transfers. Changed owners equal acknowledged and verified destination counts. |
| Paused writes, readable Gets | 503 Put while migrating; Gets read old owners until verified publication. Tests use a deterministic phase barrier; the operational rehearsal also checks real HTTP behavior. |
| Same dataset and full verification | Thirty fresh trials use identical 1,000 values and request digests. Every value and physical owner is checked after migration. |
| Key balance versus hot traffic | Reset after verification; 1,000 uniform reads then 500 extra hot-key reads. Key counts stay unchanged and exactly 500 additional forwards reach its owner. |
| Virtual-node bonus | V=1,2,4,8,10,16,32,64,128 includes the specified 1/10/128; report both max/min and CV without a monotonicity or universal-optimum claim. |
| Proper API reference | `docs/api.md`, two generated OpenAPI files and live response/schema validation. No web UI is required. |
| Failure behavior | Observed unreachable stores become down without eviction. Tests cover lost-copy acknowledgments and post-publication cleanup failure. Recovery does real cleanup before unpausing. |

Run `bash tools/reproduce.sh` for the complete WSL reproduction. `results/framework/environment.json` records the randomized schedule, interpreter, platform and source hashes. Trial files contain full router-returned owner maps, token data, counters, PIDs and exact verification results. The clients do not implement a second placement model.

Gate A covers processes and Put/Get, B placement and observation, C migration, and D controlled experiments. Their evidence is tested and recorded. Gate E has a [CLI runbook](demo.md) and operational rehearsal. Slides are kept locally and are not distributed with the source repository. A scripted rehearsal does not establish that Paco has delivered a timed spoken explanation; that remains a human action. The final report and feedback-driven revisions are outside this preparation stage.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Demonstration](demo.md) · Next: [Spec decisions](spec-decisions.md)
<!-- reading:end -->
