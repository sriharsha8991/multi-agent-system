# 10 — Orchestrator sequencing and information determinism: where we lag, what the field does, what to build

> **Status:** phases A–C implemented 2026-09-14, **not yet evaluated live** · **Scope:**
> orchestrator planning/routing/sequencing (priority 1), specialist SQL/Cypher/Python
> determinism and accuracy (priority 2). Every proposal below is tagged with *where it lives*
> and *what it costs the main graph*, and every lagging point cites evidence from our own runs.

---

## Implementation status (2026-09-14)

**Decision recorded:** progress judgment is **code only and strict** (owner's decision after
the `experiments/progress_ledger` results). No LLM progress-ledger call was added. The
misses every LLM arm shared are handled by typed-fact checks in code:
- contradictions between reports;
- a time scope the question did not name;
- reworded repeats;
- missing required fields.

| Item | Where | State |
|---|---|---|
| A — fact extraction, pass^k, fact/answer/window determinism | `eval/golden.py`, `scripts/run_eval.py --k` | done; the old numbers-in-text metric was removed |
| A — golden set to 20 (paraphrases, concepts, no-time trap, explicit date, root cause, out of scope) | `scripts/build_golden.py`, `eval/golden_dataset.json` | built from the DBs |
| A — snapshot + model config pinned in reports; sampling knobs | `run_eval.py`, `config.gemini_temperature/seed/specialist_thinking_budget` | done; default stays temperature 0 until the experiment is run |
| A — Python timeout | `execution/py_sandbox.py` | done |
| B/O1 — information ledger, mandatory `set_plan(slots, steps)` (same-turn aware) | `llm/schemas.py`, `orchestrator/ledger.py`, `orchestrator/agent.py` | done |
| B/O2 — concept glossary + derived-tag units | `catalog/glossary.py` | done (derived units are display overrides; the seeded catalog is unchanged) |
| B/O3 — step references `$sN.alert_id / tags / artifacts / work_order_id` | `ledger.resolve_ref`, `briefs.prepare` | done |
| B/O4 — capability registry | `agents/capabilities.py` | done; the prompt's shape table was replaced by generated capability cards |
| B/O5 — strict code progress rules: identical fingerprint, 2 identical failures, slot blocked after 2 attempts, STALLED after 2 non-filling delegations, replan resets | `ledger.pre_run_problems`, `ledger.apply_report` | done (code only) |
| B/O6 — answer check (numbers, units, arithmetic) with one repair + code footers | `orchestrator/guard.py` | done |
| B/O7 — zero-node budget guard, `ModelCallLimitMiddleware` removed | `orchestrator/guard.py` | done (a turn is now 2 super-steps) |
| B/S6 — typed `SpecialistReport` with prose fallback | `agents/specialists.py`, `orchestrator/agent.py` | done |
| C/S1 — recipe tools (SQL, Cypher, analysis) | — | **removed 2026-09-14** after live runs (see below) |
| C/S1′ — capable tools with a full "story" per tool (purpose, when to use, craft patterns, checks, output); richer reports; every figure kept with presentation defaults | `agents/tools.py`, `agents/prompts.py`, `execution/py_worker.py` | done; sandbox figure capture tested |
| C/S2 — sqlglot column validation, Cypher `EXPLAIN` + datetime trap, empty-result hints | `execution/sql_guard.py`, `cypher_guard.py`, `cypher_exec.py`, `agents/tools.py` | done; exercised against the DBs |
| C/S3 — role enforcement: coder has no DB tool; SQL schema discovery refused; identical calls and 3-failure streaks refused | `agents/specialists.py`, `agents/tools.py` | done |
| C/S4 — out-of-process sandbox, persistent session per delegation, fixed seeds, `random_state` lint | `execution/py_sandbox.py`, `py_worker.py`, `py_guard.py` | subprocess backend done and tested; docker backend written, image not built |
| D — verified query repository, code-owned executor, caching | — | not started (by scope) |

**Not verified:**
- No agent run and no golden eval were executed after these changes (Gemini budget).
  Behaviour with the live model is unmeasured.
- The docker sandbox image was not built.

**Data defect found:** the catalog's normal range for `pump_head` (0–100) contradicts its
physics (~2,240 m). It needs a catalog fix and a reseed.

**Why the recipe layer (S1) was reversed (2026-09-14).** Live runs showed the recipes made
the team faster but its output narrower. Every answer took the fixed shape of the recipe
that produced it. The coder's figures came from one plain plotting function instead of plots
designed for the question. The recipes also bypassed the capability the case study
evaluates: specialists writing correct SQL, Cypher and Python. They were hard-coded commands,
which is not this system's design ("four capable tools instead of a registry of narrow
parameterised capabilities", doc 08).

What replaced them:
- **Craft in the tool descriptions.** Each tool's description tells its story, including the
  patterns a recipe used to fix (the time of an extreme, ties, minutes above a limit,
  bucketing, ordering with tie-breakers, `random_state=0`). The model still writes the query.
- **Unchanged checks.** Validators, loop guards, the ledger and the answer check are
  unchanged, so correctness is still verified by code.
- **Trade-off accepted.** Determinism now rests on those conventions and checks, not on
  generated queries, so expect some variation in query shape. Measure fact determinism with
  `run_eval.py --k 3` before deciding whether any narrow case needs more.

