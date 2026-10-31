# CLI demonstration

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

<!-- contents:start -->
On this page: [Start and inspect](#start-and-inspect) · [Add a member](#add-a-member) · [Use another client](#use-another-client) · [Show the controlled comparison](#show-the-controlled-comparison)
<!-- contents:end -->

Run from the repository root on Linux, WSL or Windows with Python 3.11 or newer. It starts A, B and C as active members and D as a waiting storage process. The router listens on port 8000.

## Start and inspect

```bash
python -m sharedkv demo --config configs/demo.toml
```

Wait for the readiness messages and prompt. If a port is occupied, stop your earlier cluster or choose a free storage range. Use the address printed for D in the join command.

```text
put user:101 Apple
get user:101
get missing
owner user:101
ring user:101 --check
stats
keys
```

Put stores text and Get returns it. A missing key is an ordinary result: the CLI prints `NOT FOUND` and the interactive prompt continues. A single-command client exits with code 3 for that result. Both a successful Get and a miss count as a client request to the routed store.

`owner` and `ring` calculate placement even for an absent key. `ring --check` separately probes whether a value exists. Its token-order display marks the exact owner token; hash-space coverage is distinct from stored-key share. `keys` lists routed owners and physical hosts; `stats` shows key counts and client workload counts. Inspection probes do not add client workload requests.

## Add a member

```text
addnode D 127.0.0.1:5104
get user:101
ring user:101 --check
membership
quit
```

The router copies reassigned values, verifies destinations, publishes the new map and removes old copies. Membership advances from version 1 to 2. User keys have no record-version field. A key may keep its owner; one stored key is too small a dataset to demonstrate an expected movement percentage.

Writes receive HTTP 503 while migration is active. Gets remain readable through the old map until publication. Integration tests check overlapping operations using deterministic barriers. The separate scripted rehearsal exercises all CLI commands, complete migration, value preservation and the interactive prompt on a larger dataset:

```bash
python tools/rehearse.py --out results/runs/cli-rehearsal
```

`quit` ends this client. The managed launcher then stops the child processes it started. Quitting a separately attached client leaves the cluster running.

## Use another client

Open a second WSL terminal in the repository root:

```bash
python -m sharedkv client
python -m sharedkv client get user:101
```

Bruno or another HTTP client can use `http://127.0.0.1:8000` while the cluster runs. Put uses `POST /put` with JSON `{"key":"user:101","value":"Apple"}`; Get uses `GET /get?key=user%3A101`. An absent key returns HTTP 404. JSON is the transport envelope; the stored value is plain text. The [API reference](api.md) covers every endpoint and error, with [router OpenAPI](openapi.json) for import. There is no HTTP equivalent of quitting a local prompt.

## Show the controlled comparison

Use the [course report](report.md) for the final 1,000-key comparison and hot-key workload, with links to its raw observations. The [earlier comparison](results.md) is historical reference material. Run `python -m sharedkv study --config configs/quick.toml --out results/runs/demo-study` to collect fresh trials; each trial owns and cleans up its own processes on OS-assigned ports. The [experiment design](experiment-design.md) explains the controls and timing limits.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [Historical results](results.md) · Next: [Requirements and evidence](scope.md)
<!-- reading:end -->
