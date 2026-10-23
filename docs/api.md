# API reference

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

<!-- contents:start -->
On this page: [Put, Get and owner](#put-get-and-owner) · [Router observation](#router-observation) · [Router administration](#router-administration) · [Internal storage API](#internal-storage-api) · [Validate contracts](#validate-contracts)
<!-- contents:end -->

The router normally listens on `http://127.0.0.1:8000`. Storage defaults to ports 5001–5004; the quickstart uses `--storage-base-port 5101`, so A–D use 5101–5104. Follow the addresses printed by the launcher. The two machine-readable contracts are [router OpenAPI](openapi.json) and [storage OpenAPI](storage-openapi.json). Run `python3 tools/api_contracts.py` to regenerate them. There is no web UI or documentation server.

All listeners bind to loopback. This local teaching framework has no authentication, TLS, CORS, pagination or durable storage. JSON is the HTTP message format; the CLI accepts ordinary text values. Bodies must be UTF-8 JSON objects with `Content-Type: application/json`, at most 1 MiB. Keys contain 1–1024 UTF-8 bytes; values may be empty text. Non-finite numbers, extra Put fields and record-version fields are rejected. Percent-encode complete storage path keys and router query keys. Use Python's `urlencode`/`quote` or curl `--data-urlencode` rather than concatenating raw keys.

## Put, Get and owner

```bash
curl -sS http://localhost:8000/put -H 'Content-Type: application/json' \
  -d '{"key":"user:101","value":"Apple"}'
curl -sS -G http://localhost:8000/get --data-urlencode 'key=user:101'
```

Successful responses, with the default initial V=16 ring:

```json
{"ok":true,"owner":"A"}
```

```json
{"key":"user:101","value":"Apple","owner":"A"}
```

`POST /put` creates or overwrites text and waits for that single owner. There are no record versions or historical values. `GET /get?key=...` returns the current value or 404. `GET /owner?key=...` returns placement information whether or not the key exists: integer hash, owner, membership version, placement revision, and either a modulo index or the exact owner token/index and wrap flag.

Every application error has this shape:

```json
{"error":"not_found","message":"The key does not exist.","details":{"key":"missing","owner":"A"}}
```

The owner in an error depends on the actual mode, V and membership. HTTP statuses are 400 invalid input, 404 missing key/path, 405 wrong handled method, 409 state conflict/reload required, 413 oversized body, 415 wrong media type, 500 internal error, 502 invalid dependency response and 503 unavailable/busy/paused. GET/POST/PUT/DELETE/PATCH/OPTIONS use the JSON handler; other unsupported HTTP verbs may receive Python's ordinary 501 response. The CLI returns 0 success, 2 usage, 3 missing key, 4 other client conflict/rejection, 5 unavailable/server failure and 130 interrupted command.

## Router observation

| Method and path | Contract |
|---|---|
| `GET /stats` | Mode, V, membership/revision, pause/migration/reload state, node rows, physical total, top requested keys and inspection count. A node row has ID/address/status, key count and request count. Unavailable counts are null and `counts_complete=false`; the partial total is labeled incomplete. |
| `GET /keys` | Every stored key's routed owner and physical host list. Temporary duplicates may exist during migration. |
| `GET /ring[?key=...][&check=1]` | Structured placement, described below. |
| `GET /admin/membership` | Membership version, placement revision, registered nodes, paused/reload flags, migration phase/old/new versions, last completed summary and router PID. |
| `GET /admin/health` | `ok` and router PID. This does not probe all stores. |

Request counts increment when the router forwards a client Put/Get attempt, including misses. Loading therefore counts Puts; no hidden version lookup is performed. Inventory, health, migration and ring probes do not enter workload counts. Ring existence probes increment a separate `inspection_reads` counter. Reset after verification before measuring request balance. Reset is not a transactional boundary with unrelated concurrent clients.

`/ring` always returns mode, V, integer hash-space size, membership/revision and state flags. Consistent mode adds sorted `{pos,node,label}` tokens, total token count and per-node token count, hash-unit coverage and fraction. With a key, it adds `key_hash`, `owner`, `owner_token`, `owner_token_index` and `wrap_around`. Modulo instead adds sorted IDs and, with a key, `owner_index`. Hash positions are arbitrary-precision 256-bit integers; clients must preserve integer precision.

By default, a ring query makes no existence claim. `check=1` requires a key and adds `exists:true/false` after a storage Get. A missing key is a successful placement query with `exists:false`, not an invented stored record. During migration, a changed key may include `pending_owner` while the current owner remains the old map's owner. The CLI renders the server's token index; columns represent token rank, not evenly spaced hash values.

## Router administration

| Method and path | Body and result |
|---|---|
| `POST /admin/addnode` | `{"id":"D","addr":"127.0.0.1:5104"}` for the quickstart range. Use D's actual listening address. ID must be an unused uppercase letter and address a unique loopback port serving that ID. Destination must be empty. Returns the migration summary. |
| `POST /admin/placement` | `{"mode":"modulo"}` or `consistent`. Rebuild without data migration; return mode, V, revision and reload flag. |
| `POST /admin/vnodes` | `{"v":128}`, integer 1–1024. Same reset/reload semantics. |
| `POST /admin/reset_counters` | Empty object or no body. Clears client and inspection counters. |
| `POST /admin/flush` | Empty object or no body. Explicitly deletes values from all registered stores; returns deleted item count. Clears the reload guard only after all stores succeed. |
| `POST /admin/recover` | Empty object or no body. Valid only after failed migration; performs rollback or cleanup before resuming writes. |

The join response includes old/new membership versions, mode, reassigned count and key list, acknowledged `migrated` count, `verified` destinations, verification failures, final node counts, seconds and `estimated_item_bytes`. It declares `writes_paused_during_migration=true` but returns current `paused_writes=false` after success. The byte field is calculated UTF-8 JSON size of logical `{key,value}` items, **not measured network traffic**. [Metric definitions](metrics.md) explain its representation and the timer boundary.

During migration, Put returns 503 `migration_in_progress` with `details.retry_after_ms=500`; Get, stats and ring remain available. Another join, mode/V change or flush returns 409. Gets use old sources until the verified new map is published. Recovery keeps the old map before publication and the new map afterward. Unreachable stores are marked down without automatic eviction or data repair. A mode/V switch with populated data sets `reload_required`; Put/Get return 409 until explicit flush/reload. Owner and ring inspection remain available.

No client automatically retries mutations. A busy/paused rejection did not perform the requested Put. A connection timeout is ambiguous: inspect membership/status or read the key before deciding whether to retry. Repeating the same text Put is a value overwrite, but it could overwrite a concurrent client's later value. Repeating addnode after a lost response may instead be a duplicate registration. Flush and recovery also need inspection after an ambiguous response.

## Internal storage API

| Method and path | Request and response |
|---|---|
| `GET /health`, `GET /stats` | ID, `status=ok`, local key count and process PID. |
| `PUT /kv/{key}` | Exactly `{"value":"text"}`; returns `{"ok":true}`. |
| `GET /kv/{key}` | `{key,value}` or 404. |
| `DELETE /kv/{key}` | Delete if present, otherwise succeed. Used for router migration cleanup. |
| `GET /keys` | Sorted local key list. |
| `DELETE /keys` | Flush local values and return deleted count. |
| `POST /migrate_in` | `{"items":[{"key":"k","value":"v"}]}`; validate all distinct keys/text values before updating atomically, then return accepted count. |

Storage does not know peers, placement, membership or record versions. Ordinary clients should use the router. Direct storage mutation can break routing and is outside the framework's migration assumptions. The implementation uses individual acknowledged Puts for migration; the small batch endpoint is available as specified, without introducing another replication mechanism.

## Validate contracts

```bash
.venv-figures/bin/python -m pip install -r requirements-contracts.txt
python3 tools/api_contracts.py
.venv-figures/bin/python tools/check_contracts.py
```

These optional development checks validate both OpenAPI documents and real responses. Running storage, router, CLI, experiments or unit tests needs no third-party runtime packages.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Architecture](architecture.md) · Next: [Math and metrics](metrics.md)
<!-- reading:end -->