---

## 0. Summary

**The target.** Same data + same question → the **same information** every run. Wording and
execution path may differ; the facts (entities, values, units, times) may not.

**Where we stand** (golden eval after doc-09 work, `eval/report-final.md`):
- Routing 100%, value 100% on 8 cases; ~34k input tokens per question.
- Information is **not** deterministic. Clustering A7, run twice on 2026-09-13, returned:
  different feature sets, 33.33% vs 33.37% standby share, "online 66.67%" vs "60.86%" (the
  second is arithmetically inconsistent), and flow in "t/h" vs "m³/h" (the catalog says t/h).
- Our determinism metric is broken: it compares every number in two prose answers, so it
  reads 0% even when the facts match.

**The core diagnosis.** Most variance is not token sampling. It is **decisions left to the
model that code could own**:
- which tags a user concept means ("load"),
- which facts a question needs,
- which analysis method and parameters to use,
- which identifiers to copy between steps,
- whether the final answer matches the evidence.

Token-level determinism isn't available to us anyway:
- Temperature 0 doesn't give identical outputs because of batch-variant kernels.
- Gemini's `seed` is explicitly "best effort".
- Google recommends **against** lowering temperature on Gemini 3, and we set 0.

**The direction.** *Dynamic plan, deterministic execution, code-owned facts.*
- The orchestrator still decides — per question, with no hardcoded pathway — what information
  is needed, which specialists and in what order.
- It records that as a typed **information ledger** (the Magentic-One task-ledger idea).
- Code grounds each ledger item: concepts → tags, time → windows, identifiers → references.
- Specialists fill items through deterministic **recipe tools** first, validated free-form
  queries second.
- Code checks the final answer against the ledger before it leaves.

**Priority order:**
1. Measure information determinism properly.
2. Orchestrator ledger and grounding.
3. Specialist recipes, validation and sandbox.
4. Only then decide, from data, whether to move the control loop itself into code.

---

## 1. Definitions we will hold ourselves to

**Information determinism.** For a pinned data snapshot (`run_metadata`: generator version,
seed, anchor) and a fixed question, the **fact set** of the answer is identical across runs.
A fact is `(entity, attribute, value, unit, time_scope)`, with:
- values normalised to sensor precision (e.g. 0.1 °C),
- times to the minute,
- categorical values exact.

**Reported as pass^k at fact level.** This is τ-bench's reliability metric (all k trials
succeed), applied to "all k runs produce the same fact set and it matches ground truth".
τ-bench shows why pass@1 hides unreliability: a 61% pass@1 agent fell to 25% pass^8.

