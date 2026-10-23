\# Project 5 — Sharded Key-Value Store: Full Implementation Spec



This is the consolidated spec, incorporating all prior decisions: Dynamo paper as primary reference, blog only for consistent-hashing/virtual-node concepts, A+C architecture (CLI as pure client, network framework as the system), single-replica with no quorum, centralized router as coordinator, writes paused during migration, switchable modulo/consistent hashing, and a rectangular (non-circular) ASCII ring view.



\---



\## 1. Scope and Assumptions



\### 1.1 In scope



\- Single-replica `Put` / `Get`; owner determined by placement strategy.

\- Two placement modes: `modulo` and `consistent`, switchable at runtime.

\- Consistent hashing supports configurable virtual nodes per node (`V`).

\- At least 3 independent storage processes + 1 router process.

\- Cluster membership: node registration, membership version, runtime node addition.

\- On node addition: pause writes → migrate reassigned keys → verify key-by-key → resume writes.

\- Display owner per key, key count per node, request count per node.

\- `GET /ring` API returning structured placement data; CLI renders a linear ASCII token sequence.

\- Required experiment: same key set, compare modulo vs consistent on placement balance and reassignment fraction; include a frequent-key workload to separate key balance from request balance.



\### 1.2 Out of scope (must be stated in README)



\- No replication, no N/R/W quorum, no preference list, no sloppy quorum, no hinted handoff.

\- No vector clocks, no multi-versioning, no conflict resolution.

\- No gossip membership, no failure detection, no automatic failure eviction.

\- Writes are \*\*paused during migration\*\* (`Put` rejected with `503`). This is a simplification, not Dynamo's online migration.

\- No web GUI.



\### 1.3 Key simplifying assumptions (README must document these)



1\. \*\*Centralized membership\*\*: the router holds the single membership table; no gossip.

2\. \*\*Pause writes during migration\*\*: during migration, `Put` returns `503`; `Get` is allowed (reading the old owner is still correct because old keys are not deleted until after verification).

3\. \*\*Single replica, single-owner acknowledgment\*\*: `Put` success = owner wrote locally.

4\. \*\*No node failures\*\*: experiments assume storage nodes do not crash during migration; if a node crashes, the router marks it `down` and returns an error — no automatic recovery.



\---



\## 2. Architecture



```text

┌────────────┐   HTTP    ┌─────────────────┐   HTTP    ┌──────────────┐

│ CLI Client │ ────────► │ Router :8000    │ ────────► │ Storage A    │

│ (client.py)│ ◄──────── │                 │ ◄──────── │ :5001        │

└────────────┘           │ membership tbl  │           └──────────────┘

&#x20;                        │ placement cfg   │           ┌──────────────┐

┌────────────┐   HTTP    │ migration state │ ────────► │ Storage B    │

│ Experiment │ ────────► │ request counters│ ◄──────── │ :5002        │

│ (exp.py)   │ ◄──────── │ ring view       │           └──────────────┘

└────────────┘           └─────────────────┘           ┌──────────────┐

&#x20;                                    │ ───────────────► │ Storage C    │

&#x20;                                    │ ◄─────────────── │ :5003        │

&#x20;                                    │                  └──────────────┘

&#x20;                                    │ ───────────────► ┌──────────────┐

&#x20;                                    │ ◄─────────────── │ Storage D    │

&#x20;                                    │                  │ :5004 (added)│

&#x20;                                    └─────────────────►└──────────────┘

```



| Component | Process | Responsibility |

|---|---|---|

| Storage node | Independent | Stores `key -> value`; serves `Put/Get/Delete/Keys/MigrateIn/Stats/Health`; does not know placement or peers |

| Router | Independent | Receives client requests, computes owner, forwards, maintains membership + placement, coordinates migration, counts requests, serves `/ring` |

| CLI client | Independent | Pure client: parses input, calls router API, formats output; \*\*never\*\* computes owner or holds membership |

| Experiment script | Independent | Pure client: batch-calls API, emits comparison JSON |



\*\*Hard rule\*\*: placement, membership, and migration logic exist \*\*only\*\* in the router. The CLI and experiment script must not duplicate them.



\---



\## 3. Data Model



\### 3.1 Storage node local state



```json

{

&#x20; "id": "A",

&#x20; "kv": { "user:101": "Apple", "user:102": "Banana" }

}

```



