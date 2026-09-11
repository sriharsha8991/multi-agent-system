# Multi-Agent Industrial Asset Analytics

A supervisor agent and three specialists that answer open-ended engineering questions
about a simulated thermal power plant — over **physics-driven synthetic telemetry**
(PostgreSQL) and a **mutually-consistent asset ontology** (Neo4j).

Built for the case study in [Problem.md](Problem.md). Both the data layer and the agent
layer are implemented.

> Ask *"why is the turbine vibrating and losing output?"* and the team narrows 636 tags to
> a handful via the graph, measures only those in Postgres, then analyses and plots the
> result — instead of scanning 27M values.

---

## Quick start

One command takes a fresh clone to a seeded, verified, ready-to-query stack — it checks
your prerequisites, writes `.env`, installs dependencies, starts both databases, creates
the schemas, generates the data and runs the 22 quality gates:

```bash
python scripts/setup.py
```

That is the whole setup. It needs **Python 3.11+** and **Docker** running; it will prompt
once for a [Gemini API key](https://aistudio.google.com/apikey) (press Enter to skip — the
data layer works without one, only the agents need it).

Every step is idempotent, so re-run it any time; it will not regenerate data that already
exists. Useful flags:

| Flag | Effect |
|---|---|
| `--skip-deps` | don't run `pip install` (you manage the environment yourself) |
| `--skip-seed` | schemas only, no data generation |
| `--force-seed` | regenerate data even though the databases already hold some |
| `--reset` | destroy the database volumes and set up from scratch |
| `--no-input` | never prompt — for CI and scripted installs |

<details>
<summary>Prefer to run the steps yourself?</summary>

```bash
cp .env.example .env                      # then add your GEMINI_API_KEY
python -m pip install -r requirements.txt
docker compose up -d postgres neo4j
python scripts/init_databases.py
python scripts/seed_all.py
python scripts/validate.py
```

There is no packaging step: `src/` reaches the import path via `pytest.ini`,
`scripts/_bootstrap.py` and the notebook's own root-detection cell.
</details>

A clean run ends with `22/22 gates green`.

### Or run everything in Docker

If you would rather not install Python deps on the host, the `app` service is a runner
image with every dependency baked in. It bind-mounts `src/`, `scripts/` and `tests/`, so
edits on the host take effect immediately.

```bash
docker compose run --rm app python scripts/init_databases.py && docker compose run --rm app python scripts/seed_all.py
```

```bash
docker compose run --rm app python scripts/validate.py
```

Swap in `python -m pytest -q` or `python scripts/ask.py "<question>"` for any other task
in the table below.

## Ask it something

```bash
python scripts/ask.py "Which BFP ran hotter over the last 7 days?"
```

Add `--trace` to print every delegation, tool call and generated SQL/Cypher/Python
alongside the answer.

Or step through every agent, tool call and generated query in LangGraph Studio:

```bash
langgraph dev --port 2025
```

That exposes four assistants — the full `orchestrator` plus each specialist on its own,
so you can drive one agent in isolation and watch its tool loop.

There is also a walkthrough notebook, [`notebooks/demonstration.ipynb`](notebooks/demonstration.ipynb),
with a cell where you type a question and see every intermediate step.

## How the team is put together

```
                    ┌─────────────────┐
   user question →  │  orchestrator   │  owns the plan · writes todos · never writes SQL
                    └────────┬────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐       ┌────────────┐
   │graph_agent│      │ sql_agent │       │coder_agent │
   │  Neo4j    │      │ Postgres  │       │  Python    │
   └───────────┘      └───────────┘       └────────────┘
    the index          the values          the analysis
```

Each specialist is a full agent with its **own message history**. The orchestrator
delegates a task in plain English and gets back only a short report, so a specialist's
internal tool chatter never enters the supervisor's context — that isolation is the point
of the split.

| Agent | Tools | Role |
|---|---|---|
| `graph_agent` | `candidate_tags`, `graph_query`, `resolve_window` | **Narrows.** Turns "vibration on the turbine" into a named tag list, plus alerts, thresholds and maintenance history. Holds no sensor values. |
| `sql_agent` | `explore_schema`, `tag_stats`, `sql_query`, `resolve_window` | **Measures.** The only source of telemetry values. `tag_stats` aggregates many tags across tables in one generated query. |
| `coder_agent` | `python_analysis`, `sql_query` | **Analyses.** pandas/numpy/scipy/sklearn statistics and matplotlib figures over data already fetched. |

Data never travels through a prompt: payloads live in an out-of-band store and agents pass
each other **artifact ids**. Graph state carries only bounded digests plus a `tool_events`
trail recording every SQL/Cypher/Python call with timing and row counts — full
observability at zero context cost.

**Safety.** Generated SQL goes through `sqlglot` validation against a read-only role
(SELECT-only, 15s statement timeout); Cypher runs in a READ session behind a clause
denylist; Python runs behind an AST allowlist with no filesystem, network or `os`/`sys`.

