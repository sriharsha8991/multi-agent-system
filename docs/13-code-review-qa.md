# 13 — Code review preparation: 30 questions and how to answer them

> Every answer is pinned to code. Cite the file and line in the room; the reviewer can open it.
> Where the honest answer is "not measured" or "known weakness", say so — §E exists for that.

---

## A. Architecture and framework choices (Q1–Q7)

### Q1. Why `create_agent` instead of hand-building a `StateGraph`?

`create_agent` **is** the LangGraph structure — it compiles to a `StateGraph` with a
`model ⇄ tools` loop. Hand-wiring `add_node`/`add_edge` buys no different runtime, only more
code to own. Three concrete reasons:

1. **The topology you'd hand-write is the prebuilt one.** Orchestrator
   (`orchestrator/agent.py:265`) and all three specialists
   (`agents/specialists.py:122,136,150`) are a single agentic loop. There is no bespoke DAG to
   express, deliberately: doc 10's design is "dynamic plan, deterministic execution", so
   sequencing lives in the ledger, not in edges.
2. **Delegation is tool-shaped, not edge-shaped.** Specialists are exposed as tools
   (`orchestrator/agent.py:181-199`); each runs its own compiled agent in its own message
   history and only the typed report crosses back. A hand-built supervisor graph with handoff
   `Command`s would share `messages` by default — precisely what we avoid.
3. **Everything code-owned attaches as middleware**, which is the supported extension point:
   `OrchestratorGuard`, `_ledger_view`, `_fresh_plan` (`orchestrator/agent.py:271-275`), plus
   context editing and tool budgets on specialists (`agents/specialists.py:127`).

We still use every LangGraph escape hatch: `state_schema`, `checkpointer`, `recursion_limit`,
`Command` returns, `.stream()` (`orchestrator/agent.py:269-270,283,289`).

**The cost we paid** (say this before the reviewer finds it): every middleware *hook* is its
own super-step, so `recursion_limit` no longer maps to "number of tool calls". Both files
carry the arithmetic and the incident that forced it (`agents/specialists.py:45-86`,
`orchestrator/agent.py:46-59`). See Q24.

### Q2. Why multi-agent at all? A single agent with four tools is simpler.

Context isolation is the whole point (`agents/specialists.py:3-6`). A specialist's tool
chatter — schema dumps, failed queries, 200k-row profiles — never enters the orchestrator's
history. Only `SpecialistReport` does (`llm/schemas.py:280-293`), rendered to a bounded string
(`ledger.render_report`, `orchestrator/ledger.py:443-460`).

The measurable argument: each LLM call re-sends accumulated history, so an agent making N tool
calls costs ~N²/2. A single agent making all 34 tool calls pays that on one history; three
specialists pay it on three short ones, and the orchestrator pays it on reports only.

### Q3. Why exactly three specialists, split this way?

The split is by **data boundary**, not by task, and it is declared once in a registry
(`agents/capabilities.py:24-59`) rather than repeated in prompts:

| Slot kind | Agent | Store |
|---|---|---|
| `lookup` | `graph_agent` | Neo4j — metadata, alerts, work orders, parts |
| `measure` | `sql_agent` | PostgreSQL — sensor time series |
| `derive` | `coder_agent` | Python sandbox — artifacts already fetched |

The mapping is strict 1-to-1 (`agents/capabilities.py:62`) and enforced in code at plan time,
not suggested in prose (`can_fill`, `agents/capabilities.py:76-88`; called from
`orchestrator/ledger.py:126`). The prompt's team description is *generated from the same
registry* (`render_team`, `agents/capabilities.py:91-119`), so the prompt cannot drift from
the enforcement.

### Q4. Why does the coder have no database tool?

So it cannot re-fetch data with guessed column names — a real failure mode from live runs
(`agents/specialists.py:13-16`). It is bound only to `python_analysis`
(`agents/specialists.py:91,155`) and its capability declares `needs_inputs=True`
(`agents/capabilities.py:57`), which means a coder step *must* depend on a fetching step —
refused at plan time (`orchestrator/ledger.py:132-134`) and again at delegation time
(`orchestrator/briefs.py:59-61`). There is a test: `tests/test_agent_budgets.py:116`.

### Q5. Why are artifacts kept out of graph state?