Only `key -> value`. No version.



\### 3.2 Router state



```json

{

&#x20; "placement\_mode": "consistent",

&#x20; "vnodes\_per\_node": 16,

&#x20; "membership\_version": 2,

&#x20; "nodes": \[

&#x20;   {"id": "A", "addr": "localhost:5001", "status": "active"},

&#x20;   {"id": "B", "addr": "localhost:5002", "status": "active"},

&#x20;   {"id": "C", "addr": "localhost:5003", "status": "active"},

&#x20;   {"id": "D", "addr": "localhost:5004", "status": "active"}

&#x20; ],

&#x20; "ring": \[

&#x20;   {"pos": 0.000, "node": "A", "label": "a1"},

&#x20;   {"pos": 0.021, "node": "B", "label": "b1"},

&#x20;   {"pos": 0.043, "node": "A", "label": "a2"}

&#x20; ],

&#x20; "migration": {

&#x20;   "state": "idle",

&#x20;   "paused\_writes": false,

&#x20;   "old\_membership\_version": null,

&#x20;   "new\_membership\_version": null

&#x20; },

&#x20; "request\_counts": { "A": 12, "B": 87, "C": 10, "D": 9 },

&#x20; "key\_request\_counts": { "user:101": 75 }

}

```



The router \*\*does not hold\*\* `key -> value` and \*\*does not hold\*\* a global `key -> node` table. The owner is computed from placement on demand.



\### 3.3 State enums



| Field | Values |

|---|---|

| `node.status` | `active` / `joining` / `leaving` / `down` |

| `migration.state` | `idle` / `preparing` / `migrating` / `verifying` / `done` / `failed` |

| `placement\_mode` | `modulo` / `consistent` |



\---



\## 4. Placement Algorithms



\### 4.1 Modulo hashing



```text

owner(key) = active\_nodes\_sorted\_by\_id\[ floor(hash(key) \* N) % N ]

where N = len(active\_nodes)

```



\- `active\_nodes` sorted lexicographically by `id` ensures determinism.

\- Adding/removing a node changes `N`, so most keys change owner.

\- Stored as: `nodes\_sorted`, `key\_hash` in `\[0,1)`, `owner\_index`.



\### 4.2 Consistent hashing with virtual nodes



```text

token(node\_id, i) = hash(f"{node\_id}#{i}")   for i in 0..V-1

ring = sorted(\[(pos, node\_id, label) for each node, each i])

owner(key):

&#x20;   t = hash(key)

&#x20;   idx = first index in ring where ring\[idx].pos >= t

&#x20;   if none: idx = 0                            # wrap-around

&#x20;   return ring\[idx].node\_id, ring\[idx]

```



\- `V` is `vnodes\_per\_node`, configurable via `POST /admin/vnodes`.

\- `label` is `f"{node\_id}{i+1}"` (e.g., `a7`).

\- Only keys between the joining node's predecessor and the joining node's own tokens are affected.



\### 4.3 Unified interface



```text

placement.owner(key, membership, mode, vnodes) -> (node\_id, owner\_token\_or\_index)

placement.build(membership, mode, vnodes) -> placement\_state

```



When `placement\_mode` or `vnodes\_per\_node` is switched, `placement\_state` is rebuilt. \*\*No data is migrated by a mode switch\*\* — the experiment must flush and reload keys after switching (documented in README).



\---



\## 5. Cluster Membership



\### 5.1 Initialization



```bash

python router.py --port 8000 \\

&#x20; --nodes A=localhost:5001,B=localhost:5002,C=localhost:5003 \\

&#x20; --placement consistent \\

&#x20; --vnodes 16

```



`membership\_version = 1` after initialization.



\### 5.2 Add-node flow (inside router)



