# Shared KV Storage

A lightweight CISC3010 Project 5 framework running in WSL. One router coordinates independent text-storage processes; the CLI is a pure HTTP client. The project compares modulo and consistent hashing, measures the cost of adding a node, and shows why evenly placed keys can still receive uneven request traffic. Author: Paco.

**Reading guide:** [Documentation map and repository overview](docs/README.md) · [API reference](docs/api.md) · [Results](docs/results.md) · [CLI demonstration](docs/demo.md)

**On this page:** [Start](#start-in-wsl) · [Standalone processes](#standalone-processes) · [Placement](#placement-and-runtime-changes) · [Migration](#assumptions-and-migration) · [API](#api-and-request-counts) · [Experiments](#experiments-and-metrics) · [Reproduction](#optional-artifacts-and-reproduction)

The repository contains the runtime, documentation, experiment data and reporting tools. The published source was prepared from Paco's Windows project directory. On another PC, clone it into WSL's Linux filesystem and work directly from the clone; no files from the original PC are needed. Slides, lecture PDFs, presentation sources and speaker notes stay private and are excluded from Git.

## Start in WSL

```bash
git clone https://github.com/Nvb-flipped/shared-kv-storage.git
cd shared-kv-storage
python3 --version  # Python 3.11 or newer
bash run_cluster.sh --placement consistent --vnodes 16 --storage-base-port 5101
```

This starts four independent storage processes A–D, one independent router and a separate client prompt. A/B/C are initial members; D waits at `127.0.0.1:5104`. The router uses port 8000. The launcher prints real PIDs, checks ports before starting and stops only its owned processes when you quit. An occupied port is an error; it never kills another application.

Startup prints each process and its readiness result. A process that fails its health check stops the launch after about five seconds and the launcher cleans up its own children. The recorded demonstration used 5101–5104 because the original PC's WSL session accepted a bind on 5004 but timed out on TCP connections. A new PC need not have that issue. Omitting the optional storage-port setting uses 5001–5004. No networking or firewall settings are changed. Use the exact `addnode D ...` command printed at startup.

```text
put user:101 Apple
get user:101
get missing
owner user:101
ring user:101 --check
stats
keys
addnode D 127.0.0.1:5104
get user:101
ring user:101 --check
membership
quit
```

Use quotes for spaces or an empty value, for example `put greeting "hello world"`. Put overwrites text; there are no record versions. A missing Get prints `NOT FOUND`, includes its routed owner and returns exit code 3. The interactive prompt continues. Colors are always enabled, with node letters, patterned bars and numeric shares as additional cues. Ring columns show token order, with a caret at the exact owner token; they do not imply equally spaced hash positions.

To attach another client, run `python3 client.py` in a second WSL terminal. For a single command, use `python3 client.py get user:101`. A different router uses `python3 client.py --router http://localhost:8000 get user:101`. The CLI never computes owners or stores a membership table. There is no web UI.

## Standalone processes

```bash
python3 storage_node.py --id A --port 5101
python3 storage_node.py --id B --port 5102
python3 storage_node.py --id C --port 5103
python3 storage_node.py --id D --port 5104
python3 router.py --port 8000 --nodes A=localhost:5101,B=localhost:5102,C=localhost:5103 --placement consistent --vnodes 16
```

Run each long-lived command in its own terminal, or use the launcher. Storage holds only `key -> value`, without peers or placement knowledge. The router owns membership, integer placement, request counting and migration. Both runtime and unit tests use only Python 3.11+ standard-library modules; no installation, database or cloud service is needed.

## Placement and runtime changes

SHA-256 produces a stable unsigned integer. Modulo uses `hash_integer % node_count` over sorted IDs. Consistent hashing selects the first integer token at or after the key, with wraparound; each member contributes V tokens. `ring KEY` asks for placement even if the key does not exist. `--check` explicitly probes storage and reports yes/no. Coverage percentages are hash intervals, separate from stored-key shares.

At the prompt, `placement modulo`, `placement consistent` and `vnodes 128` rebuild placement without migrating existing data. With populated stores they set `reload_required`; Put/Get are rejected until `flush` and reload. Changing a mode alone does not delete values. `flush` deliberately deletes every registered store's values. Start a fresh cluster to repeat a three-to-four-node experiment after D has already joined.

## Assumptions and migration

- Membership is centralized in one router. Stable uppercase IDs identify processes; there is no gossip or automatic failure eviction.
- There is one owner and one acknowledgment per Put. No replication, quorum, vector clock, record history or conflict resolution is implemented.
- Writes pause during migration and receive 503. Gets remain available from the old owner during copying/verification. The router publishes the verified new map before deleting old copies; a brief gate protects in-flight Gets at publication.
- Experiments assume nodes do not lose data during migration. An unreachable store is marked down and causes an error. Recovery performs explicit staging rollback or source cleanup; it does not rebuild lost storage contents.
- Data and router state are volatile. The router and this PC are single failure points. All HTTP listeners bind to loopback, without authentication or TLS.

Migration proceeds through prepare, copy, verify, publish, cleanup and resume. A failed migration leaves writes paused. Use `recover` only after addressing the underlying issue; it retains the old map before publication or the new map afterward. [Architecture](docs/architecture.md) explains the locks and recovery boundary. [Specification decisions](docs/spec-decisions.md) record corrections to the supplied pseudocode.

## API and request counts

Client endpoints are `/put`, `/get`, `/owner`, `/stats` and `/ring`. Administrative endpoints control membership, placement, V, counters, recovery and explicit reset. Storage exposes local values, keys, batch migration input, stats and health. The [API reference](docs/api.md) documents bodies, responses, errors and retry behavior; [router OpenAPI](docs/openapi.json) and [storage OpenAPI](docs/storage-openapi.json) provide machine-readable contracts. JSON is the HTTP protocol, not a required user value type.

Node request counts include router-forwarded client Put/Get attempts, including misses. They exclude migration, inventory, health and ring existence probes. Puts require no version lookup. `reset-counters` clears workload counters; explicit ring probes are counted separately as inspections.

## Experiments and metrics

From the repository root in WSL:

```bash
python3 -m unittest -v
python3 tools/run_experiments.py
python3 tools/rehearse.py
```

The orchestrator owns fresh clusters on OS-assigned ports; `experiment.py` remains a pure HTTP client. For an existing fresh cluster, run `python3 experiment.py --mode consistent --vnodes 16 --out results/manual.json`.

Every setting uses the same 1,000 keys/values. Compare before/after physical counts, max/min ratio, population CV and moved fraction. Read every value after join and compare exact text; also require one physical host matching each routed owner. Reset counters, send the same 1,000 uniform reads, then add 500 reads to `key-00000`. Key counts must remain unchanged while those extra requests all reach its owner.

The sweep includes V=1,2,4,8,10,16,32,64,128, covering the specified 1/10/128 and the earlier doubling sequence. Three fresh runs per setting give 30 measured trials. Setting order is randomized within each round using seed 3010. Fixed identities give repeated placements, not independent layouts. Timings describe this laptop. Virtual nodes provide the scoped bonus; replication is excluded by the primary spec.

<!-- comparison:start -->
| Setting | Before A/B/C | After A/B/C/D | Max/min after | CV after | Reassigned | Value failures |
|---|---|---|---:|---:|---:|---:|
| Modulo | 332/337/331 | 246/247/254/253 | 1.033 | 0.014 | 743 (74.3%) | 0 |
| Consistent V=1 | 119/412/469 | 119/351/469/61 | 7.689 | 0.666 | 61 (6.1%) | 0 |
| Consistent V=2 | 382/434/184 | 268/404/184/144 | 2.806 | 0.398 | 144 (14.4%) | 0 |
| Consistent V=4 | 280/390/330 | 189/390/315/106 | 3.679 | 0.439 | 106 (10.6%) | 0 |
| Consistent V=8 | 202/245/553 | 171/213/455/161 | 2.826 | 0.480 | 161 (16.1%) | 0 |
| Consistent V=10 | 323/218/459 | 244/216/319/221 | 1.477 | 0.165 | 221 (22.1%) | 0 |
| Consistent V=16 | 324/247/429 | 296/245/270/189 | 1.566 | 0.158 | 189 (18.9%) | 0 |
| Consistent V=32 | 379/335/286 | 294/286/239/181 | 1.624 | 0.180 | 181 (18.1%) | 0 |
| Consistent V=64 | 321/380/299 | 287/327/218/168 | 1.946 | 0.245 | 168 (16.8%) | 0 |
| Consistent V=128 | 317/380/303 | 267/298/210/225 | 1.419 | 0.139 | 225 (22.5%) | 0 |
<!-- comparison:end -->

Max/min ratios approach 1 as balance improves, but are infinite or undefined when a minimum is zero; JSON stores those cases as null. CV measures spread relative to mean load. Reassigned fraction divides changed owners by all original keys. The request ratio uses node read counts after the added hot workload. [Math and qualifications](docs/metrics.md) explain every denominator, transfer matrix, expectation and empty-data convention. [Measured results](docs/results.md) contain full tables and figures.

Acknowledged transfers and join seconds are measured. `estimated_item_bytes` is calculated serialized logical item size, not captured network traffic. All 1,000 values and physical owners must pass verification; a theoretical placement calculation is insufficient.

## Optional artifacts and reproduction

The pinned plotting packages require Python 3.12 or newer (the recorded environment used 3.14.4). The runtime and unit tests still support Python 3.11 or newer.

```bash
python3 -m venv .venv-figures
.venv-figures/bin/python -m pip install -r requirements-figures.txt
bash tools/reproduce.sh
```

Figures, contracts, tests and documentation tables regenerate from source. Raw trial JSON and source hashes are under `results/framework/`. Optional contract validators use `requirements-contracts.txt`; neither plotting nor validation packages are runtime dependencies. Install both requirement files into `.venv-figures` for live contract checks during reproduction. The [CLI demonstration](docs/demo.md) gives a short end-to-end walkthrough. [The documentation map](docs/README.md) explains each directory and the evidence trail.

Optional math validation uses MathJax 3.2.2 without a browser: set `MATHJAX_PACKAGE` to an installed `mathjax-full` package directory and run `node tools/check_math.cjs`. This checks formulas and SVG conversion locally; it does not certify GitHub's hosted rendering. To audit the saved experiments without rerunning them, use `python3 tools/check_project.py`. Run `python3 tools/check_publication.py` before a commit or push; it checks tracked files and reachable history for slide material and likely credentials.

The project applies established partitioning ideas from [Dynamo §4.2](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf). [MIT 6.5840's shard lab](https://pdos.csail.mit.edu/6.5840/labs/lab-shard1.html) is a transfer/configuration reference only. Full Dynamo replication, consensus, quorums, gossip, read repair, automatic recovery and a web GUI are outside this framework. [Scope map](docs/scope.md) connects requirements to implementation and evidence. Paco remains the author; [assistance and attribution](docs/ai-use.md) record tools and sources truthfully.
