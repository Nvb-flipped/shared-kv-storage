# Use an HTTP client

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

<!-- contents:start -->
On this page: [Bruno setup](#bruno-setup) · [Curl examples](#curl-examples)
<!-- contents:end -->

Start the demo with `python -m sharedkv demo --config configs/demo.toml`. Keep that terminal open while sending requests from Bruno, curl or another client. The default router URL is `http://127.0.0.1:8000`; use the printed URL if settings differ. Every request below goes to the router.

## Bruno setup

Create a REST request, select the method and enter the URL. Add query parameters in Params. For POST requests, choose a JSON body and use `Content-Type: application/json`. Get requests need no body. No authentication is configured. A normal missing-key response is HTTP 404 with a JSON error envelope; it is not a crashed server.

| CLI command | Method and path | Query or JSON body |
|---|---|---|
| `put user:101 Apple` | `POST /put` | `{"key":"user:101","value":"Apple"}` |
| `get user:101` | `GET /get` | Params `key=user:101` |
| `get missing` | `GET /get` | Params `key=missing`; expect 404 `not_found` |
| `owner user:101` | `GET /owner` | Params `key=user:101` |
| `ring user:101 --check` | `GET /ring` | Params `key=user:101`, `check=1` |
| `stats` | `GET /stats` | No body |
| `keys` | `GET /keys` | No body |
| `addnode D 127.0.0.1:5104` | `POST /admin/addnode` | `{"id":"D","addr":"127.0.0.1:5104"}`; use D's actual printed address |
| `get user:101` after join | `GET /get` | Params `key=user:101`; value remains `Apple` |
| `ring user:101 --check` after join | `GET /ring` | Same query; owner may change and `exists` remains true |
| `membership` | `GET /admin/membership` | No body; completed join advances membership version |
| `quit` | Local client action | No HTTP equivalent; it ends the local prompt |

A ring query without `check=1` inspects placement only. It can be used for an absent key without claiming that a value exists. A missing Get still counts as a forwarded client request; ring inspection has a separate counter.

## Curl examples

```bash
curl -sS http://127.0.0.1:8000/put \
  -H 'Content-Type: application/json' \
  -d '{"key":"user:101","value":"Apple"}'
curl -sS -G http://127.0.0.1:8000/get --data-urlencode 'key=user:101'
curl -sS -G http://127.0.0.1:8000/ring \
  --data-urlencode 'key=user:101' --data-urlencode 'check=1'
```

During migration a Put receives 503 `migration_in_progress`. An incomplete body that stops sending data receives 408 `request_timeout` after the server's inactivity deadline. An ambiguous connection timeout is different from an explicit rejection; inspect state before retrying an administrative mutation.

The [API reference](api.md) documents every operation, schema and error. Import [router OpenAPI](openapi.json) or [storage OpenAPI](storage-openapi.json) when your client supports OpenAPI 3.1. Ordinary clients should use the router; directly mutating stores can invalidate migration assumptions.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [API reference](api.md) · Next: [Math and metrics](metrics.md)
<!-- reading:end -->