```text

add\_node(id, addr):

&#x20; 1. Validate id absent; addr reachable (storage /health)

&#x20; 2. migration.state = preparing; paused\_writes = true

&#x20; 3. old\_membership = current active nodes

&#x20; 4. New node status = joining; add to nodes

&#x20; 5. new\_membership = old + {id}

&#x20; 6. Enumerate all keys from all old owners via GET /keys

&#x20; 7. For each key: old\_owner = placement(key, old); new\_owner = placement(key, new)

&#x20;    reassigned = {(key, old\_owner, new\_owner) | old\_owner != new\_owner}

&#x20; 8. migration.state = migrating

&#x20; 9. For each (key, old\_owner, new\_owner):

&#x20;      val = GET old\_owner /kv/{key}

&#x20;      PUT new\_owner /kv/{key} {value: val}

&#x20;      record (key, hash(val))

&#x20;10. migration.state = verifying

&#x20;11. For each (key, expected\_hash):

&#x20;      val = GET new\_owner /kv/{key}

&#x20;      if hash(val) != expected\_hash: failures.append(key)

&#x20;12. If failures: migration.state = failed; paused\_writes stays true; return error

&#x20;13. Else: delete old keys from old\_owner (only if old\_owner != new\_owner)

&#x20;14. New node status = active; membership\_version += 1

&#x20;15. migration.state = idle; paused\_writes = false

&#x20;16. Return migration summary

```



\### 5.3 Pause-writes semantics



| Operation | When `paused\_writes = true` |

|---|---|

| `Put` | `503 {"error":"migration\_in\_progress","retry\_after\_ms":500}` |

| `Get` | Allowed (old keys still present until after verification) |

| `Stats` | Allowed |

| `Ring` | Allowed; response includes `migration\_state` and `pending\_owner` if applicable |

| `AddNode` | `409 {"error":"migration\_in\_progress"}` |

| `Placement` / `Vnodes` | `409` (must not reconfigure mid-migration) |



> If you choose to queue instead of reject: router keeps a bounded queue and flushes after migration; document the choice in README. The spec assumes \*\*reject\*\* as default.



\---



\## 6. API Spec



All APIs use JSON over HTTP. Unified error format:



```json

{"error": "<code>", "message": "<human readable>", "details": {...}}

```



\### 6.1 Storage Node API



| Method | Path | Body / Query | Response |

|---|---|---|---|

| `GET` | `/health` | — | `{"id":"A","status":"ok","key\_count":5}` |

| `PUT` | `/kv/{key}` | `{"value":"..."}` | `{"ok":true}` |

| `GET` | `/kv/{key}` | — | `{"key":"...","value":"..."}` or `404 {"error":"not\_found"}` |

| `DELETE` | `/kv/{key}` | — | `{"ok":true}` |

| `GET` | `/keys` | — | `{"keys":\["k1","k2",...]}` |

| `POST` | `/migrate\_in` | `{"items":\[{"key":"k","value":"v"}]}` | `{"ok":true,"count":N}` |

| `GET` | `/stats` | — | `{"id":"A","key\_count":5}` |

| `DELETE` | `/keys` | — | `{"ok":true,"deleted":N}` (flush, for experiments) |



> Storage nodes are unaware of placement and peers.



\### 6.2 Router Client API



| Method | Path | Body / Query | Response |

|---|---|---|---|

| `POST` | `/put` | `{"key":"...","value":"..."}` | `{"ok":true,"owner":"A"}` / `503` |

| `GET` | `/get` | `?key=...` | `{"key":"...","value":"...","owner":"A"}` / `404` |

| `GET` | `/owner` | `?key=...` | `{"key":"...","owner":"A"}` |

| `GET` | `/stats` | — | See 6.3 |

| `GET` | `/ring` | `?key=...` (`\&check=1` optional) | See 6.5 |



\### 6.3 `/stats` response



```json

{

&#x20; "placement\_mode": "consistent",

&#x20; "vnodes\_per\_node": 16,

&#x20; "membership\_version": 2,

&#x20; "paused\_writes": false,

&#x20; "nodes": \[

&#x20;   {"id":"A","status":"active","key\_count":3,"request\_count":12},

&#x20;   {"id":"B","status":"active","key\_count":4,"request\_count":87},

&#x20;   {"id":"C","status":"active","key\_count":3,"request\_count":10},

&#x20;   {"id":"D","status":"active","key\_count":2,"request\_count":9}

&#x20; ],

&#x20; "key\_counts\_total": 12,

&#x20; "top\_keys\_by\_requests": \[

&#x20;   {"key":"user:101","owner":"B","requests":75}

&#x20; ]

}

```



`key\_count` is aggregated from each storage `/stats`. `request\_count` is incremented by the router on forwarding.



\### 6.4 Router Admin API



| Method | Path | Body | Response |

|---|---|---|---|

| `POST` | `/admin/addnode` | `{"id":"D","addr":"localhost:5004"}` | Migration summary (6.6) / `409` |

