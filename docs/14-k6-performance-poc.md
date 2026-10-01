# 14 — k6 Performance-Testing POC: "Plant Telemetry API"

**Goal:** learn performance testing with k6 by load-testing a small FastAPI + Nginx + Postgres
service, then add optimisations one level at a time and record what each one changes.
The service is built on **this project's existing data** (no agents, no LLM).

> Why this data works well for it: the tables are the kind an asset-performance-monitoring
> product (UptimeAI-style) serves all day. There are 5 wide time-series tables, each with
> 43,200 rows × 108–160 columns (~27.5M values). There's a small metadata catalog, an unpivot
> view that is expensive on purpose, and alerts and maintenance work orders. So you get
> cheap, medium and expensive endpoints from one realistic dataset.

---

## 1. What we reuse from the repo

| Existing piece | Use in the POC |
|---|---|
| `bfpa / bfpb / cepa / cepb / turbine` wide tables ([ddl.py](../src/mas/db/ddl.py)) | Hot-path telemetry reads (latest, trend, stats) |
| `sensor_catalog` table | Metadata endpoints, and the source of k6 test data (the tag list) |
| `<system>_long` views (LATERAL unpivot) | Deliberately expensive endpoint, with heavy payloads |
| `run_metadata` (`window_start/window_end`) | **All "now" is the pinned anchor (2026-09-07)**, not `now()`. Queries relative to `now()` return empty results |
| `SYSTEM_META`, `tags_for()` ([catalog/api.py](../src/mas/catalog/api.py)) | `/systems` endpoint, request validation |
| `alerts.detect()` + `maintenance.build()` outputs ([seed_all.py](../scripts/seed_all.py)) | Put them into **Postgres** tables `alerts`, `maintenance_logs`, `consumed_items` so the POC needs only Postgres (Neo4j stays out of scope) |
| `mas.db.postgres` helpers, `mas_reader` role | DB access. Note that `mas_reader` has a **15 s `statement_timeout`**, so under stress you'll see timeouts, which is useful to observe |
| `datagen.modes` operating modes, scikit-learn, matplotlib | Real CPU-heavy work for the long-running jobs |

**Isolation:** run the POC against a copy of the database so the write tests don't disturb
the agents' golden evals:
`CREATE DATABASE mas_perf TEMPLATE mas;`

---

## 2. The API, grouped by performance profile

Each endpoint is picked to teach something specific.

### A. Cheap and cacheable (measures framework overhead)
| Endpoint | Query | Lesson |
|---|---|---|
| `GET /health` | none | Raw ceiling: FastAPI + Nginx overhead only |
| `GET /systems` | static `SYSTEM_META` | Serialisation cost, in-memory cache baseline |
| `GET /systems/{s}/tags?family=temperature` | `sensor_catalog` filter | Small query that changes rarely, so it's ideal for caching |

### B. Dashboard hot path (the "realistic" load)
| Endpoint | Query | Lesson |
|---|---|---|
| `GET /systems/{s}/latest?tags=a,b,c` | `SELECT cols FROM s ORDER BY ts DESC LIMIT 1` | Highest-RPS path. Uses the PK index. Short-TTL caching; invalidated by ingest |
| `GET /systems/{s}/trend?tag=&from=&to=&bucket=5m` | `date_bin()` + `avg/min/max` group-by | Cost grows with the time range: compare 1 h vs 30 d. Leads to rollup tables and materialised views |
| `GET /systems/{s}/stats?tag=&window=7d` | min/max/avg/`percentile_cont(0.95)` | Aggregates that sort (the p95) are expensive. Covers "max bearing temp yesterday" |
| `GET /compare?tag=bearing_temp_1&systems=bfpa,bfpb&window=7d` | the same query on N tables | Sequential vs `asyncio.gather` fan-out. Pool sizing |
| `GET /systems/{s}/health` | latest row + catalog alarm limits, scored in Python | CPU-bound work in the request path. Shows why you add workers/compute |