**Reproducibility (secondary).** Paraphrases of a question ("max bearing temp on BFP-A
yesterday" / "hottest bearing reading on pump A yesterday") produce the same fact set.

**Dynamic sequencing.** No question-type → pipeline mapping in code or prompt. The
orchestrator derives steps from what the question needs and from capabilities agents
declare. Code may *validate and schedule*; it may not *choose the route*.

---

## 2. Current design snapshot

| Layer | Today |
|---|---|
| Orchestrator | `create_agent` tool-calling supervisor (ReAct loop). Tools: `graph_agent`, `sql_agent`, `coder_agent` (typed `Task`), `set_plan`. |
| Plan | Optional `set_plan` (≥2 steps): agent, purpose, depends_on. Status/answer/artifacts kept by code; done steps can't re-run; deps enforced. |
| Grounding in code | Task validation (real tags, no code, ≤4 deliverables); time named by LLM, resolved in code (incl. `around_alert` ±2 h); measurement → catalog tag linking (sql_agent only). |
| Graph hooks | `_fresh_plan.before_agent` (1 node/question); `ModelCallLimitMiddleware` before/after (2 nodes/turn); `_artifact_ledger` via `wrap_model_call` (0 nodes). |
| Specialists | Free-form SQL/Cypher/Python + `tag_stats`, `candidate_tags`, `explore_schema`. Prose reports. |
| Validation | SQL: sqlglot parse, SELECT-only, **table** allowlist. Cypher: **regex** write-denylist. Python: AST import allowlist, in-process `exec`, no timeout. |
| Model | `gemini-3.7-flash`, `temperature=0`, no seed, default thinking. |
| Eval | 8 golden cases × 2 runs; value, routing, "determinism" = numbers-in-text equality (broken), window equality. |

---

## 3. What the field does

### 3.1 Orchestration and sequencing

| Source | What they do | What it means for us |
|---|---|---|
| **Anthropic, multi-agent research system** | Lead agent plans, delegates with *objective, output format, tool/source guidance, clear boundaries*. Explicit effort-scaling rules. Persists the plan to memory. Admits agents are "non-deterministic between runs, even with identical prompts". Evaluates with a single LLM-judge rubric on ~20 real queries. | Our `Task` already carries objective/boundaries. Missing: a *persisted information plan* the answer is checked against, and a real-usage eval set of ~20. |
| **Magentic-One (Microsoft)** | Outer loop: **Task Ledger** = given facts, facts to look up, facts to derive, educated guesses, plan. Inner loop: **Progress Ledger** (satisfied? looping? progress? next agent? instruction?). Stall counter ≤2 → reflect and replan. Removing the ledgers cost **−31%** on GAIA. | Closest analogue to what we need. Adopt the *task ledger as typed information slots*, and the *progress ledger as an LLM call whose judgments code facts can veto* — tested in O5. |
| **ReWOO / LLMCompiler / Plan-and-Execute** (LangGraph tutorials) | Plan up front with *variable references* between steps (ReWOO); stream a DAG and let a scheduler run ready tasks in parallel (LLMCompiler, ~3.6× speed-up); replan on failure. | Step outputs should be **referenced** (`$s1.alert_id`), not re-typed by the LLM. Parallel scheduling is a latency win, not a determinism win — lower priority. |
| **LangChain multi-agent guide** | Subagents-as-tools recommended for context isolation. "Custom workflow" when mixing deterministic logic with agentic decisions. Subagents cost the most model calls. | Our pattern is the recommended one. The next step is a hybrid: agentic *planning*, deterministic *checking and scheduling*. |
| **12-factor agents (HumanLayer)** | "Tools are structured outputs", "own your control flow", small focused agents (3–20 steps). | Supports moving checks and scheduling into our code, and keeping agents small. |
| **Cognition, "Don't build multi-agents" and its 2026 follow-up** | Share context and decisions; conflicting implicit decisions break results. Multi-agent works when agents contribute intelligence and writes stay single-threaded. | Specialists make implicit decisions — which tags mean "load", which k-means features. Those must be made once, recorded, and passed on, not re-decided per agent. |
| **Agentic Plan Caching (NeurIPS 2025)** | Extract plan templates from finished runs; reuse for similar requests. −50% cost, −27% latency. | Optional later layer. Not a substitute for fixing variance. |

### 3.2 Determinism and accuracy of generated queries and code

| Source | Finding | Implication |
|---|---|---|
| **Thinking Machines, "Defeating Nondeterminism"** | Temp-0 output differs across runs: 80 distinct completions in 1,000 samples, caused by batch-variant kernels. Fixable only server-side, at 25–60% throughput cost. | We can't get bitwise determinism from a hosted API. Determinism must be architectural. |
| **Gemini 3 developer guide** | Keep temperature at the default 1.0; lowering it "may lead to looping or degraded performance". `seed` is best-effort. | We violate this (`temperature=0`). Test default + seed against temp 0 on fact pass^k and decide by data. |
| **dbt Semantic Layer vs text-to-SQL (2026)** | Semantic layer 98–100% vs text-to-SQL 84–90% on covered questions. Deterministic query generation gives identical results across runs; text-to-SQL gives "correct-looking numbers that are subtly different across runs"; out-of-scope questions error rather than lie. Recommends a hybrid. | A **recipe layer** (parameterised metric tools) for frequent intents, with free-form SQL as fallback. |
| **Snowflake Cortex Analyst** | Semantic model with **synonyms, metrics, verified queries**; retrieves verified question→SQL pairs for similar questions. | A **concept glossary** (load → `motor_power`, …) and a **verified query repository** fed by passing eval runs. |
| **Neo4j Text2Cypher guide** | Complexity × frequency matrix: frequent → prewritten parameterised tools. Bake validation and correction into deterministic functions; dynamic few-shot retrieval of question→Cypher pairs. | Parameterised Cypher recipes for alerts, work orders and rollups. Deterministic validation before execution. |
| **CyVer / Neo4j `EXPLAIN`** | Schema-aware Cypher validation. **Verified on our DB:** `EXPLAIN` returns `UnknownPropertyKeyWarning`, `UnknownLabelWarning` and `UnknownRelationshipTypeWarning` with positions, without executing. It does **not** flag `start_ts >= '2026-09-01'` (string vs datetime). | Use `EXPLAIN` notifications (no new dependency). Add our own check for the datetime-string trap. |
| **sqlglot `qualify`** | **Verified on our DB schema:** with a catalog-built schema it rejects `max(bearing_temp_9)` ("could not be resolved", with position), and accepts CTEs, `_long` views and joins. | Column-level validation before execution, in the existing guard. |
| **BIRD SOTA (CHASE-SQL, XiYan, SIRIUS-SQL)** | Multi-candidate generation + execution-guided selection gives the top accuracy. | Too costly as a default at our scale (N× tokens). Use only as a fallback when a recipe doesn't cover the case *and* validation or an empty result signals trouble. |
| **Sandboxes** | `langchain-sandbox` (Pyodide) **archived Jan 2026**. smolagents: `LocalPythonExecutor` "must not be used as a security boundary"; offers Docker/E2B/Modal/WASM. `llm-sandbox` (Docker/Podman/K8s, persistent IPython sessions) active as of Aug 2026. E2B runs in a remote microVM. | Move to a local container (llm-sandbox or our own Docker runner). Plant data shouldn't leave the box, so no E2B by default. |
| **Anthropic, "Writing effective tools for agents"** | Few thoughtful tools for high-impact workflows; consolidate multi-step chains; return meaningful context; iterate from evals. | Recipes should be *consolidated* (alert + setpoints + follow-up WOs in one call), not a zoo of thin wrappers. |

---

## 4. Lagging points — orchestrator (priority 1)

Ranked by impact on information determinism, then accuracy.

### O1. No information-level plan
- **Now:** the plan records *agents and purposes*, not *facts the answer needs*. Each run
  re-decomposes the question, so different runs pull different information.
- **Evidence:**
  - A4: one run split work orders into in-window vs historical, the other didn't.
  - A4: deliverables drifted ("breakdown of work orders" added on some runs).
  - Turbine run: an unasked "overall latest alert" section.
  - A7: 5 vs 4 clustering features.
- **Field practice:** Magentic-One task ledger (−31% without it); Anthropic persists the plan.
- **Proposal:** an **Information Ledger**, written once per question through `set_plan`
  (mandatory, in the same turn as the first delegation, so no extra turn).
  - Typed slots: `slot_id, kind (given|lookup|measure|derive), entity, concept, aggregation,
    time (TimeSpec), depends_on`.
  - Steps must reference the slots they fill. Code rejects a plan leaving a slot unassigned.
  - The final answer must cover every slot.
- **Why slots beat steps for determinism:** extracting "max of bearing temperature on bfpa
  yesterday" as a slot is a constrained extraction. Planning a free-form sequence is open
  generation, so slots vary far less.
- **Graph cost:** 0 nodes (tool + state channel).

### O2. User concepts aren't grounded in code
- **Now:** `link_tags` searches the whole phrase ("load, efficiency, and vibration" → no match).
  "Load" is not a catalog word, so the specialist guesses.
- **Evidence:**
  - A7: run 1 sql_agent ran 8 `sensor_catalog` queries (its prompt forbids this); run 2
    coder_agent queried `information_schema`, hallucinated `tag_type`/`system_id`, and chose
    different features.
  - Derived tags (`pump_efficiency`, `pump_head`) have **empty units** in the catalog; one run
    invented "m³/h" for a t/h tag.
- **Field practice:** Cortex Analyst synonyms and metrics; dbt semantic layer; text-to-SQL
  errors are ~81% semantic, not syntax (Atlan 2026 summary).
- **Proposal:** a code-owned **concept glossary** in `catalog`:
  - Each concept (`load`, `efficiency`, `vibration`, `bearing temperature`, …) maps to tags per
    system class, with a canonical primary tag and optional companions.
  - Slot concepts resolve through it. Unknown concept → the orchestrator gets the candidate
    list and must pick once, recorded in the ledger — never re-picked by a specialist.
  - Fill in units for derived tags.
- **Graph cost:** 0.

### O3. Identifiers are copied between steps by the LLM
- **Now:** the orchestrator retypes tag lists, alert ids and artifact ids from report prose
  into the next Task.
- **Risk:** copy errors, silent omissions (a tag dropped from a 14-tag list), and
  run-to-run differences in what gets carried.
- **Field practice:** ReWOO/LLMCompiler variable references.
- **Proposal:** typed **step outputs** (slot-keyed findings, §5 S6), referenceable in a Task:
  - `around_alert: "$s1.alert_id"`, `tags: "$s1.handoff_tags"`, `inputs: "$s2.artifacts"`.
  - Code resolves references; an unresolvable reference bounces the Task.
- **Graph cost:** 0.

### O4. Routing knowledge lives in if/else on agent names and a prompt table
- **Now:**
  - `briefs.link_tags` only for `sql_agent`.
  - Clamp only when `agent != "graph_agent"`.
  - `check_task` has per-agent rules.
  - The prompt has a question-shape → pipeline table (a soft hardcoded pathway).
- **Proposal:** a declarative **capability registry**, one card per agent:
  - owns (`telemetry.values`, `graph.alerts`, …)
  - accepts (slot kinds)
  - requires (inputs, systems)
  - time policy (clamp or not)
  - grounding (link tags or not)

  `briefs`, validation and the prompt's team section are generated from the cards. Keep
  2–3 worked *reasoning* examples in the prompt; drop the shape table once the eval shows
  no routing regression.
- **Why:** routing becomes "which declared capability fills this slot kind". Adding an
  agent changes a card, not code paths. The route is still chosen dynamically per question.
- **Graph cost:** 0.

### O5. Progress judgment: an LLM progress ledger, with code facts binding
- **Now:** nothing explicit. Loop, stall and "are we done" are left to the orchestrator
  noticing during its normal turn.
- **Revision.** An earlier draft of this doc proposed code-only signals, reasoning that they
  are computable. That was an untested cost argument. The experiment in
  `experiments/progress_ledger/` tested it and it was wrong on accuracy:
  - 22 labelled orchestrator states (real traces plus edge cases favouring each side);
  - Magentic-One's own questions;
  - 3 runs per LLM arm, `gemini-3.7-flash`.

| Approach | Label acc. | Fully right on every run | Same labels on every run | Tokens / call |
|---|---|---|---|---|
| Code signals only (v1) | 0.844 | 13/22 | 22/22 | 0 |
| Code, glossary-grounded fingerprints (v2) | 0.812 | 13/22 | 22/22 | 0 |
| LLM ledger, Magentic wording (t=0 / t=1) | 0.828 / 0.833 | 11/22 | 15–16/22 | ~1.4k |
| LLM ledger, questions reworded for our architecture* | 0.917 | 17/22 | 21/22 | ~1.4k |
| **Reworded LLM ledger + code signals + code facts binding*** | **0.927** | **18/22** | 21/22 | ~1.6k |

\* Designed after reading the first run's reasons, so this is a hypothesis check, not an
unbiased comparison. See `results.md` for limitations: author-written labels, 64 labels,
and noise of about ±5 points.

- **What each side gets wrong.**
  - *Code alone* misses meaning:
    - a result about the wrong pump (E2);
    - a report that omits the "when" the user asked for (E4);
    - an empty result that *is* the answer (E3);
    - a complete report stamped INCOMPLETE (R2).
  - *The LLM alone*:
    - reads "is the request satisfied?" as "has the reply been sent";
    - believes "All deliverables delivered successfully" over absent artifacts and a budget
      stop (C6), even when shown the code signal;
    - notices an exact repeat eight turns later but labels it "not a loop" (C1);
    - agrees with itself across runs on only 15–16 of 22 states.
  - *Every LLM arm* misses:
    - a task that narrowed the time scope the question didn't limit (R3);
    - a reworded repeat (E1);
    - two reports contradicting each other on the same peak (E5).

    Its stated reasons restate the reports' own claims without cross-checking. That fits
    Magentic-One's own error analysis (insufficient verification in 18% of failures, even
    with its ledger) and research on models confirming their own outputs.