| `POST` | `/admin/placement` | `{"mode":"modulo"}` | `{"ok":true,"mode":"modulo"}` / `409` |

| `POST` | `/admin/vnodes` | `{"v":128}` | `{"ok":true,"vnodes\_per\_node":128}` / `409` |

| `GET` | `/admin/membership` | — | `{"version":2,"nodes":\[...]}` |

| `POST` | `/admin/reset\_counters` | — | `{"ok":true}` |

| `POST` | `/admin/recover` | — | `{"ok":true}` (clears `failed` state) |

| `GET` | `/admin/health` | — | `{"ok":true}` |



> `/admin/placement` and `/admin/vnodes` only rebuild placement; they do not migrate data. After switching, owners change while storage data stays put — \*\*experiments must flush and reload keys after switching\*\*.



\### 6.5 `/ring` response



Consistent mode:



```json

{

&#x20; "placement\_mode": "consistent",

&#x20; "vnodes\_per\_node": 16,

&#x20; "total\_tokens": 48,

&#x20; "tokens": \[

&#x20;   {"pos": 0.000, "node": "A", "label": "a1"},

&#x20;   {"pos": 0.021, "node": "B", "label": "b1"},

&#x20;   {"pos": 0.043, "node": "A", "label": "a2"}

&#x20; ],

&#x20; "node\_shares": {

&#x20;   "A": {"tokens": 15, "fraction": 0.30},

&#x20;   "B": {"tokens": 10, "fraction": 0.20},

&#x20;   "C": {"tokens": 23, "fraction": 0.50}

&#x20; },

&#x20; "key": "user:101",

&#x20; "key\_hash": 0.415,

&#x20; "owner": "A",

&#x20; "owner\_token": {"pos": 0.420, "node": "A", "label": "a7"},

&#x20; "migration\_state": "idle",

&#x20; "exists": true

}

```



Modulo mode:



```json

{

&#x20; "placement\_mode": "modulo",

&#x20; "nodes\_sorted": \["A", "B", "C"],

&#x20; "key": "user:101",

&#x20; "key\_hash": 0.415,

&#x20; "owner\_index": 1,

&#x20; "owner": "B",

&#x20; "exists": true

}

```



\- `tokens` already sorted ascending by `pos`.

\- `exists` populated only with `?check=1` (router calls `GET /kv/{key}` on owner); omitted otherwise.

\- If migration is in progress and the key is being reassigned, include `"pending\_owner": "D"`.



\### 6.6 `/admin/addnode` response



```json

{

&#x20; "ok": true,

&#x20; "old\_membership\_version": 1,

&#x20; "new\_membership\_version": 2,

&#x20; "placement\_mode": "consistent",

&#x20; "paused\_writes": true,

&#x20; "reassigned\_key\_count": 7,

&#x20; "reassigned\_keys": \["user:101","user:102", "..."],

&#x20; "migrated": 7,

&#x20; "verified": 7,

&#x20; "verification\_failures": \[],

&#x20; "key\_counts\_after": {"A":3,"B":4,"C":3,"D":2}

}

```



\---



\## 7. Migration Protocol (Detailed)



\### 7.1 State machine



```text

idle ──addnode──► preparing ──► migrating ──► verifying ──► done ──► idle

&#x20;                                  │              │

&#x20;                                  └──error───────┴──► failed (paused\_writes=true; manual /admin/recover)

```



\### 7.2 Reassigned key computation



Union of keys from all old owners (via `/keys`). For each key, compute `old\_owner` and `new\_owner`. Reassigned keys are those where they differ.



\- \*\*Consistent hashing\*\*: `new\_owner` can only be the new node `D`; `old\_owner` is `D`'s clockwise predecessor.

\- \*\*Modulo\*\*: `new\_owner` can be any node (including old nodes); `old\_owner` may not be the new node. Implementation must support many-to-many movement.



\### 7.3 Movement steps



```text

for (key, old\_owner, new\_owner) in reassigned:

&#x20;   val = HTTP GET old\_owner /kv/{key}

&#x20;   HTTP PUT new\_owner /kv/{key}  {value: val}

&#x20;   record (key, hash(val))

```



Do \*\*not\*\* delete old keys until verification passes, so `Get` remains readable during migration.



\### 7.4 Verification