### C. Deliberately expensive
| Endpoint | Query | Lesson |
|---|---|---|
| `GET /systems/{s}/readings?page=N` (offset) vs `?after_ts=` (keyset) | 43,200-row paging | OFFSET gets slower the deeper you page; keyset stays flat |
| `GET /systems/{s}/long?from=&to=` | `_long` unpivot view | Payload size (130 values × rows). Covers gzip, orjson, response limits |
| `GET /systems/{s}/export.csv` | streaming full table | `StreamingResponse`, memory stays flat, Nginx buffering |
| `GET /alerts?system=&severity=&cursor=` | `alerts` table | Composite index design, cursor pagination |
| `GET /maintenance/{system}/costs` | join `maintenance_logs` × `consumed_items` | Join + aggregate. Materialise it or cache it |

### D. Write path
| Endpoint | Behaviour | Lesson |
|---|---|---|
| `POST /ingest/{s}` (1 row) / `POST /ingest/{s}/batch` (N rows) | Append rows with `ts > window_end` (a simulated live feed) | Write throughput, per-row INSERT vs batch vs `COPY`, lock and WAL cost, **cache invalidation** for `/latest` |

---

## 3. k6: the test types and concepts to cover

Write the k6 suite once and reuse it at every optimisation level.

| Test type | k6 executor | Shape | What it answers |
|---|---|---|---|
| **Smoke** | `constant-vus` 1–2 VUs, 1 min | tiny | Does the script and the stack work at all? |
| **Average load** | `ramping-vus` → plateau 10 min | expected traffic | Are we inside the SLO (e.g. p95 < 300 ms) under normal load? |
| **Stress** | step ramp past normal | 2×–5× load | Where does latency bend, and what fails first? |
| **Spike** | 10 → 500 VUs in 10 s | sudden burst | Does the system recover, or queue and time out? |
| **Soak** | moderate, 1–2 h | long | Memory leaks, connection leaks, cache growth, PG bloat |
| **Breakpoint** | `ramping-arrival-rate` until thresholds fail | open-ended | Maximum sustainable RPS for this level |

Concepts to learn along the way:
- **Closed vs open model:** VU-based executors (`*-vus`) slow down when the server slows
  down, which hides the problem (coordinated omission). Arrival-rate executors keep
  sending requests at a fixed rate. Run the same test both ways once and compare.
- **Thresholds** (`http_req_duration: ['p(95)<300']`, `http_req_failed: ['rate<0.01']`) make
  a test pass or fail.
- **Checks** confirm correctness under load (status 200 and a non-empty body).
- **Custom metrics** (`Trend`, `Counter`, `Rate`, `Gauge`), for example `cache_hit` read
  from an `X-Cache` response header, or `job_completion_time`.
- **Tags and groups:** per-endpoint percentiles (`tags: {endpoint: 'trend'}`).
- **Scenarios:** several workloads running at once (see the mix below).
- **Data parameterisation:** `SharedArray` loaded with `tags.json`, exported from `sensor_catalog`.
- **`handleSummary()`:** writes `results/L{n}-{test}.json` so every run is recorded.
- **Outputs:** `--out experimental-prometheus-rw` to Prometheus + Grafana, for time-series
  views of runs and to put side by side with container CPU.

### Realistic workload mix (the `mixed.js` scenario)
```
dashboard_readers  (ramping-arrival-rate) 60% latest, 20% trend (mostly short ranges),
                                          10% metadata, 5% stats/compare, 5% alerts
ingest_feed        (constant-arrival-rate) 5 systems × 2 rows/s
report_users       (constant-vus, 2 VUs)   submit a long-running job, poll until done
```
The key experiment: **does `report_users` hurt `dashboard_readers` p95?**
That question is what motivates the background-job levels below.

---

## 4. The optimisation ladder (one git tag or compose profile per level)

Run the **same** k6 tests at every level and record RPS, p50/p95/p99, error rate, container
CPU/memory, PG connections and cache hit ratio.