- **Proposal: combine them, each owning what it's good at.**
  1. **LLM progress ledger** after each delegation round. Use Magentic's five questions, with
     *satisfied* and *loop* reworded as in `run_clarified.py`. Make it a separate call, so the
     transcript is judged as external content. Skip it only before the first delegation.
  2. **Code facts are binding vetoes**, never advisory:
     - loop if an identical task or identical failure repeats;
     - no progress if the last step failed, was rejected, repeated, or produced no artifacts;
     - not satisfied while a plan step is pending or failed, or a requested figure is missing.
  3. **Stall counter in state:** 2 consecutive rounds of loop or no-progress trigger a replan
     instruction (Magentic's threshold), or an answer-with-gaps if replanning already failed.
  4. **Typed-fact checks for the misses every LLM arm shares**, once slot-keyed findings
     exist (S6, O1). *Hypothesis — verify on the scenario set before adopting:*
     - *contradiction:* same entity, attribute and window, different values;
     - *scope:* task time narrower than the question's slots;
     - *reworded repeat:* same slot signature (linked tags + aggregation + window), which
       avoids v2's false loops on "stats vs series" and "max vs minutes-above";
     - *missing field:* a deliverable with no finding.
- **Cost.** Measured ~1.4–1.6k tokens and ~2.7–3.1 s per ledger call on scenario-sized
  transcripts. Production transcripts are larger, so estimate 2–4k tokens: about +5–10k
  tokens (+15–30%) and ~+7 s on a typical multi-step question. Accepted, because accuracy
  and consistency are the priority.
- **Graph cost:** one `before_model` node per orchestrator turn. It must write the ledger and
  stall counter to state; a no-op when no delegation returned since the last ledger. Unlike
  `ModelCallLimitMiddleware`'s counters this node does real work, so it earns its place.
  Running it inside `_delegate` instead would add no node, but parallel delegations would
  each judge a stale view.

### O6. The final answer is not checked against evidence
- **Evidence:** A7's inconsistent "60.86% running" and the unit swap reached the user.
- **Proposal:** an **answer check** in code after the orchestrator's final message, bounded to
  one repair turn:
  - every required slot is addressed;
  - every number+unit in the answer matches a ledger fact (within precision) or is marked as
    derived arithmetic whose inputs are facts;
  - units match the catalog.

  Violations go back once as a tool-style message ("slot s2 missing; 60.86% not in evidence"),
  then the answer is released with a gaps note if still failing. The **Evidence** footer is
  generated by code.
- **Graph cost:** `after_model` on the final turn only, or better a `wrap_model_call` that
  inspects a no-tool-call response → 0 extra nodes per turn.

### O7. The budget stop returns a non-answer, and costs 2 nodes per turn
- **Verified:** `ModelCallLimitMiddleware(exit_behavior="end")` ends with the literal text
  "Model call limits exceeded: run limit (20/20)", not an answer. Its before/after hooks make
  a turn 4 super-steps instead of 2.
- **Proposal:** replace with a `wrap_model_call` guard:
  - count this question's model calls from messages since the last human message (no counter
    channel, no node);
  - on the last allowed turn, call the model **without tools** plus a line: "answer now from
    the ledger, list gaps".

  Same safety, a real answer, and per-turn cost drops 4 → 2 super-steps.