**Budgets.** LangGraph counts every middleware hook as a super-step, so limits are
*derived* rather than guessed (`specialists.py`, `orchestrator/agent.py`) and the graceful
tool limiter always binds before the hard recursion ceiling. `tests/test_agent_budgets.py`
asserts this — it is the kind of failure that is silent and expensive when it regresses.

## What gets built

- **PostgreSQL** — 5 wide telemetry tables (`bfpa`, `bfpb`, `cepa`, `cepb`, `turbine`):
  one `ts` plus 108–160 `DOUBLE PRECISION` sensor columns each. **636 tags ×
  43,200 rows = ~27.5M values**, 30 days at 60s. Plus `sensor_catalog`, `run_metadata`,
  and a `*_long` view per table.
- **Neo4j** — exactly 5 labels (`System`, `Tag`, `MaintenanceLog`, `Item`, `Alert`) and
  4 relationships (`GENERATED_ON`, `PERFORMED_ON`, `MEASURED_AT`, `CONSUMED`). Metadata
  only — **no telemetry values**, enforced by gate G-07.

The `(system, tag_name)` ↔ `(table, column)` bridge is carried as node properties, so a
graph answer resolves to a Postgres target with no hardcoded map.

Both databases are projected from one in-code catalog (`src/mas/catalog/`), so they cannot
disagree. One event timeline drives telemetry, alerts *and* maintenance together: every
alert is plottable and every repair is visible in the data.

## Reproducibility

Every RNG derives from `MASTER_SEED` via `SeedSequence` keyed by `(system, tag_name, …)`,
so adding a tag never perturbs an existing one. `NOW_ANCHOR` is **pinned by default**, so
"yesterday" resolves against a frozen clock and seeding is byte-identical; set
`NOW_ANCHOR=live` for a fresh wall-clock window. The resolved anchor and seed are
persisted to `run_metadata`, and gate **G-22** proves two seeds produce identical content
hashes.

## Layout

```
scripts/          init_databases · seed_all · validate · gen_data_dictionary
                  build_golden · run_eval · build_notebook
src/mas/
  config.py       seed / anchor / window + RNG discipline
  catalog/        in-code source of truth: families, systems, items, api
  db/             DDL generation, Neo4j constraints, connection helpers
  datagen/        modes · physics · events · instrument · build_telemetry
                  alerts · maintenance · graph_seed
  harness/        deterministic non-LLM runtime: clock, digests
  tools/          safety validators + executors (sql/cypher/python) + timewin
  memory/         artifact types + out-of-band payload store
  agents/         the three specialists, their tools and their prompts
  orchestrator/   the supervisor agent + trace formatting
  eval/           consistency gates (G-01..G-22) + golden-dataset scoring
  studio.py       graph entrypoints for `langgraph dev`
tests/            catalog + generation (no DB), full-gate suite (needs DBs),
                  agent budget invariants
notebooks/        demonstration.ipynb — stage-by-stage walkthrough
eval/             golden_dataset.json + generated report
```

## Commands

| Task | Command |
|---|---|
| **Set up everything** | **`python scripts/setup.py`** |
| Start databases | `docker compose up -d postgres neo4j` |
| Initialise schemas | `python scripts/init_databases.py` |
| Seed both databases | `python scripts/seed_all.py` |
| Run the 22 quality gates | `python scripts/validate.py` |
| Ask the agent team | `python scripts/ask.py "<question>"` |
| Run the test suite | `python -m pytest -q` |
| Score the golden dataset | `python scripts/run_eval.py` |
| Regenerate the data dictionary | `python scripts/gen_data_dictionary.py` |
| Regenerate the notebook | `python scripts/build_notebook.py` |
| LangGraph Studio | `langgraph dev --port 2025` |
| Run any task in Docker | `docker compose run --rm app <command>` |
| Stop databases | `docker compose down` (add `-v` to destroy seeded data) |

## Documentation

| Doc | Covers |
|---|---|
| [01-problem-analysis](docs/01-problem-analysis.md) | Problem framing and constraints |
| [02-data-design](docs/Data_design/02-data-design.md) | Schema and generation design |
| [03-data-dictionary](docs/Data_design/03-data-dictionary.md) | Generated tag reference |
| [04-data-story](docs/Data_design/04-data-story.md) | The injected event timeline |
| [05-metadata-tables](docs/Data_design/05-metadata-tables.md) | `sensor_catalog` and `run_metadata` |
| [06-agentic-architecture](docs/agentic_design/06-agentic-architecture.md) | Agent roles and routing |
| [07-memory-and-harness](docs/agentic_design/07-memory-and-harness.md) | Artifacts, digests, data separation |
| [08-langgraph-implementation](docs/agentic_design/08-langgraph-implementation.md) | LangGraph and Gemini specifics |
| [09-implementation-steps](docs/agentic_design/09-implementation-steps.md) | Build order and acceptance criteria |

## Requirements

Python 3.11+ and Docker. Gemini API key in `.env` (see `.env.example`).
