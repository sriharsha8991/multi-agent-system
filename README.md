# Multi-Agent Industrial Asset Analytics — Data Layer

Physics-driven synthetic telemetry (PostgreSQL) + a mutually-consistent asset
ontology (Neo4j) for the multi-agent case study ([Problem.md](Problem.md)).
This repository currently implements the **data layer**: schemas, a physics
generator, event-derived alerts/maintenance, and a 22-gate consistency suite.
Agents and the orchestrator are the next milestone.

> Design rationale lives in [docs/01-problem-analysis.md](docs/01-problem-analysis.md)
> and [docs/02-data-design.md](docs/02-data-design.md); the generated tag reference
> is [docs/03-data-dictionary.md](docs/03-data-dictionary.md).

## Quick start (Docker only)

```bash
make up        # start postgres + neo4j, build the app runner image
make seed      # spin up schemas, then populate BOTH databases
make validate  # run the 22 quality gates (fails on any red)
```

`make up && make seed && make validate` on a clean clone reaches a green report
with only Docker installed. `make data-dict` regenerates the data dictionary;
`make test` runs the pytest suite; `make clean` drops the data volumes.

### Host development (optional)

```bash
pip install -e .            # or: uv sync
python scripts/init_databases.py
python scripts/seed_all.py
python scripts/validate.py
```
Set `PG_HOST`/`NEO4J_URI` to the exposed ports (defaults in `.env.example` target localhost).

## What gets built

- **PostgreSQL** — 5 wide telemetry tables (`bfpa`, `bfpb`, `cepa`, `cepb`,
  `turbine`), one `ts` + 108–160 `DOUBLE PRECISION` sensor columns each
  (**636 tags, ~27.5M values, 30 days @ 60 s**), plus `sensor_catalog`,
  `run_metadata`, and a `*_long` view per table. A read-only `mas_reader` role
  (SELECT-only, read-only tx, 15 s statement timeout) is the future SQL agent's
  only entry point.
- **Neo4j** — exactly 5 labels (`System`, `Tag`, `MaintenanceLog`, `Item`,
  `Alert`) and 4 relationships (`GENERATED_ON`, `PERFORMED_ON`, `MEASURED_AT`,
  `CONSUMED`). Metadata only — **no telemetry values** (enforced by gate G-07).

Everything is produced by **Python scripts** (Problem.md §2); the tag/item
catalog is defined in code (`src/mas/catalog/`) and both databases are projected
from it, so they cannot disagree.

## Design decisions

| Decision | Choice |
|---|---|
| Generation engine | Full physics-driven: one latent plant-load driver → physics coupling → noise → event timeline → derived alerts |
| Currency | **INR** (item/maintenance costs) |
| Tag counts | 130 / 130 / 108 / 108 / 160 = **636** |
| `NOW_ANCHOR` | **Pinned by default** (`.env.example`) → byte-identical `make seed`; set `NOW_ANCHOR=live` for a fresh wall-clock window |

## How the data is meaningful

One event timeline drives telemetry, alerts, and maintenance together, so every
alert is plottable and every repair is visible in the data. The seven injected
events (bearing degradation, seal leakage, cavitation, oil-filter clogging,
vacuum deterioration, restart eccentricity, sensor fault) each produce a
telemetry excursion, the alert the detector rediscovers, and (where applicable)
the work order that consumes spare parts. Demo guarantees (DG-1..DG-5) are
enforced by build-failing gates — most importantly **DG-1**: the latest BFP-A
alert is always the bearing-temperature excursion, so the flagship
alert→plot query shows a real anomaly.

## Layout

```
scripts/         init_databases.py · seed_all.py · validate.py · gen_data_dictionary.py
src/mas/
  config.py      seed / anchor / window + RNG discipline
  catalog/       in-code source of truth: families, systems, items, api
  db/            DDL generation, Neo4j constraints, connection helpers
  datagen/       modes · physics · events · instrument · build_telemetry · alerts · maintenance · graph_seed
  eval/          consistency.py (gates G-01..G-22)
tests/           catalog + generation (no DB) and full-gate suite (needs DBs)
```

## Reproducibility

Every RNG derives from `MASTER_SEED` via `SeedSequence` keyed by
`(system, tag_name, …)`, so adding a tag never perturbs an existing one. The
resolved anchor/seed are persisted to `run_metadata`; gate **G-22** proves two
seeds produce identical content hashes.