- **Worth it?** Yes, but small. No golden case exceeds 4 orchestrator calls; it matters only
  in pathological loops, where today the user gets nothing.

### O8. Sampling configuration contradicts provider guidance
- **Now:** `temperature=0` on Gemini 3.7 Flash; no `seed`; no thinking budget per role.
- **Proposal:** an experiment, not a switch. Run the fact-pass^k eval under:
  1. temp 0,
  2. default temperature + `seed`,
  3. default + seed + lower thinking budget for specialists.

  Keep the config with the best fact pass^k that doesn't regress value accuracy.
- **Graph cost:** 0.

### O9. Sequential dispatch
- **Now:** independent steps run in parallel only if the model emits parallel calls.
- **Proposal:** later. A code scheduler that runs ready steps concurrently (LLMCompiler
  task-fetching unit). Latency only.

### Mechanisms we already have — kept or changed?

| Mechanism | Keep? | Reason |
|---|---|---|
| `_fresh_plan` (before_agent, 1 node per question) | **Keep** | Question-scoped keys would avoid the node but add reducer and key plumbing for a no-LLM step that costs nothing in tokens. |
| `ModelCallLimitMiddleware` | **Replace** (O7) | Non-answer on exit, 2 nodes per turn. |
| `set_plan` optional | **Change** to mandatory information ledger (O1) | Slots are the determinism lever. Same turn as the first delegation, so no added turn. |
| Prompt routing table | **Phase out after eval** (O4) | Soft hardcoding; replace with capability cards plus reasoning examples. |
| Separate intake node with structured output | **Don't add yet** | The ledger via `set_plan` gives the same slots at 0 nodes. Add a node only if slot extraction proves unstable. |
| Code-owned executor (plan-and-execute rewrite) | **Decide in Phase D** | Big change; the current system is at 100% value accuracy. Adopt only if fact pass^k stays below target after phases B–C. |