For each `(key, expected\_hash)`, `GET new\_owner /kv/{key}` and compare. Non-empty failures → `state = failed`; otherwise delete old keys (only if `old\_owner != new\_owner`) and `state = done`.



\### 7.5 Recovery



`POST /admin/recover`: clears `failed`, sets `paused\_writes=false`, `state=idle`. Used for failure-path demos; automatic recovery not required.



\---



\## 8. CLI Client Spec (`client.py`)



Pure client. Does not hold membership or compute owners. Prints `owner` fields from router responses.



\### 8.1 Commands



```text

put <key> <value>

get <key>

owner <key>

ring <key> \[--check]

stats

addnode <id> <addr>

placement <modulo|consistent>

vnodes <V>

membership

reset-counters

recover

quit

```



\### 8.2 Output format



Field labels aligned with fixed width; `Value:` and `Owner:` label padded to 8 chars.



```text

>> User: put user:101 Apple

\[Stored] user:101

&#x20;  Value:  Apple

&#x20;  Owner:  A



>> User: get user:101

\[FOUND] user:101

&#x20;  Value:  Apple

&#x20;  Owner:  A



>> User: get user:999

\[NOT FOUND] user:999

&#x20;  Owner:  B



>> User: put user:102 Banana

\[REJECTED] migration\_in\_progress (retry after 500ms)

```



\### 8.3 `ring` rendering (consistent mode, rectangular layout)



Layout: left→right = 0%→100%; one character per token; `^` aligned to the first token with `pos >= key\_hash`. Wrap every 60 chars.



```text

>> User: ring user:101

Ring: consistent hashing

Tokens: 48 total (16 vnodes/node)

Sequence: clockwise, 0% left -> 100% right



&#x20; 0%                                                          100%

&#x20; ABACBACCABCABCAA CBACBACACBACA BCABC ABACB ACBAC BACB

&#x20;                    ^

&#x20; key user:101 @ 41.5%

&#x20; next token: A/a7 @ 42.0% -> owner A



Node shares:

&#x20; A   30.0%  (15 tokens)

&#x20; B   20.0%  (10 tokens)

&#x20; C   50.0%  (23 tokens)



Stored on A: yes

```



Rules:



\- Each character = one token, in ascending `pos` order.

\- `^` placed at the index of the first token with `pos >= key\_hash` (across all wrapped lines).

\- If `key\_hash` exceeds all token positions, owner wraps to first token; annotate `(wrap-around)` at line end.

\- `Stored on A` shown only with `--check` (or after an internal `/get`); omit otherwise.

\- If migration is in progress and this key is being reassigned: append `migration: pending new owner D`.



\### 8.4 `ring` rendering (modulo mode)



No token sequence. Show the `hash % N` computation.



```text

>> User: ring user:101

Placement: modulo hashing

Nodes (sorted): \[A, B, C]

hash(user:101) = 0.415

owner index = floor(0.415 \* 3) = 1

owner = B



Stored on B: yes

```



\### 8.5 `stats` rendering



```text

>> User: stats

placement=consistent  vnodes=16  membership=v2  paused=false

&#x20; A  status=active  keys=3   requests=12

&#x20; B  status=active  keys=4   requests=87

&#x20; C  status=active  keys=3   requests=10

&#x20; D  status=active  keys=2   requests=9

&#x20; total keys=12

top keys:

&#x20; user:101  -> B  (75 requests)

```



\### 8.6 `addnode` rendering



```text

>> User: addnode D localhost:5004

\[router] membership v1 -> v2, writes paused

\[router] reassigned 7 keys, migrating...

\[router] verifying 7 keys... OK

\[router] writes resumed

key counts: A=3 B=4 C=3 D=2

```



\---



\## 9. Experiment Script Spec (`experiment.py`)



Pure client; calls router API directly.



\### 9.1 Parameters



```bash

python experiment.py \\

&#x20; --router http://localhost:8000 \\

&#x20; --keys 1000 \\

&#x20; --mode modulo|consistent \\

&#x20; --vnodes 16 \\

&#x20; --hot-key user:101 \\

&#x20; --hot-requests 500 \\

&#x20; --out results/<mode>.json

```



\### 9.2 Flow



