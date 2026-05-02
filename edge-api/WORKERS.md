# Lab 17 — Cloudflare Workers Edge Deployment

This document covers the deployment of the `edge-api` Worker to the Cloudflare global edge network for DevOps Core Lab 17.

---

## 1. Deployment Summary

| Field | Value |
|-------|-------|
| Worker name | `edge-api` |
| Public URL | https://edge-api.devops-core.workers.dev |
| Account | amitytneva030@gmail.com (`0756a013e30376e39f9c99cd3f58807c`) |
| KV namespace ID | `18b156e41d6a43dca08badf1e9b5bd69` |
| Current version | v1.0.1 (`2a919d05-6568-4824-bff7-3f78435f6ef6`) |
| Runtime | Cloudflare Workers (V8 isolates) |
| Language | TypeScript |
| Compatibility date | `2025-01-21` |
| KV binding | `SETTINGS` |
| Plaintext vars | `APP_NAME`, `COURSE_NAME`, `OWNER` |
| Secrets | `API_TOKEN`, `ADMIN_EMAIL` |

### Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | App info: name, course, owner, version, route list |
| GET | `/health` | Liveness probe — returns `{ status: "ok" }` |
| GET | `/edge` | Edge metadata from `request.cf` (colo, country, city, asn, httpProtocol, tlsVersion, …) |
| GET | `/counter` | KV-backed visit counter — increments persistent value in `SETTINGS` |
| GET | `/admin` | Auth-gated route requiring `Authorization: Bearer <API_TOKEN>` (uses secret) |

### Configuration

`wrangler.jsonc` declares:
- `vars` for non-sensitive runtime configuration
- `kv_namespaces` binding `SETTINGS` to a real KV namespace (ID is replaced after `wrangler kv namespace create`)
- `observability.enabled = true` so logs are accessible via the dashboard and `wrangler tail`

Secrets are not committed — they are uploaded with `wrangler secret put`. For local dev only, `.dev.vars` provides plaintext values and is git-ignored.

---

## 2. Evidence

### 2.1 Local dev verification (`npx wrangler dev`)

```
$ curl -s http://127.0.0.1:8787/health
{
  "status": "ok",
  "app": "edge-api",
  "version": "1.0.0",
  "timestamp": "2026-04-28T18:34:57.993Z"
}

$ curl -s http://127.0.0.1:8787/edge
{
  "colo": "LHR",
  "country": "GB",
  "city": "London",
  "region": "England",
  "continent": "EU",
  "timezone": "Europe/London",
  "asn": 26383,
  "asOrganization": "Baxet Group Inc.",
  "httpProtocol": "HTTP/1.1",
  "tlsVersion": "TLSv1.3",
  "tlsCipher": "AEAD-AES256-GCM-SHA384"
}

$ curl -s http://127.0.0.1:8787/counter
{ "visits": 1, "key": "visits", "binding": "SETTINGS", ... }

$ curl -s http://127.0.0.1:8787/counter
{ "visits": 2, "key": "visits", "binding": "SETTINGS", ... }

$ curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8787/admin
{ "error": "unauthorized" }
HTTP 401

$ curl -s -H "Authorization: Bearer <API_TOKEN>" http://127.0.0.1:8787/admin
{ "admin": "admin@example.com", "app": "edge-api", ... }
```

> Local `cf` metadata is mocked by Miniflare (LHR / GB). After production deploy, replace this section with the real `/edge` JSON from your `workers.dev` URL.

### 2.2 Production `/edge` response

```
$ curl -s https://edge-api.devops-core.workers.dev/edge
{
  "colo": "LHR",
  "country": "GB",
  "city": "London",
  "region": "England",
  "continent": "EU",
  "timezone": "Europe/London",
  "asn": 26383,
  "asOrganization": "Baxet Group Inc.",
  "httpProtocol": "HTTP/2",
  "tlsVersion": "TLSv1.3",
  "tlsCipher": "AEAD-CHACHA20-POLY1305-SHA256"
}
```

The `colo` field (`LHR` — London Heathrow data center) confirms execution at the Cloudflare edge POP nearest to the client, with HTTP/2 and TLS 1.3 negotiated by the edge — none of these were configured by the developer.

### 2.2.1 KV persistence verification

Counter values across redeploys (proves `SETTINGS` KV survives version updates):