---

## 5. Lagging points — specialists (priority 2)

### S1. Free-form queries for frequent intents
- **Evidence:** every golden intent is recurring:
  - max/avg over tags in a window,
  - compare two systems,
  - tag counts,
  - maintenance rollups,
  - latest alert with context,
  - correlation,
  - clustering,
  - series around an event.

  Free-form generation re-decides filters, derived-tag handling, bucketing and ties each run.
- **Field practice:** dbt (100% vs 84% on covered questions, identical across runs); Neo4j
  complexity × frequency matrix; Anthropic consolidated tools.
- **Proposal:** a **recipe layer**. Parameterised, code-generated, consolidated tools whose
  outputs are deterministic (ordering, ties, rounding, derived-tag policy fixed in code):
  - *SQL:* `telemetry_stats(tags, window, aggs)` returning `first_ts_at_max` and minutes above
    alarm_hi/hihi; `compare_systems(concept, systems, window, agg)`;
    `series(tags, window, bucket_policy)`.
  - *Cypher:* `alert_context(system, alert_type?, in_window?, latest=True)` (alert + setpoints
    + following work orders); `maintenance_rollup(system, window?)` (always returns in-window
    and historical splits); `parts_consumed(work_order | latest_on_system)`; `tag_inventory(system)`.
  - *Analysis:* `cluster_operating_regions(df, features, k_range=2..6, seed=0)` (k by
    silhouette, standardised, deterministic labels by centroid order); `correlate(a, b, method)`;
    `exceedance_plot(series, thresholds, window)`.
  - Free-form `sql_query`/`graph_query`/`python_analysis` stay as the fallback for uncovered
    questions.
- **Graph cost:** 0 (tools).

### S2. Validation checks too little before execution
- **Now:** SQL guard checks tables but not columns. Cypher is a regex write-denylist.
  Neither checks semantics.
- **Proposal** (both verified on our DBs this session):
  - **SQL:** add `sqlglot.optimizer.qualify(..., schema=<catalog schema>, validate_qualify_columns=True)`
    in `sql_guard`. Unknown column → rejection with position + `difflib` suggestions.
  - **Cypher:** run `EXPLAIN <query>` in the READ session. Promote `UnknownLabelWarning`,
    `UnknownPropertyKeyWarning` and `UnknownRelationshipTypeWarning` to validation errors with
    suggestions.
  - **Datetime trap:** a deterministic check for `start_ts|end_ts|acknowledged_ts <op> '<string>'`.
    Auto-wrap in `datetime()` or reject with the fix; `EXPLAIN` does not catch it.
  - **Empty-result diagnostics:** on 0 rows, the tool reports likely causes — window outside
    coverage, all-null tag, string datetime comparison, over-constrained filter.
- **Graph cost:** 0.

### S3. Agents step outside their roles
- **Evidence:** A7 sql_agent ran 8 `sensor_catalog` discovery queries. A7 coder_agent ran 6
  `sql_query` calls, including `information_schema`, and hallucinated columns.
- **Proposal:** enforce in tools, not prompts:
  - `sql_query` rejects `sensor_catalog`/`information_schema` discovery patterns with "use
    explore_schema" (still allowed in joins for setpoints).
  - Remove `sql_query` from the coder, or allow it only for columns named in the brief.
  - A coder brief whose artifacts lack needed columns returns GAPS; the orchestrator refetches
    via sql_agent.
- **Graph cost:** 0.

### S4. The Python runtime is unsafe and invites nondeterminism
- **Now:**
  - In-process `exec` — not a security boundary.
  - No timeout, so an infinite loop hangs the run.
  - Exception classes missing from builtins.
  - Fresh namespace per call while the model assumes persistence: A7 failed twice with
    `name 'KMeans' is not defined`.
  - Analysis parameters (features, k, scaling) chosen per run.
- **Proposal:**
  - Local container execution (`llm-sandbox` Docker backend, or our own Docker runner per
    doc 08 §8): no network, read-only FS, memory/CPU/time limits.
  - A **persistent session per delegation** (IPython kernel), so multi-call analysis works.
  - A fixed prelude: imports, `np.random.seed(0)`, `random.seed(0)`, `PYTHONHASHSEED=0`.
  - An AST lint that requires `random_state` on sklearn estimators that accept it.
  - Analysis recipes (S1) for the frequent methods.
  - No E2B by default (plant data leaves the machine). No `langchain-sandbox` (archived).
- **Graph cost:** 0 (the tool implementation changes).