Graph state is checkpointed and serialized over HTTP by the dev server / Studio; a DataFrame
does not survive that round trip — it returns as `None` (`memory/store.py:1-14`). So payloads
live in a process-local store and only the **digest** enters state (`agents/base.py:65-67`).
Tools hand ids to each other (`agents/tools.py:144-156`); the payload never reaches a prompt, a
checkpoint, or the wire. This is the strongest form of the data-separation rule.

### Q6. Why custom state reducers instead of the default?

Parallel delegations in one turn must not clobber each other. `merge_keyed`
(`agents/base.py:31-42`) merges **per record**, so two specialists updating different slots in
the same super-step both land. The same function handles the per-question reset via a sentinel
(`PLAN_RESET`, `agents/base.py:28`, applied at `orchestrator/agent.py:244-248`) — a thread's
next question does not inherit the last one's ledger, while `blackboard` (artifacts)
deliberately persists (`agents/base.py:17-23`).

### Q7. Why `wrap_model_call` for the guard rather than `before_model`/`after_model`?

`wrap_model_call` adds **no graph node** (`orchestrator/guard.py:1-6`). It replaced
`ModelCallLimitMiddleware`, which cost two super-steps per turn *and* ended runs with the
literal string "Model call limits exceeded" instead of an answer. Under the wrap, one
orchestrator turn is two super-steps (`orchestrator/agent.py:47-53`), and a spent budget
produces a code-composed answer from accepted facts (`budget_answer`,
`orchestrator/ledger.py:638-643`).

---

## B. Determinism, the ledger, and the code/model boundary (Q8–Q16)

### Q8. What is the actual determinism claim?

Not token-level — we say so explicitly, with reasons (batch-variant kernels; Gemini's `seed`
is best-effort; Google advises against low temperature on Gemini 3). The claim is
**information determinism**: for a pinned data snapshot and a fixed question, the *fact set* —
`(entity, attribute, value, unit, time_scope)` — is identical across runs. Wording and
execution path may differ. Facts are normalised to sensor precision and times to the minute.
See doc 10 §0–§1 and the metric implementation (`eval/golden.py:1-17`).

### Q9. What exactly does code decide, and what does the model decide?

The model decides **what information the answer needs and who fills it**. Code decides
everything decidable exactly:

| Decision | Owner | Where |
|---|---|---|
| Which slots the answer needs, which agent, in what order | model | `set_plan` (`orchestrator/agent.py:202`) |
| Concept → catalog tags | code | `catalog/glossary.py`; `linked_tags`, `orchestrator/ledger.py:170-202` |
| Phrase → `[start, end)` window | code | `resolve_timespec`, `execution/timewin.py:68-100` |
| Identifiers between steps | code | `resolve_ref`, `orchestrator/ledger.py:151-167` |
| Whether a delegation may run | code | `pre_run_problems`, `orchestrator/ledger.py:242-285` |
| Whether a report fills a slot | code | `apply_report`, `orchestrator/ledger.py:312-422` |
| Whether the answer is supported | code | `answer_problems`, `orchestrator/ledger.py:579-610` |
| The SQL / Cypher / Python itself | model | validated at `execution/sql_guard.py`, `cypher_guard.py`, `py_guard.py` |