| Level | Change | Hypothesis / what to observe |
|---|---|---|
| **L0 Naive** | 1 uvicorn worker. `async def` handlers call **sync** psycopg with a **new connection per request**. `SELECT *`. stdlib `json` | The event loop is blocked, so throughput stays flat. Connection setup dominates latency |
| **L1 Correct async + pool** | `psycopg` async + `AsyncConnectionPool` (or asyncpg). Select only the needed columns. orjson | Large drop in p50. Learn pool size vs latency |
| **L2 Database tuning** | `EXPLAIN (ANALYZE, BUFFERS)`, `pg_stat_statements`. BRIN index on `ts`. Rollup tables / materialised views (5 min, 1 h) for trends. Keyset pagination. Tune `shared_buffers` / `work_mem` | Trend p95 drops sharply on long ranges. Deep OFFSET pages become flat |
| **L2b (optional) TimescaleDB** | Hypertables + continuous aggregates | The time-series-native answer to L2's manual rollups |
| **L3 In-process cache** | `cachetools.TTLCache` per endpoint (metadata 1 h, trends 60 s, latest 2 s) | Hit rate climbs. Each worker holds its own copy, so the next level exposes stale data and duplicated memory |
| **L4 More compute + Nginx** | Nginx reverse proxy (upstream keepalive, gzip). `gunicorn -k uvicorn.workers.UvicornWorker -w N`. `docker compose up --scale api=3` | Throughput scales with cores… until **Postgres `max_connections` (100)** runs out: 3 replicas × 4 workers × pool 10 = 120. That sets up the next level |
| **L5 PgBouncer** | Transaction pooling in front of PG. App pools get smaller | Many client connections map to few server connections, so connection errors go away. Gotcha: prepared statements in transaction mode (psycopg `prepare_threshold=None`, or PgBouncer ≥ 1.21 `max_prepared_statements`) |
| **L6 Redis shared cache** | Cache-aside with per-endpoint TTL. Invalidate `/latest` on ingest. Stampede protection (lock or single-flight) | One cache shared across replicas, and consistency returns. Compare with L3. Run a spike test on a cold cache to *see* a stampede |
| **L6b Nginx micro-cache** | `proxy_cache` with a 1 s TTL on `/latest`, `/systems` | Repeated requests are served by Nginx before they reach Python. Very high RPS at the cost of up to 1 s staleness |
| **L7 Offload long work** | Background workers (§5) + Nginx `limit_req` | In the `mixed` scenario, dashboard p95 no longer moves when reports run |
| **L8 Scale-out** | PG streaming read replica for reads. More worker containers | Read capacity scales. Replication lag becomes visible |

**Rules that keep the experiments valid**
- Pin resources in compose (`deploy.resources.limits: cpus: "1.0", memory: 512M` per service),
  otherwise results are noise. On Windows, Docker Desktop runs in one WSL2 VM, so cap it in `.wslconfig`.
- Run k6 in its **own container** (`grafana/k6`), or better on another machine, so it
  doesn't compete for CPU. Watch k6's own CPU usage.
- Warm up (1–2 min unmeasured), run each test 3×, report the median.
- Change **one** thing per level. Record each result in `perf/results/LEVELS.md`.

---

## 5. Long-running tasks: possible jobs from this data

Real, CPU- or IO-heavy jobs that fit an asset-monitoring product:

| Job | What it does (existing code / libraries) | Profile |
|---|---|---|
| **Asset health report** | 30-day summary per system: stats, alert timeline, matplotlib charts, rendered to HTML/PDF | 5–30 s, mixed CPU/IO |
| **Anomaly re-scan** | Re-run threshold/z-score detection across 43,200 × 130 tags (the same idea as `datagen/alerts.py`) | CPU-heavy |
| **Operating-mode clustering** | KMeans over load/flow/speed. The data has 6 separable modes (MOD-04) | CPU-heavy, scikit-learn |
| **Bulk export** | Full table to CSV/Parquet in object storage (a MinIO container) | IO-heavy, large output |
| **Document extraction** | Render each maintenance work order (failure mode, items, cost, technician) as a **synthetic PDF**, then upload → extract text (pypdf) → chunk → index | IO + CPU |
| **Knowledge retrieval** | `GET /kb/search?q=bearing seal leak` over the extracted chunks. Start with **Postgres full-text search** (`tsvector` + GIN), then add **pgvector** with local embeddings as a heavier job | Search is fast; indexing is the long job |