### S5. No memory of queries that worked
- **Proposal:** a **verified query repository**: (question, slot signature, SQL/Cypher/code,
  eval-verified result hash), fed by passing eval runs and later by user feedback.
  - Retrieve top-k by slot signature (exact) then by text similarity, as few-shots for the
    free-form fallback.
  - A slot signature with a verified recipe call is replayed with fresh parameters.
- **Graph cost:** 0 (retrieval inside `briefs`).

### S6. Reports are prose, facts are untyped
- **Earlier finding (doc-09 spike):** typed reports were valid 3/3 with Gemini but ~2× larger,
  and code-in-reports was already 0, so they weren't adopted.
- **Why revisit now:** O1, O3 and O6 need **slot-keyed facts** to reference and to check the
  answer against. Size is solved by rendering facts compactly for the orchestrator (one line
  per fact); the JSON stays in state.
- **Proposal:** `ProviderStrategy(SpecialistReport)`:
  - `findings[{slot_id, value, unit, entity, time, artifact_id, statement}]`, `handoff`, `gaps`.
  - Prose fallback on `StructuredOutputValidationError`, which carries the `ai_message`.
- **Graph cost:** 0 (verified 2026-09-13: a graph_agent built with `ProviderStrategy` has the
  same nodes — `model`, `tools`, `ToolCallLimitMiddleware.after_model`).

---

## 6. Measurement first (Phase A)

The current "determinism" number is noise, and 8 cases is too small.

1. **Fact extraction.** Once S6 lands, facts come from the ledger. Until then, a single
   LLM-judge call per answer extracts `(entity, attribute, value, unit, time)` against the
   golden slot schema (Anthropic: a single-prompt judge was the most consistent).
2. **Metrics per case:**
   - value accuracy vs ground truth,
   - **fact pass^k** (k=3): identical normalised fact sets across all runs *and* matching
     ground truth,
   - paraphrase agreement,
   - tokens, orchestrator turns, inner calls, bounced Tasks,
   - role violations (S3), validation rejections (S2).
3. **Golden set to ~20 cases**, following Anthropic's "about 20 queries representing real
   usage":
   - paraphrase pairs,
   - concept questions (load / efficiency / "running hot"),
   - a root-cause question,
   - an out-of-scope question,
   - an ambiguous-system question,
   - a no-time history question (A4-style trap).
4. **Pin the data snapshot** in the report header (generator version, seed, anchor from
   `run_metadata`).
5. **Sampling experiment (O8)** runs here, because it changes nothing else.
6. **Quick safety fix, independent of the rest:** a Python execution timeout.

---

## 7. Roadmap

Each phase ends with the Phase-A eval. A change that doesn't improve its target metric
without regressing value accuracy is reverted.

| Phase | Contents | Target metric | Exit criterion |
|---|---|---|---|
| **A — Measure** | Fact extraction + pass^k; golden set to ~20 with paraphrases; snapshot pinning; sampling experiment; Python timeout. | Baseline fact pass^3, paraphrase agreement. | Baseline recorded; sampling config chosen by data. |
| **B — Orchestrator sequencing** (priority 1) | Information ledger via mandatory `set_plan` (O1); concept glossary + derived units (O2); capability registry (O4); slot-keyed typed findings (S6); step references (O3); LLM progress ledger with binding code facts + stall→replan, then typed-fact checks re-scored on `experiments/progress_ledger` (O5); answer check (O6); zero-node budget guard (O7). | Fact pass^3 on multi-step and concept cases; progress-ledger scenario accuracy; routing and value ≥ baseline. | Fact pass^3 ≥ 0.8; no value regression; tokens ≤ +30%. |
| **C — Specialist determinism** (priority 2) | Recipe tools SQL/Cypher/analysis (S1); sqlglot qualify + Cypher `EXPLAIN` + datetime-trap + empty-result diagnostics (S2); role enforcement (S3); container sandbox, persistent session, seeds (S4). | Fact pass^3 on single-agent cases; bounced/failed queries per case. | Fact pass^3 ≥ 0.95 on recipe-covered cases; zero role violations. |
| **D — Decide by data** | Verified query repository (S5). Then evaluate: (a) code-owned executor with parallel scheduling (O9, LLMCompiler/ReWOO style) vs current supervisor loop; (b) optional answer/plan cache keyed by (snapshot, normalised question), off by default. | Remaining variance and latency. | Adopt (a)/(b) only if they move pass^k or latency materially. |

---

## 8. Explicitly not doing

- **Temperature 0 as the determinism strategy:** contradicts Gemini 3 guidance, and
  batch-variant inference means it can't deliver anyway.
- **Letting an LLM progress ledger override hard code facts:** it believed "delivered
  successfully" over zero artifacts and a budget stop (C6). **Code-only progress signals:**
  8 points less accurate than the LLM + code combination and blind to meaning (O5).
- **Multi-candidate SQL + execution voting as default:** N× tokens. Fallback-only, after
  recipes and validation.
- **A fully hardcoded question-type router:** violates dynamic sequencing. Code validates and
  schedules; the model routes.
- **`langchain-sandbox`:** archived. **E2B by default:** data egress.
- **Caching as a substitute for fixing variance:** caching makes repeats identical but hides
  the underlying nondeterminism and fails on paraphrases. Evaluate with cache off.

---

## 9. Evidence log (this repository)