The last row is the deliberate line: this case study evaluates whether specialists can *write*
correct queries, so we do not pre-write them (see Q29's recipe-reversal row).

### Q10. Why not use an LLM to judge progress (a Magentic-One-style progress ledger)?

We ran the experiment (`experiments/progress_ledger`) and the decision is recorded as **code
only and strict** (doc 10, "Implementation status"). Every LLM arm shared the same misses: it
believed confident prose over missing artifacts, and missed reworded repeats, scope changes and
contradictions (`orchestrator/ledger.py:22-24`). Those are exactly the cases code decides
exactly — so they became typed checks, at zero token cost and zero added graph nodes.

### Q11. How do you stop the agent doing the same work twice?

A **fingerprint** of the data request: agent + slot signatures (kind, aggregation, systems,
resolved tags, resolved window key, threshold) + inputs + note (`slot_signature`/`fingerprint`,
`orchestrator/ledger.py:205-219`). The *wording* of the ask is deliberately excluded, so a
reworded repeat hashes identically; the note is included, so a corrective retry ("include the
time of the max") is a different task but a blind identical retry is not
(`orchestrator/ledger.py:213-216`). Enforcement: a fingerprint that already produced facts is
refused, and two identical failures are refused (`orchestrator/ledger.py:276-284`). Tests:
`tests/test_ledger.py:80,96`.

There is a second, inner guard at tool level: identical `sql_query`/`graph_query`/
`python_analysis` calls, and three consecutive failures, are refused inside the specialist
(`loop_guard`, `agents/tools.py:107-126`; test `tests/test_execution.py:239`).

### Q12. How do you stop an infinite replan loop?

Three independent stops:
- **Stall**: two consecutive delegations that fill no slot block further delegation until a
  replan (`STALL_LIMIT`, `orchestrator/ledger.py:44`; `stall_count`,
  `orchestrator/ledger.py:226-234`; enforced `orchestrator/ledger.py:271-275`). A replan resets
  the counter, by design — that's the escape hatch.
- **Slot blocking**: a slot unfilled after two attempts becomes `blocked`
  (`orchestrator/ledger.py:384-386`) and further delegation to it is refused
  (`orchestrator/ledger.py:268-270`).
- **Model-call budget**: 20 calls, then code writes the answer (`orchestrator/agent.py:52`,
  `orchestrator/guard.py:64-72`).

### Q13. How do you catch a hallucinated number in the final answer?

`answer_problems` (`orchestrator/ledger.py:579-610`) extracts every number-with-unit and every
currency amount, then requires it to be an accepted fact, a catalog setpoint of a tag in play, a
number from the question, or one- or two-term arithmetic on those (`_evidence`,
`orchestrator/ledger.py:525-552`; `_derivable`, `orchestrator/ledger.py:564-576`).

The matching rule matters: **equality at the precision the number was written with**, with no
relative slack (`_close`, `orchestrator/ledger.py:555-561`). The comment records why — with
relative slack, a wrong "60.86%" passed as arithmetic landing on 60.79. Violations get one
repair turn (`orchestrator/guard.py:84-89,114-126`); anything still unsupported is printed under
"Unverified by code" (`footers`, `orchestrator/ledger.py:613-635`). Tests:
`tests/test_ledger.py:234,240`, `tests/test_guard.py:62`.

### Q14. How do you catch two specialists disagreeing?

Pairwise contradiction detection on accepted facts: same normalised entity, same normalised
attribute, same window, values differing beyond tolerance → both slots marked `conflict` and a
`CONFLICT:` note enters the report the orchestrator reads
(`orchestrator/ledger.py:350-365`). Tolerance is `max(0.051, 0.5% of magnitude)`
(`orchestrator/ledger.py:300-301`) — 0.051 absorbs one-decimal rounding. Attribute synonyms are
normalised first (`norm_attr`, `orchestrator/ledger.py:289-293`) so `max` and `peak_value`
compare. Test: `tests/test_ledger.py:189`.

### Q15. Why is a `SpecialistReport` typed, and what happens if the model fails the schema?

Typed so `apply_report` can check it: findings must name a slot the task asked for, artifact ids
must exist, units must match the catalog, and each slot's declared `needs` must be present
(`orchestrator/ledger.py:323-348,369-391`). "Confident text with no findings" is explicitly
*not* progress (`tests/test_ledger.py:170`).

It uses the provider's native structured output (`ProviderStrategy`,
`agents/specialists.py:115-116`), which adds **no graph node** — Gemini 3 supports it alongside
tool calls (`agents/specialists.py:8-11`; test `tests/test_agent_budgets.py:108`).

On schema failure we do not lose the run: `StructuredOutputValidationError` carries the message,
which is kept as raw text (`orchestrator/agent.py:83-84,88-90`), wrapped in a synthetic
`partial` report (`orchestrator/agent.py:150-155`) and rendered with an explicit "UNSTRUCTURED
REPORT (not machine-checked)" banner (`orchestrator/ledger.py:458-459`). Degraded, labelled, not
lost.

### Q16. Why does the orchestrator never write SQL, Cypher or Python?

Because it knows the schema worse than the specialist does. It is enforced, not asked: a
`CODE_PATTERN` regex rejects code in the slot `ask` and the task `note` as a cheap Pydantic
validation error (`llm/schemas.py:57-58,65-69`, applied at `llm/schemas.py:193-196,248-251`).
The reverse direction is measured too: `report_has_code` is recorded per delegation
(`orchestrator/agent.py:95,108`).

---

## C. Safety, execution boundaries, and data access (Q17–Q23)

### Q17. Walk me through the SQL safety boundary.

Four layers, in order:
1. **Parse with a real grammar**, not regex — `sqlglot` (`execution/sql_guard.py:50-56`).
   Exactly one statement, and it must be a SELECT/UNION/Subquery
   (`execution/sql_guard.py:54-59`).
2. **AST denylist** for write nodes and dangerous functions (`pg_read_file`, `lo_import`,
   `dblink`, `pg_sleep`, …) (`execution/sql_guard.py:20-27,61-68`).
3. **Table allowlist derived from the catalog**, not hardcoded (`default_allowed_tables`,
   `execution/sql_guard.py:34-37`), with CTE aliases exempted — and the comment explains why
   that opens nothing: the CTE body's own tables are still checked
   (`execution/sql_guard.py:70-78`).
4. **LIMIT injection** on a bare SELECT (`execution/sql_guard.py:82-84`).

Behind all of that is the driver-level gate: a `mas_reader` role with SELECT-only,
`default_transaction_read_only = on` and a 15 s `statement_timeout` (`db/postgres.py:62-91`).
The validator is defence in depth; the role is the hard boundary.

### Q18. You validate column names too — doesn't that block valid SQL?

Deliberately not. `_check_columns` uses sqlglot's scope-aware `qualify` against a schema built
from the catalog with no DB round trip (`catalog_schema`, `execution/sql_guard.py:89-100`). It
rejects **only** a name that exists in no reachable relation and that the query never aliases
(`execution/sql_guard.py:123-129`); anything the optimizer merely cannot follow returns silently
(`execution/sql_guard.py:117-121`). This catches a hallucinated `bearing_temp_9` and suggests
near matches (`execution/sql_guard.py:130-134`). Both directions are tested:
`tests/test_execution.py:144` (valid SQL never blocked) and `:153` (hallucinations rejected with
hints).

### Q19. Cypher has no AST parser — how is that safe?

Acknowledged in the module docstring (`execution/cypher_guard.py:1-6`): there is no mature
Python Cypher AST, so we use the community pattern — a clause/procedure denylist
(`execution/cypher_guard.py:20-26,67-70`) **plus** a driver-level READ session as the hard gate.
Belt and braces; the denylist alone is not the claim.

Two semantic checks sit beside it, and they are the interesting part:
- **The datetime trap**: comparing a zoned datetime property to a string literal is not an error
  in Neo4j — it evaluates to null and silently matches nothing, and `EXPLAIN` does not warn (we
  verified). Caught here (`check_datetime_compare`, `execution/cypher_guard.py:75-81`).
- **`EXPLAIN` notifications** for unknown labels/properties/relationships are turned into
  validation errors with "did you mean" suggestions from the graph vocabulary (`unknown_names`,
  `execution/cypher_guard.py:84-97`).

### Q20. Is the Python AST validator a security boundary?

No, and the docstring says so first: CPython is not a sandbox (PEP 551)
(`execution/py_guard.py:1-6`). It is a *correctness and accident* guard — import allowlist,
banned builtins, no dunder access, no system modules (`execution/py_guard.py:15-20,44-68`).

The isolation boundary is the out-of-process executor (`execution/py_sandbox.py:1-17`): a
separate interpreter per delegation with `PYTHONHASHSEED=0` and a hard timeout that kills the
process and resets the session (`execution/py_sandbox.py:57,108-112`), or the docker backend
with `--network none --read-only`, memory/CPU/PID limits and read-only source mount
(`execution/py_sandbox.py:59-66`).

One thing the guard enforces that is *not* about safety at all: randomised sklearn estimators
must pass `random_state` (`execution/py_guard.py:22-30,59-63`) — because a clustering run that
picks different centroids reports different information. That is determinism enforced by an AST
walk. Test: `tests/test_execution.py:175`.

### Q21. Why is the sandbox session scoped to a delegation?

Variables and imports persist across calls within one step, so the coder can look at the data
once and build on it (`agents/tools.py:492-493`) — without that, every call started from a fresh
namespace. The session is keyed by the delegation id the orchestrator puts in the specialist's
run config (`orchestrator/agent.py:77` → `agents/tools.py:536`) and is closed in a `finally`
when the delegation ends (`orchestrator/agent.py:145-146`), with an `atexit` sweep
(`execution/py_sandbox.py:169-172`).

### Q22. How does time resolution avoid drift?

Three rules:
- The model **names** time (`phrase` / `start+end` / `around_alert`, exactly one, validated)
  (`TimeSpec`, `llm/schemas.py:101-133`); code produces the window, and `TimeWindow` says so in
  its docstring (`llm/schemas.py:136-137`).
- **Alert padding is one fixed constant**, not a model choice (`EVENT_PAD_HOURS = 2.0`,
  `execution/timewin.py:49-52`) — the comment records the trace where the model chose
  04:00–11:00 on one run and 00:00–15:00 on the next for the same alert.
- **Windows are clamped to real telemetry coverage** read from `run_metadata` (`data_bounds`,
  `execution/timewin.py:19-40`; `execution/timewin.py:90-99`) and the brief says so verbatim
  (`orchestrator/briefs.py:147`), so "last 60 days" does not burn budget on empty results.

### Q23. What stops the orchestrator inventing a time scope the user never asked for?

A word-list check at plan validation: a slot may not carry a `time` unless the question contains
a time word (`TIME_WORDS`, `llm/schemas.py:300-305`; enforced `llm/schemas.py:330-332`). The
comment cites the trace that motivated it — an orchestrator added "last 24 months" to "how many
turbine work orders" and silently dropped a record.

---

## D. Cost, budgets, and observability (Q24–Q28)

### Q24. Explain the recursion-limit arithmetic. This looks like magic numbers.

It is derived, not guessed, and the derivation is in the code (`_steps_for`,
`agents/specialists.py:69-80`): `3·tool_calls` (model → after_model → tools per iteration)
`+ 2·2` (two refused over-budget attempts, 2 steps each) `+ 2` (final model + after_model that
writes the report) `+ 2` margin.

The comment records the incident: `3n + 4` looked sufficient but ignored the refused call — a
traced `sql_agent` spent its 12 calls, tried a 13th, wrote a complete report, and landed exactly
on 40, so the recursion limit fired *after* the report was written and the orchestrator received
a finished answer stamped INCOMPLETE (`agents/specialists.py:71-75`). An earlier trace with
`recursion_limit=20` bought 6 iterations, not 10, and killed 5 of 10 delegations
(`agents/specialists.py:51-55`).

**The invariant**: the *tool* budget must bind before the recursion limit, because the tool
limiter returns "you are out of budget" into the conversation and lets the model write its
report, whereas the recursion limit raises and loses the run (`agents/specialists.py:83-86`). It
is unit-tested for every specialist (`tests/test_agent_budgets.py:34`) and for the orchestrator
(`:79`).

### Q25. Why one global tool limiter rather than one per tool?

Each limiter is a separate `after_model` node, so a per-tool split costs one super-step per
iteration per extra tool name (`agents/specialists.py:106-112`). Asserted by test:
`tests/test_agent_budgets.py:60`.

### Q26. The context-editing trigger is 12,000 tokens. Why that number?

Because 20,000 was dead configuration: the largest context in a real run was 18,396, so it never
fired (`agents/specialists.py:94-100`). 12,000 sits below the window a specialist reaches
partway through its budget. There is a test that the trigger is actually reachable
(`tests/test_agent_budgets.py:69`) — that test exists specifically so this cannot silently
become dead config again.

### Q27. How would you debug a bad run in production?

`tool_events` is an append-only trail in state (`agents/base.py:68`) that never enters a prompt.
Per delegation we record the brief, status, fingerprint, resolved windows, artifacts created,
code-check notes, inner call count, and measured cost — input/output tokens, model calls, report
length, whether the report leaked code, and the distinct ISO timestamps that appeared in the
specialist's queries (`_delegation_metrics`, `orchestrator/agent.py:99-110`; assembled at
`orchestrator/agent.py:165-171`). Sub-events from the specialist are re-tagged with the agent
name and folded in (`orchestrator/agent.py:165`). Refusals and failures are events too, with the
reason (`agents/tools.py:129-141`).

