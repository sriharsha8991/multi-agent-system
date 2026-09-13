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

## 🚀 Setup Guide for New Users

### Prerequisites
- **Python 3.11+** installed
- **Docker & Docker Compose** installed and running
- **Google Gemini API Key** ([Get a free key from Google AI Studio](https://aistudio.google.com/apikey))

---

### Option A: Automated One-Command Setup (Recommended)

Run the automated setup script which handles environment setup, dependencies, spinning up Docker containers, database initialization, seed data generation, and verification:

``` 
python scripts/setup.py
```

It will prompt for your `GEMINI_API_KEY` (or read it from `.env`). The script is idempotent and can be re-run at any time.

Useful setup flags:
| Flag | Effect |
|---|---|
| `--skip-deps` | Skip `pip install -r requirements.txt` |
| `--skip-seed` | Setup database schemas without data seeding |
| `--force-seed` | Force data regeneration |
| `--reset` | Stop & destroy database volumes and rebuild from scratch |
| `--no-input` | Non-interactive mode (for CI/automated setups) |

---

### Option B: Step-by-Step Manual Setup

If you prefer to configure and seed the system step-by-step:

#### Step 1: Clone Repository & Create Virtual Environment
``` 
git clone <repository-url>
cd multi_agent_system
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

#### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and set your Gemini API key:
``` 
cp .env.example .env
```
Edit `.env` and set `GEMINI_API_KEY=your_actual_api_key_here`.

#### Step 3: Install Python Dependencies
``` 
python -m pip install -r requirements.txt
```

#### Step 4: Spin Up Database Containers (Postgres & Neo4j)
Start the PostgreSQL telemetry store and Neo4j graph database in the background:
``` 
docker compose up -d postgres neo4j
```
Verify containers are running:
``` 
docker compose ps
```

#### Step 5: Initialize Database Schemas & Roles
Create wide telemetry tables, index views, and Neo4j constraints:
``` 
python scripts/init_databases.py
```

#### Step 6: Generate & Seed Data
Generate 30 days of synthetic physics telemetry (Postgres) and asset graph ontology (Neo4j):
``` 
python scripts/seed_all.py
```

#### Step 7: Verify Data Consistency
Run the 22 automated quality validation gates:
``` 
python scripts/validate.py
```
A successful setup will output `22/22 gates green`.

---

## 🧪 Testing & Interacting with the Agent System

### Method 1: Interactive Chat UI with LangGraph Studio (`langgraph dev`)

You can test and inspect the full multi-agent workflow in real-time using LangGraph Studio:

#### 1. Start the LangGraph development server:
``` 
langgraph dev --port 2025
```
*(If `langgraph` command is not found, ensure virtualenv is active or use `npx @langchain/langgraph-cli dev --port 2025`)*

#### 2. Open the Chat Interface:
Open the local URL displayed in your terminal (typically `http://localhost:2025` or the Studio browser link) to access the interactive web interface.

#### 3. Select an Assistant / Agent Graph to Test:
The setup exposes 4 distinct graph targets (configured in `langgraph.json` & `src/mas/studio.py`):
- **`orchestrator`**: The full supervisor team (orchestrator + graph + sql + coder specialists).
- **`sql_agent`**: Specialist for PostgreSQL telemetry queries only.
- **`graph_agent`**: Specialist for Neo4j metadata & work order queries only.
- **`coder_agent`**: Specialist for Python analytics and figure generation.

#### 4. Test with Sample Queries:
Select the `orchestrator` graph, type your question in the chat prompt, and press Send:
- *"Which Boiler Feed Pump ran hotter over the last 7 days?"*
- *"Why did the turbine trip on Aug 28?"*
- *"Show me a temperature vs vibration plot for BFP-A during its alert window."*

**What you will see in the Chat UI:**
- **Live State Graph**: Visual node highlights showing current agent execution flow.
- **Step-by-Step Tool Calls**: Real-time rendering of generated SQL, Cypher, and Python sandbox executions.
- **Artifacts & Ledger**: In-memory artifact IDs and information ledger slot transitions (`pending` → `filled`).

---

### Method 2: Command-Line Interface (`ask.py`)

Run queries directly from the command line:

```
python scripts/ask.py "Which BFP ran hotter over the last 7 days?"
```

Add `--trace` flag to print detailed step-by-step agent delegations, plan steps, and generated queries:
```
python scripts/ask.py "Which BFP ran hotter over the last 7 days?" --trace
```

---

### Method 3: Interactive Jupyter Notebook

Launch the step-by-step walkthrough notebook to inspect intermediate outputs:
``` 
jupyter notebook notebooks/demonstration.ipynb
```

## How the team is put together

```
                    ┌─────────────────┐
   user question →  │  orchestrator   │  states the facts needed · routes · never writes SQL
                    └────────┬────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐       ┌────────────┐
   │graph_agent│      │ sql_agent │       │coder_agent │
   │  Neo4j    │      │ Postgres  │       │  Python    │
   └───────────┘      └───────────┘       └────────────┘
    the index          the values          the analysis
```

Each specialist is a full agent with its **own message history**; only its checked report
crosses back to the orchestrator. The model decides *what* each question needs and *who*
fills it. Code decides everything that can be decided exactly (`docs/agentic_design/10`):

- **Ledger.** `set_plan` records the facts the answer needs (*slots*: kind, aggregation,
  required fields, systems, glossary concepts, time) and the steps that fill them. It is
  validated against the capability registry (`agents/capabilities.py`), the concept
  glossary (`catalog/glossary.py`) and the question's time scope — a window the user did not
  name is rejected.
- **Briefs in code.** A delegation names a step and its slots. `orchestrator/briefs.py`
  resolves references to earlier results (`$s1.alert_id`, `$s1.tags`, `$s1.artifacts`),
  windows against the frozen clock (fixed ±2 h around alerts) and concepts to catalog tags.
  The same plan always yields the same brief.
- **Strict progress rules, code only** (`orchestrator/ledger.py`). An identical task, a
  filled or blocked slot, an unfinished dependency, or any delegation after two that filled
  nothing (STALLED) is refused. Specialist tools refuse identical calls and stop after three
  failures in a row.
- **Typed reports.** Specialists return a `SpecialistReport` whose findings are keyed to
  slots. Code rejects stray slots and fake artifact ids, corrects units to the catalog,
  marks missing required fields and contradictions between reports.
- **Checked answers.** `orchestrator/guard.py` checks every number with a unit in the final
  answer against the accepted facts (one repair, then flagged), and appends Evidence and
  Gaps. It also enforces the model-call budget — answering from the ledger rather than
  stopping with an error.

| Agent | Tools | Role |
|---|---|---|
| `graph_agent` | `graph_query` | Tags and setpoints, alerts, work orders, parts, costs. No sensor values. |
| `sql_agent` | `sql_query`, `explore_schema` | The only source of telemetry values. |
| `coder_agent` | `python_analysis` (sandbox) | Any analysis and as many figures as the question needs, from artifacts it is given. No database access. |

The specialists write their own SQL, Cypher and Python — nothing is pre-written for them.
Each tool's description tells its story: what it is for, when to reach for it, the patterns
that answer this plant's questions well (the time of an extreme, ties, minutes above a limit,
bucketed series, fully ordered results, `random_state=0`), what code checks, and what comes
back. The sandbox keeps every figure the analysis draws, with legible presentation defaults.

Data never travels through a prompt: payloads live in an out-of-band store and agents pass
each other **artifact ids**. Graph state carries only bounded digests plus a `tool_events`
trail recording every SQL/Cypher/Python call with timing and row counts — full
observability at zero context cost.

**Safety.** Generated SQL goes through `sqlglot` validation against a read-only role
(SELECT-only, 15s statement timeout) with column checks against the catalog; Cypher runs in
a READ session behind a clause denylist, an `EXPLAIN` check for unknown labels/properties
and a string-vs-datetime trap check; Python runs out of process (`execution/py_sandbox.py`)
with a hard timeout, fixed seeds and an AST allowlist — set `PY_SANDBOX_BACKEND=docker` and
build `docker/py-sandbox.Dockerfile` for container isolation.

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
  execution/      L3 safety boundary: validators + read-only executors + timewin
  memory/         artifact types + out-of-band payload store
  agents/         specialists, prompts, capabilities, tools.py (L4)
  orchestrator/   supervisor, ledger (strict checks), briefs, guard, trace
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
| Build the golden dataset (DB only) | `python scripts/build_golden.py` |
| Score it: pass^k + determinism (live Gemini) | `python scripts/run_eval.py <label> --k 3` |
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
| [10-orchestration-and-determinism-plan](docs/agentic_design/10-orchestration-and-determinism-plan.md) | Why the ledger and strict rules exist — research, roadmap, and why recipes were removed |
| [11-agents-architecture-explained](docs/agentic_design/11-agents-architecture-explained.md) | **Start here:** every term, tool, rule and limit of the agent team, with diagrams |

## Requirements

Python 3.11+ and Docker. Gemini API key in `.env` (see `.env.example`).
