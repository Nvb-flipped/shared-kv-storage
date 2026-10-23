# Requirements and evidence

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

The primary spec is [refined_spec.md](../refined_spec.md), applied with the [documented correctness decisions](spec-decisions.md). The current framework has one owner, plain text values, integer hashing and a pure CLI client. Replication and record versions are excluded.

| Requirement | Implementation and evidence |
|---|---|
| Independent processes | `storage_node.py`, `router.py` and `sharedkv/cluster.py`; N initial stores, one waiting store and a distinct router PID in each current trial. The historical reference uses four stores and one router. |
| Put/Get through a router | `/put` and `/get`; `client.py` only calls HTTP and formats responses. Storage holds plain text values. Tests cover overwrite, empty text, Unicode and misses. |
| Modulo and consistent hashing | Router-only `sharedkv/placement.py`; integer SHA-256 remainder or first clockwise integer token. Fixed-membership and token-order tests. |
| Runtime mode and V controls | `/admin/placement` and `/admin/vnodes`; no implicit migration/deletion. Populated data requires flush/reload. Tests cover the guard and reloading. |
| Owners, key counts and traffic | `owner`, `keys`, `stats` and `/ring`; routed versus physical hosts, counts, shares and separate inspection probes. |
| Node registration and membership version | `addnode D 127.0.0.1:5104` with the quickstart port range; validated identity/address/empty destination, version 1 to 2 after verification. |
| Actual reassigned-key transfer | Router copy/verify/publication/cleanup protocol; both modulo many-to-many and consistent-to-D transfers. Changed owners equal acknowledged and verified destination counts. |
| Paused writes, readable Gets | 503 Put while migrating; Gets read old owners until verified publication. Tests use deterministic phase barriers and real storage HTTP calls; the separate rehearsal exercises CLI commands. |
| Same dataset and full verification | Each configured trial uses identical synthetic values and seeded reads. Every value and physical owner is checked after migration. The historical comparison has thirty trials with 1,000 values each. |
| Key balance versus hot traffic | Reset after verification; configurable uniform reads followed by extra hot-key reads. Key counts stay unchanged and exactly the configured extra forwards reach its owner. Historical totals are 1,000 and 500. |
| Virtual-node bonus | Configurable V=1..1024; the original-sized profile includes 1,2,4,8,10,16,32,64,128. Reports include max/min and CV without a monotonicity or universal-optimum claim. |
| Proper API reference | `docs/api.md`, two generated OpenAPI files and live response/schema validation. No web UI is required. |
| Failure behavior | Observed unreachable stores become down without eviction. Tests cover lost-copy acknowledgments and post-publication cleanup failure. Recovery does real cleanup before unpausing. |

The original thirty-trial comparison remains historical reference evidence. Current collection and reporting are parameterized through TOML and produce separate raw runs. See [configuration](configuration.md) and [reproduction](reproduction.md). One join, single-uppercase IDs, loopback-only processes and single-owner volatile data preserve the academic study boundary.

The framework's practical uses are [guided lab exercises](use-cases.md), client practice and controlled local comparisons. It is not a research-paper pipeline. A complete exercise consists of a question, explicit settings, checked observations and a short explanation of the tradeoffs and limits. Presentations and private course material are not part of reproduction.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Demonstration](demo.md) · Next: [Spec decisions](spec-decisions.md)
<!-- reading:end -->