```text

1\. POST /admin/reset\_counters

2\. POST /admin/placement {mode}

3\. POST /admin/vnodes {v}                    # only if consistent

4\. Flush: DELETE /keys on each storage node

5\. Load: for k in keys: POST /put {k, v\_k}

6\. Baseline: GET /stats, GET /owner for each key -> owner map

7\. POST /admin/addnode {id:"D", addr:"localhost:5004"}

8\. Record migration summary (reassigned\_key\_count, verified, failures)

9\. After: GET /stats -> key\_counts\_after

10\. Verify: for k in keys: GET /get?key=k, compare with v\_k

11\. Hot workload: for i in hot\_requests: GET /get?key=hot-key

12\. GET /stats -> request\_counts per node

13\. Emit JSON (see 9.3)

```



\### 9.3 Output JSON



```json

{

&#x20; "mode": "consistent",

&#x20; "vnodes\_per\_node": 16,

&#x20; "key\_count": 1000,

&#x20; "placement\_balance\_before": {

&#x20;   "key\_counts": {"A":334,"B":333,"C":333},

&#x20;   "max\_min\_ratio": 1.003

&#x20; },

&#x20; "placement\_balance\_after": {

&#x20;   "key\_counts": {"A":250,"B":251,"C":250,"D":249},

&#x20;   "max\_min\_ratio": 1.008

&#x20; },

&#x20; "reassignment": {

&#x20;   "reassigned\_key\_count": 251,

&#x20;   "fraction": 0.251

&#x20; },

&#x20; "verification": {

&#x20;   "checked": 1000,

&#x20;   "failures": \[]

&#x20; },

&#x20; "request\_balance": {

&#x20;   "before\_hot": {"A":12,"B":13,"C":11,"D":0},

&#x20;   "after\_hot":  {"A":12,"B":513,"C":11,"D":0},

&#x20;   "hot\_key": "user:101",

&#x20;   "hot\_key\_owner": "B"

&#x20; }

}

```



`request\_balance` is measured under the \*\*same key distribution\*\*, adding only hot `GET`s — showing `key\_counts` nearly unchanged while `request\_counts` skew heavily.



\---



\## 10. Required Experiment and Metric Definitions



\### 10.1 Comparison table (must appear in README)



| Metric | Modulo | Consistent |

|---|---|---|

| Baseline key counts | A/B/C | A/B/C |

| After add D key counts | A/B/C/D | A/B/C/D |

| `placement\_balance` = `max(count) / min(count)` | ? | ? |

| `reassigned\_key\_count` | ? | ? |

| `reassignment\_fraction` = `reassigned / total` | ? | ? |

| Verification failures | 0 | 0 |

| Hot-key request counts (after hot workload) | ? | ? |



If `V` is explored: a second table for `V ∈ {1, 10, 128}` showing `placement\_balance` convergence.



\### 10.2 Metric definitions (write into README)



\- \*\*placement\_balance\*\*: `max(node.key\_count) / min(node.key\_count)`; closer to 1 is more uniform.

\- \*\*reassignment\_fraction\*\*: `reassigned\_key\_count / total\_keys`.

\- \*\*request\_balance\_ratio\*\*: `max(node.request\_count) / min(node.request\_count)` after the hot workload.

\- \*\*verification\*\*: after migration, `GET` each key; value must equal the original; `failures` must be empty.



\### 10.3 Expected conclusions (verify experimentally)



\- Modulo: `reassignment\_fraction` approaches `1 - 1/N` (\~75% after adding D); placement may still be uniform.

\- Consistent (`V=1`): `reassignment\_fraction` \~`1/(N+1)` (\~25% for 3→4) with high placement variance.

\- Consistent (`V=128`): `placement\_balance` close to 1; `reassignment\_fraction` still \~`1/(N+1)`.

\- Hot workload: `key\_counts` unchanged, `request\_counts` skewed toward the hot key's owner → key balance ≠ request balance.



\---



\## 11. Directory Structure



```text

project5/

├── storage\_node.py       # standalone storage process

├── router.py             # standalone router process

├── placement.py          # modulo + consistent hashing (used by router)

├── client.py             # CLI demo client

├── experiment.py         # experiment script

├── run\_cluster.sh        # launch 3 storage nodes + router

├── README.md             # assumptions, API, experiment results, comparison table

└── results/

&#x20;   ├── modulo.json

&#x20;   └── consistent.json

```



\---



\## 12. Implementation Order



1\. \*\*Storage node\*\*: `PUT/GET/DELETE /kv/{key}`, `/keys`, `DELETE /keys`, `/stats`, `/health`. Test via curl on a single process.