The window list is the one to point at: it lets you diff *which time ranges two runs actually
queried*, which is the window-determinism metric (`eval/golden.py:13`).

### Q28. How is this evaluated?

A golden set of 20 cases built from the databases (`scripts/build_golden.py`), scored per case
over k runs on pinned data (`eval/golden.py:1-17`): routing, value, **pass^k** (τ-bench
reliability: all k runs pass), fact determinism, answer-number determinism, window determinism.
The scorers are pure functions over final states, so they unit-test without live model calls
(`eval/golden.py:15-16`).

Two details worth volunteering:
- **The old determinism metric was removed, not patched.** It compared every number in two prose
  answers, so it read 0% even when the facts matched (`eval/golden.py:14-16`, doc 10 §0).
- **The number-matching tolerance was tightened** because 1% relative let 66.1 pass for 65.8
  (`_num_in_text`, `eval/golden.py:82-103`).

Underneath, 22 cross-database consistency gates run as a build-failing suite
(`eval/consistency.py:1-6`).

---

## E. Weaknesses — name these before the reviewer does (Q29–Q30)

### Q29. What's not done, not measured, or known-broken?

Lead with this list; it buys credibility for everything else.

| Gap | Where / evidence |
|---|---|
| **No live agent run or golden eval after the doc-10 changes** (Gemini budget). Behaviour with the live model is unmeasured. | doc 10, "Not verified" |
| **Docker backend was dead until 2026-09-16.** Building the image revealed every container died with `ModuleNotFoundError: pydantic_settings` — `-m mas.execution.py_worker` ran the package `__init__`, which imports config. Fixed (invoke by path); 12/12 isolation checks now pass. The image is still not built by CI or `setup.py`, so `PY_SANDBOX_BACKEND=docker` on a fresh checkout silently gets nothing. | `execution/py_sandbox.py:59-72`; `tests/test_execution.py::test_docker_backend_starts_and_isolates`; doc 10 |
| **On Windows the subprocess backend has no memory/CPU limit** — `_posix_limits` is POSIX-only, so only the timeout applies. The dev machine is win32. | `execution/py_sandbox.py:70,140-144` |
| **Data defect**: the catalog's normal range for `pump_head` (0–100) contradicts its physics (~2,240 m). Needs a catalog fix and reseed. | doc 10, "Data defect found" |
| **The artifact store is process-local** — a distributed deployment needs Redis/disk behind the same `put`/`get`. | `memory/store.py:12-13` |
| **Specialist agents are `lru_cache`d singletons**, so model config is frozen at first construction. | `agents/specialists.py:119,133,147` |
| **Default credentials in settings** — fine for a seeded local stack, not for anything shared. | `config.py:56-63` |
| **The answer check's arithmetic is only 1–2 terms** (`a`, `a±b`, `a/b·100`), and it is O(n²) over the evidence set. A three-step derivation is flagged as unverified; a coincidental match passes. | `_derivable`, `orchestrator/ledger.py:564-576` |
| **Recipe layer (S1) was built and reversed.** Recipes made the team faster but its output narrower — every answer took the recipe's shape — and bypassed the capability under evaluation. Replaced by craft in tool descriptions; determinism now rests on conventions and checks, not on generated queries. Trade-off accepted, to be measured with `run_eval.py --k 3`. | doc 10, "Why the recipe layer (S1) was reversed" |