| Run | Observation |
|---|---|
| `eval/report-baseline.md` → `eval/report-final.md` | Tokens 57.6k → 34.2k; `write_todos` 8 → 0; window determinism 75% → 88%; value 100%; "determinism" 0% (metric defect). |
| A4 (doc-09 session) | The orchestrator added `time: 'last 24 months'` to a no-time question → 22 vs 23 work orders. Fixed by field description; illustrates O1. |
| A7 ×2 (2026-09-13) | Different feature sets (5 vs 4); standby 33.33% vs 33.37%; running 66.67% vs inconsistent 60.86%; flow t/h vs invented m³/h. sql_agent 8 catalog queries; coder 6 SQL queries incl. `information_schema` and hallucinated columns; `KMeans is not defined` twice (no persistent session). |
| Neo4j `EXPLAIN` probe | Unknown property/label/relationship → warnings with positions; string-vs-datetime compare → no warning. |
| sqlglot `qualify` probe | `bearing_temp_9` rejected with position; CTE, `_long` view and join accepted. |
| Graph introspection | Orchestrator nodes: `_fresh_plan.before_agent`, `ModelCallLimitMiddleware.before_model`, `.after_model`; `wrap_model_call` middleware adds none. |
| `ModelCallLimitMiddleware` source | `exit_behavior="end"` emits "Model call limits exceeded: …" as the final message. |
| `experiments/progress_ledger` (2026-09-13) | 22 labelled states, 330 LLM calls. Label accuracy: code 0.844; Magentic LLM ledger 0.83 (15–16/22 consistent); reworded ledger 0.917; reworded ledger + binding code facts 0.927 (18/22 fully right). Every LLM arm missed scope narrowing, a reworded repeat, and a contradiction between reports. |

---

## 10. Sources

**Orchestration**
- Anthropic — [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system)
- Anthropic — [When to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them)
- Microsoft Research — [Magentic-One paper](https://arxiv.org/html/2411.04468v1) · [Agent Framework Magentic orchestration](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic)
- LangChain — [Plan-and-Execute agents (ReWOO, LLMCompiler)](https://www.langchain.com/blog/planning-agents) · [Multi-agent patterns](https://docs.langchain.com/oss/python/langchain/multi-agent) · [Choosing the right multi-agent architecture](https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture)
- LangChain — [deepagents](https://github.com/langchain-ai/deepagents)
- HumanLayer — [12-factor agents](https://github.com/humanlayer/12-factor-agents)
- Cognition — [Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents) · [Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working)
- Zhang et al. — [Agentic Plan Caching (NeurIPS 2025)](https://arxiv.org/abs/2506.14852)
- AutoGen — [Magentic-One progress-ledger prompt](https://github.com/microsoft/autogen/blob/main/python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/_magentic_one/_prompts.py) · ledger parse failures [#6599](https://github.com/microsoft/autogen/issues/6599), [PR #7913](https://github.com/microsoft/autogen/pull/7913)
- Cemri et al. — [Why Do Multi-Agent LLM Systems Fail? (MAST)](https://arxiv.org/abs/2503.13657)
- Huang et al. — [Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798) · [The Self-Correction Illusion](https://arxiv.org/html/2606.05976v1) · [Agentic Uncertainty Reveals Agentic Overconfidence](https://arxiv.org/pdf/2602.06948)

**Determinism and evaluation**
- Thinking Machines — [Defeating Nondeterminism in LLM Inference](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- Google — [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3) · [Content generation parameters (seed)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/content-generation-parameters)
- Sierra — [τ-bench, pass^k](https://arxiv.org/abs/2406.12045)
- [When Agents Disagree With Themselves: behavioural consistency](https://arxiv.org/pdf/2602.11619)

**Text-to-SQL and semantic layers**
- dbt Labs — [Semantic Layer vs. Text-to-SQL: 2026 Benchmark](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- Snowflake — [Cortex Analyst Verified Query Repository](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository) · [Text-to-SQL accuracy for BI](https://www.snowflake.com/en/blog/engineering/cortex-analyst-text-to-sql-accuracy-bi/)
- Atlan — [Text-to-SQL for enterprise: metric drift](https://atlan.com/know/ai-agent/data-for-ai/text-to-sql-for-enterprise/)
- [CHASE-SQL](https://arxiv.org/html/2410.01943v1) · [SIRIUS-SQL](https://arxiv.org/html/2606.01246) · [BIRD benchmark](https://bird-bench.github.io/)
- sqlglot — [qualify](https://sqlglot.com/sqlglot/optimizer/qualify.html) · [qualify_columns](https://sqlglot.com/sqlglot/optimizer/qualify_columns.html)

**Text-to-Cypher**
- Neo4j — [Text2Cypher guide](https://neo4j.com/blog/genai/text2cypher-guide/) · [Verifying Cypher with CyVer](https://medium.com/neo4j/verifying-neo4j-cypher-queries-with-cyver-2ed5efbaa5af) · [Server notifications](https://neo4j.com/docs/status-codes/current/notifications/)

**Sandboxing and tools**
- [langchain-sandbox (archived)](https://github.com/langchain-ai/langchain-sandbox) · [smolagents secure execution](https://github.com/huggingface/smolagents) · [llm-sandbox](https://github.com/vndee/llm-sandbox)
- Anthropic — [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) · [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