The API pattern for all of them: `POST /jobs/{type}` returns **202 + job_id** →
`GET /jobs/{id}` (status/progress) → `GET /jobs/{id}/result`. Optionally stream progress over
SSE or WebSocket.

### Mechanisms, in the order to learn them
| # | Mechanism | Infra | What k6 will show you |
|---|---|---|---|
| 1 | Run it **inline** in the request | none | The request times out, and every other endpoint's p95 blows up. This is the anti-pattern |
| 2 | FastAPI `BackgroundTasks` | none | The response returns fast, but the work still runs in the API worker. The job is lost on restart, and CPU work still hurts the dashboard |
| 3 | `run_in_threadpool` / `ProcessPoolExecutor` | none | CPU work moves off the event loop, but it's still tied to the API process |
| 4 | **Postgres job queue**: `jobs` table + `SELECT … FOR UPDATE SKIP LOCKED` worker container | PG only | Durable, visible, no new moving parts. A great way to see how queues work |
| 5 | **Redis queue**: Celery (+ Flower UI), or arq (asyncio-native, lighter) | Redis (already there from L6) | Industry-standard. Retries, time limits, concurrency per queue, separate CPU and IO queues |
| 6 | Progress delivery: polling vs SSE vs WebSocket | — | Polling multiplies request load (k6 counts it); push does not |

**k6 for jobs:** a `jobs.js` scenario submits a job, polls with `sleep`, and records a custom
`Trend('job_end_to_end_ms')` and `Rate('job_failed')`. It runs next to `dashboard_readers`, so
queue depth and worker count become things you can tune and measure. For WebSockets use
`k6/websockets`; SSE needs the `xk6-sse` extension.

**Recommendation:** follow 1 → 2 → 4 → 5 (Celery). Step 4 teaches how a queue works inside;
step 5 is what you'll meet in production.

---

## 6. Proposed layout
```
perf/
  api/                    FastAPI app. Imports `mas` from src/ (catalog, db, timewin)
    main.py  routers/{meta,telemetry,alerts,ingest,jobs,kb}.py
    cache.py  db.py  settings.py
  worker/                 queue worker(s) for §5
  nginx/nginx.conf        reverse proxy → later proxy_cache, limit_req
  pgbouncer/              pgbouncer.ini, userlist.txt
  sql/                    perf-only DDL: alerts/maintenance tables, rollups, indexes
  scripts/                export_tags_json.py, materialise_events.py, make_workorder_pdfs.py
  k6/
    lib/{config,data,checks}.js
    smoke.js load.js stress.js spike.js soak.js breakpoint.js mixed.js jobs.js
  docker-compose.perf.yml profiles: l0 … l8, observability (prometheus, grafana, cadvisor, postgres_exporter)
  results/LEVELS.md + L{n}-{test}.json
```

## 7. Suggested build order
1. `mas_perf` DB copy + put alerts and maintenance into PG tables + `tags.json` export.
2. L0 API (sections A–B only) + Nginx + compose + k6 smoke & load. **Record the baseline.**
3. Add section C + D endpoints, and the stress / spike / breakpoint tests.
4. Climb L1 → L6, one level per session, recording each.
5. Add jobs (§5 mechanisms 1 → 5) + `mixed.js` + `jobs.js`. Measure the effect on dashboard p95.
6. Document extraction + FTS search. Add pgvector last.
7. Observability stack whenever the raw k6 numbers stop being enough to explain the results
   (usually around L4).