```
# After v1.0.0 deploy
GET /counter  →  { "visits": 1 }
GET /counter  →  { "visits": 2 }

# After v1.0.1 deploy (code change: VERSION bump)
GET /counter  →  { "visits": 3 }   # ← did NOT reset to 1
GET /counter  →  { "visits": 4 }
```

### 2.2.2 Deployment history (`wrangler deployments list`)

```
Created:  2026-05-02T08:46:15.543Z   Source: deployment        Version: 4c528301-62e9-48e2-b620-4915c98e8d63   (v1.0.0)
Created:  2026-05-02T08:51:05.773Z   Source: deployment        Version: 2a919d05-6568-4824-bff7-3f78435f6ef6   (v1.0.1)
```

Plus three earlier `Secret Change` events (uploads of `API_TOKEN`, `ADMIN_EMAIL`) which Cloudflare also records as immutable versions.

Rollback command (instant, no rebuild):
```
npx wrangler rollback
```

### 2.3 Screenshots

Place the following screenshots into `edge-api/screenshots/`:

1. `dashboard-worker.png` — Cloudflare dashboard → Workers & Pages → `edge-api` overview
2. `dashboard-metrics.png` — Worker metrics tab (requests / errors / CPU time)
3. `kv-namespace.png` — Workers KV → `SETTINGS` namespace showing the `visits` key

> Live log evidence (terminal `wrangler tail`) and the deployment history are already captured as plain-text output above (sections 5.1 and 2.2.2), so terminal screenshots are optional.

---

## 3. Edge Behavior

### 3.1 What `request.cf` exposes

Cloudflare populates `request.cf` with metadata about the incoming request as observed at the edge POP that handled it. The `/edge` route exposes:

- `colo` — IATA code of the data center (e.g. `FRA`, `DME`, `WAW`) closest to the user
- `country`, `city`, `region`, `continent`, `timezone` — geo-IP information
- `asn`, `asOrganization` — network the client is on
- `httpProtocol`, `tlsVersion`, `tlsCipher` — connection details

The `colo` field is the most direct proof that execution happened at the edge: each user sees the POP nearest to them, not a fixed region you chose.

### 3.2 Global distribution

Cloudflare Workers runs in **all 300+ Cloudflare data centers** simultaneously. There is no "region" concept the developer manages — `wrangler deploy` propagates code globally within seconds. A request from Frankfurt is served from FRA; a request from Tokyo is served from NRT. This is fundamentally different from VM/PaaS platforms where you pick `us-east-1` and pay latency for users elsewhere — there is no "deploy to 3 regions" step because there is nothing to choose.

### 3.3 Routing options

| Option | What it is | When to use |
|--------|-----------|-------------|
| `workers.dev` | Free auto-generated subdomain (`<worker>.<account>.workers.dev`) | Demos, internal tools, lab work |
| Routes | Pattern (e.g. `api.example.com/*`) attached to a Worker on an existing Cloudflare zone | Worker handles a slice of an existing site |
| Custom Domain | A hostname pointed entirely at a Worker as origin | Production app on its own domain |

For this lab the required deployment uses `workers.dev`.

---

## 4. Configuration, Secrets & Persistence

### 4.1 Plaintext vars vs secrets

`vars` in `wrangler.jsonc` are **stored in plaintext in the Worker's bundle** and visible in the Cloudflare dashboard and in version diffs. They are appropriate for non-sensitive runtime config (app name, course name, feature flags).

Secrets are uploaded out-of-band with `wrangler secret put` and are **encrypted at rest, never displayed, and never serialized into the Worker bundle**. Use them for tokens, API keys, DB credentials.

### 4.2 KV persistence

A KV namespace `SETTINGS` is bound to the Worker. The `/counter` route reads the `visits` key, increments it, writes it back. KV is **eventually consistent across the global network** (writes propagate within seconds), and values survive any number of redeploys, version rollbacks, or Worker restarts because storage is decoupled from the runtime.

Verification: hit `/counter` ≥ 2 times → run `wrangler deploy` → hit `/counter` again → observe that the value continues to increase rather than resetting to 1.

---

## 5. Operations

### 5.1 Logging

`console.log()` calls inside the Worker stream to:
- `npx wrangler tail` (live in your terminal)
- The Workers Logs tab in the dashboard (when `observability.enabled = true`)