### Q30. What would you do next, and where does this design stop scaling?

**Next, in order** (doc 10 priority list):
1. Run the live eval — every claim about behaviour is currently unmeasured.
2. Fix the `pump_head` catalog defect and reseed.
3. ~~Build the docker image~~ — done 2026-09-16; it exposed a fatal invocation bug (Q29).
   What remains: build the image in CI, and add the `stderr` capture that would have made
   the failure visible in one run instead of needing a manual repro (`py_sandbox.py:75`
   sends container stderr to `DEVNULL`).
4. Then, and only from data, decide whether to move the control loop itself into code — the
   explicitly deferred decision (doc 10, priority 4), and the one place where hand-rolling a
   `StateGraph` would actually win over `create_agent` (see Q1).

**Where it stops scaling:**
- **The registry is hand-written.** Three agents is fine; thirty would need generated capability
  cards or retrieval over them, because `render_team` (`agents/capabilities.py:91-119`) puts
  every capability in every orchestrator prompt.
- **Contradiction detection is pairwise over all facts** (`orchestrator/ledger.py:354`) — fine
  at tens of facts, quadratic at thousands.
- **The unit regex is a fixed alphabet** (`_UNIT_RE`, `orchestrator/ledger.py:518-519`). A new
  domain means editing it; a number with an unlisted unit is silently not checked. That is a
  fail-open in the answer guard and the thing I would harden first if this went beyond this
  plant.
- **Single process, single tenant.** The store, the sandbox session table
  (`execution/py_sandbox.py:147-148`) and the agent singletons all assume it.