2\. \*\*Placement module\*\*: `modulo` and `consistent` (with V) `owner()` + unit tests (fixed membership, fixed key set; owner determinism; reassignment set correct after adding D).

3\. \*\*Router basic routing\*\*: `/put`, `/get`, `/owner`, `/stats`, `/admin/membership`. `paused\_writes=false`.

4\. \*\*Router admin\*\*: `/admin/placement`, `/admin/vnodes`, `/admin/reset\_counters`, request counting.

5\. \*\*`/ring`\*\*: consistent and modulo responses; `?check=1` existence probe.

6\. \*\*Migration\*\*: `/admin/addnode` + state machine + pause writes + enumeration + movement + verification + `/admin/recover`.

7\. \*\*CLI client\*\*: all commands and renderers (8.2–8.6).

8\. \*\*Experiment script\*\*: two rounds, modulo vs consistent; JSON outputs; README table.

9\. \*\*README\*\*: assumptions, API, state machine, experiment results, conclusions.



\---



\## 13. Test Plan



| Level | Tests |

|---|---|

| Placement unit | Fixed key set + membership; owner determinism for modulo and consistent; reassigned set correct after adding D; V=1 vs V=128 shares differ |

| Storage | curl on a single node: PUT/GET/DELETE/keys/stats/flush |

| Router routing | 3 nodes: PUT then GET consistent; `/owner` matches actual owner |

| Pause writes | Concurrent `PUT` during `addnode` returns `503`; `PUT` succeeds after migration |

| Migration verification | After adding D, GET each key; values all equal; `verification\_failures` empty |

| Modulo many-to-many | After adding D, `new\_owner` of reassigned keys may not be D; movement still correct |

| Hot key | Same key set; 500 GETs on hot key; `request\_counts` skew, `key\_counts` unchanged |

| `/ring` | Token order ascending; `^` aligned to first `pos >= key\_hash`; wrap-around handled; modulo mode shows index computation |

| Failure path | Storage unreachable during migration → `state=failed`, `paused\_writes=true`, `/admin/recover` restores |

| Mode switch | `/admin/placement` and `/admin/vnodes` return `409` mid-migration; otherwise rebuild placement without moving data |



\---



\## 14. Optional Extensions



\- \*\*Virtual-node sweep\*\*: `POST /admin/vnodes` with `V ∈ {1, 10, 128}`; add a table to README showing `placement\_balance` convergence with `V`.

\- \*\*Replication (separate mechanism)\*\*: if implemented, document `N/R/W`, read/write paths, and conflict strategy separately; \*\*must not\*\* be mixed into the baseline single-replica path.



\---



\## 15. Required README Sections



1\. System overview and architecture diagram.

2\. \*\*Simplifying assumptions\*\* (centralized membership, pause writes, single replica, no quorum, no gossip).

3\. API spec (storage / router / admin / ring).

4\. Placement algorithms (modulo / consistent with V) and switch semantics (no data migration on switch; flush and reload required).

5\. Migration state machine and pause-writes semantics (`Put` returns `503`).

6\. Experiment setup (key count, hot key, request count, V) and the \*\*comparison table\*\*.

7\. Metric definitions and conclusions (modulo vs consistent on balance / reassignment; key balance vs request balance; V convergence if explored).

8\. Known limitations and out-of-scope list.

9\. Launch and test instructions.



\---



\## 16. Acceptance Checklist (mapped to Project Requirements)



\- \[ ] 1 router + ≥3 storage \*\*independent processes\*\*, supporting `Put`/`Get`.

\- \[ ] Both `modulo` and `consistent` implemented; switchable at runtime; consistent supports configurable V.

\- \[ ] `/stats` shows owner per key (`/owner`) and key count per node.

\- \[ ] `GET /ring` returns structured token data; CLI renders linear ASCII sequence with aligned `^`.

\- \[ ] `addnode` adds one node and transfers reassigned keys.

\- \[ ] During migration, `Put` returns `503`; documented in README.

\- \[ ] Same key set: comparison table of `placement\_balance` and `reassignment\_fraction` for modulo vs consistent.

\- \[ ] After migration, each key's value verified; `failures` empty.

\- \[ ] Frequent-key workload included; `key\_counts` and `request\_counts` presented separately.

\- \[ ] README contains assumptions, API, state machine, experiment results, out-of-scope.