Example log lines captured live from `npx wrangler tail` while hitting the production URL:
```
Successfully created tail, expires at 2026-05-02T14:52:06Z
Connected to edge-api, waiting for logs...
GET https://edge-api.devops-core.workers.dev/health  - Ok @ 5/2/2026, 11:52:15 AM
  (log) request GET /health  colo LHR country GB
GET https://edge-api.devops-core.workers.dev/edge    - Ok @ 5/2/2026, 11:52:16 AM
  (log) request GET /edge    colo LHR country GB
GET https://edge-api.devops-core.workers.dev/counter - Ok @ 5/2/2026, 11:52:16 AM
  (log) request GET /counter colo LHR country GB
```

### 5.2 Metrics

The dashboard's Metrics tab shows requests per second, errors, CPU time per request, and subrequest counts. Useful first metric: **request count by status code** to confirm `/health` and `/edge` return 200 in production.

### 5.3 Deployment history & rollback

```
npx wrangler deployments list   # see the last N versions
npx wrangler rollback           # roll back to the previous version
```

Workers stores every deployment as an immutable version, so rollback is instant — no re-build, no re-upload.

---

## 6. Kubernetes vs Cloudflare Workers

| Aspect | Kubernetes | Cloudflare Workers |
|--------|------------|--------------------|
| Setup complexity | High — cluster, networking, ingress, RBAC, storage classes | Very low — `npm create cloudflare` + `wrangler deploy` |
| Deployment speed | Minutes (image build + push + rollout) | Seconds (`wrangler deploy` propagates globally in <30s) |
| Global distribution | Manual — multi-region clusters or a CDN in front | Automatic — every request runs in the nearest of 300+ POPs |
| Cost (small apps) | Pay for nodes 24/7 even when idle | Free tier covers 100k req/day; pay-per-request after |
| State / persistence | Full freedom — PVCs, StatefulSets, any DB | Bindings only — KV, R2, D1, Durable Objects, Queues |
| Control / flexibility | Any container, any binary, any port, sidecars, daemons | V8 isolates only, no filesystem, no long-running processes, 30s wall time per request (Workers Standard plan) |
| Best use case | Complex stateful systems, batch jobs, custom runtimes, regulated workloads | Globally distributed APIs, edge transforms, lightweight serverless logic |

### When to use each

**Favors Kubernetes:**
- Workload needs a specific OS, language runtime, or native binary not supported by Workers
- Long-running connections, background workers, cron beyond a few minutes, sidecars
- Strict data residency / on-prem requirements
- Existing container ecosystem and team operational maturity

**Favors Workers:**
- HTTP API or webhook handler that should be globally low-latency
- Bursty / unpredictable traffic where idle node cost matters
- Small team that doesn't want to operate a cluster
- Simple state model fits KV / D1 / Durable Objects

**My recommendation:** Use Workers as the public-facing edge layer (auth, routing, caching, lightweight transforms) and keep heavier stateful or specialized work on Kubernetes behind it. The two are complements, not substitutes.

---

## 7. Reflection

**Easier than Kubernetes:**
- No cluster, no nodes, no Helm chart, no ingress controller, no `kubectl` — the entire deploy is `wrangler deploy`
- Global distribution is free and automatic; on K8s reaching the same global footprint requires a multi-region cluster or a CDN layer in front of services
- Logs and metrics work out of the box with `observability.enabled = true`

**More constrained:**
- No long-running processes, no raw TCP, no filesystem, strict CPU/wall-time limits per request
- State must fit one of the platform bindings (KV, R2, D1, Durable Objects); no "just attach a Postgres PVC"
- Limited choice of language / runtime — JS/TS first-class, Python and others narrower in scope

**What changed because Workers is not a Docker host:**
- The Lab 2 Docker image is **not** redeployed here — Workers does not run containers. The API was rewritten directly against the Workers `fetch` handler signature.
- Operational concepts re-mapped instead of being re-used: Pods → isolates, ConfigMaps → `vars`, Secrets → `wrangler secret put`, PVCs → KV, Deployments → versions/rollback, kubelet logs → `wrangler tail`.
- There is no "build" step in the Docker sense — the source is uploaded, compiled to V8 modules in the Cloudflare control plane, and distributed to all POPs.
