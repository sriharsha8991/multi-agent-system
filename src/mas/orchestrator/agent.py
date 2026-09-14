"""The orchestrator — a supervisor agent over three specialists (Problem.md §1).

The model decides, per question, what the answer needs and who fills it; code decides
everything that can be decided exactly (doc 10):

    START → [_fresh_plan] → orchestrator ⇄ [set_plan | graph_agent | sql_agent | coder_agent] → answer

* ``set_plan(slots, steps)`` — mandatory ledger: the facts the answer needs (slots) and the
  steps that fill them. Validated against the capability registry, the glossary and the
  question's time scope; may go in the same turn as the first delegation.
* delegation tools take a ``Task`` (step + slot ids). ``briefs.prepare`` resolves
  references, time and tags, fingerprints the request and applies the strict code-only
  progress rules (``ledger.pre_run_problems``) before any specialist runs.
* a specialist returns a typed ``SpecialistReport``; ``ledger.apply_report`` validates it
  (slots, required fields, units, artifacts, contradictions) and updates the ledger.
* ``OrchestratorGuard`` bounds model calls and checks the final answer against the facts,
  appending code-written Evidence and Gaps.

Each specialist runs in its own context; only the rendered, checked report crosses back.
Artifacts flow through the ``blackboard``; payloads never enter a prompt.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import before_agent, dynamic_prompt
from langchain.agents.structured_output import StructuredOutputValidationError
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from ..agents import specialists
from ..agents.base import PLAN_RESET, MASState, build_model
from ..agents.prompts import supervisor_prompt
from ..execution.py_sandbox import close_session
from ..llm.schemas import PlanStep, Slot, SpecialistReport, Task
from . import briefs, ledger
from .guard import OrchestratorGuard
from .trace import content_text

# ── budget ───────────────────────────────────────────────────────────────────────
# Every middleware *hook* is its own super-step; ``wrap_model_call`` middleware is not. With
# the guard and the ledger view both wrapping the model call, one turn is two super-steps
# (model -> tools). It was four under ``ModelCallLimitMiddleware`` (before/after hooks) and
# five while ``TodoListMiddleware`` added its own ``after_model``. ``_fresh_plan`` runs once
# per question.
ORCHESTRATOR_MODEL_CALLS = 20
_SUPER_STEPS_PER_TURN = 2
#: One-off nodes outside the turn loop (``_fresh_plan``'s before_agent) plus margin.
_FIXED_SUPER_STEPS = 3

#: Hard ceiling, sized so the guard's budget always binds first.
MAX_SUPERVISOR_STEPS = (_SUPER_STEPS_PER_TURN * (ORCHESTRATOR_MODEL_CALLS + 1)
                        + _FIXED_SUPER_STEPS)


def _run_specialist(agent, brief: str, blackboard: dict, delegation_id: str
                    ) -> tuple[dict, bool, SpecialistReport | None, str | None]:
    """Run a specialist; return ``(last_state, exhausted, report, raw_text_if_unstructured)``.

    Streams rather than ``invoke``s, so a specialist that runs out of super-steps still hands
    back the state it reached. A final message that fails the report schema is kept as raw
    text (``StructuredOutputValidationError`` carries it) instead of losing the run.
    """
    state: dict = {}
    exhausted = False
    raw: str | None = None
    try:
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": brief}], "blackboard": dict(blackboard)},
            config={"recursion_limit": specialists.SPECIALIST_STEPS,
                    "configurable": {"delegation_id": delegation_id}},
            stream_mode="values",
        ):
            state = chunk
    except GraphRecursionError:
        exhausted = True
    except StructuredOutputValidationError as e:
        raw = content_text(e.ai_message.content) if e.ai_message is not None else str(e)
    report = state.get("structured_response")
    if report is not None and not isinstance(report, SpecialistReport):
        report = SpecialistReport.model_validate(report)
    if report is None and raw is None:
        messages = state.get("messages") or []
        raw = content_text(messages[-1].content) if messages else ""
    return state, exhausted, report, raw


#: Code shapes that do not belong in a report handed to another agent.
_CODE_IN_TEXT = re.compile(r"\bSELECT\b[^;]{0,400}?\bFROM\b|\bMATCH\s*\(|^\s*import\s+\w+", re.M)
_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?")


def _delegation_metrics(result: dict, report_text: str, sub_events: list[dict]) -> dict:
    """Cost and hygiene of one delegation, measured from what the specialist actually did."""
    usage = [getattr(m, "usage_metadata", None) or {} for m in (result.get("messages") or [])]
    queries = " ".join(str(e.get("sql") or e.get("cypher") or "") for e in sub_events)
    return {
        "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
        "model_calls": sum(1 for u in usage if u),
        "report_chars": len(report_text),
        "report_has_code": bool(_CODE_IN_TEXT.search(report_text)),
        "windows": sorted({t.replace(" ", "T") for t in _ISO_TS.findall(queries)}),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _delegate(agent, task: Task, runtime: ToolRuntime, label: str) -> Command:
    """Prepare, check and run one delegation; validate its report into the ledger."""
    t0 = time.perf_counter()
    state = dict(runtime.state or {})
    blackboard = dict(state.get("blackboard") or {})
    before = set(blackboard)

    def event(**extra) -> dict:
        return {"tool": f"delegate:{label}", "agent": "orchestrator", "at": _now(),
                "ms": round((time.perf_counter() - t0) * 1000), "step_id": task.step_id,
                "slots": task.slots, **extra}

    prepared = briefs.prepare(task, label, state)
    if prepared.problems:
        reason = "; ".join(prepared.problems)
        return Command(update={
            "tool_events": [event(error=f"rejected: {reason}"[:400])],
            "messages": [ToolMessage(f"Task rejected by code, nothing ran: {reason}",
                                     tool_call_id=runtime.tool_call_id)]})

    slots, steps = ledger.effective_ledger(state)
    round_key = f"r:{runtime.tool_call_id}"
    try:
        result, exhausted, report, raw = _run_specialist(agent, prepared.brief, blackboard,
                                                         runtime.tool_call_id)
        error = None
    except Exception as e:  # noqa: BLE001 — a crashed specialist is a failed round, not a crash
        result, exhausted, report, raw, error = {}, False, None, None, str(e)[:300]
    finally:
        close_session(runtime.tool_call_id)

    updated = result.get("blackboard") or blackboard
    created = sorted(set(updated) - before)
    if report is None:
        report = SpecialistReport(
            status="failed" if error else "partial",
            answer=(raw or error or "no report")[:500],
            gaps=[f"specialist error: {error}" if error else
                  "the report was not structured, so no finding could be checked or accepted"])

    update, notes, status = ledger.apply_report(
        state, slots, steps, step_id=task.step_id, agent=label, task_slots=task.slots,
        windows=prepared.windows, linked=prepared.linked, report=report, created=created,
        blackboard=updated, exhausted=exhausted, fp=prepared.fingerprint, round_key=round_key,
        failed_error=error)
    rendered = ledger.render_report(task.step_id, label, status, report, update, notes,
                                    raw_fallback=raw)

    sub_events = [{**e, "agent": label} for e in (result.get("tool_events") or [])]
    events = [event(brief=prepared.brief[:1500], status=status, artifacts_created=created,
                    inner_calls=len(sub_events), fingerprint=prepared.fingerprint,
                    windows_resolved=prepared.windows, code_notes=notes,
                    **_delegation_metrics(result, rendered, sub_events),
                    **({"error": error or "step budget exhausted"} if error or exhausted else {}))]
    events.extend(sub_events)

    return Command(update={
        **update,
        "blackboard": updated,
        "tool_events": events,
        "messages": [ToolMessage(rendered, tool_call_id=runtime.tool_call_id)],
    })


@tool
def graph_agent(task: Task, runtime: ToolRuntime) -> Command:
    """Fill lookup slots from the Neo4j graph: tags and setpoints, alerts, work orders, parts,
    costs. No sensor values."""
    return _delegate(specialists.graph_agent(), task, runtime, "graph_agent")


@tool
def sql_agent(task: Task, runtime: ToolRuntime) -> Command:
    """Fill measure slots from telemetry: per-tag stats and when extremes happened, time
    above thresholds, system comparisons, series for plotting."""
    return _delegate(specialists.sql_agent(), task, runtime, "sql_agent")


@tool
def coder_agent(task: Task, runtime: ToolRuntime) -> Command:
    """Fill derive slots — statistics, correlation, clustering, trends, one figure — from
    artifacts earlier steps fetched (pass them in `inputs`, e.g. '$s1.artifacts')."""
    return _delegate(specialists.coder_agent(), task, runtime, "coder_agent")


@tool
def set_plan(slots: list[Slot], steps: list[PlanStep], runtime: ToolRuntime) -> Command:
    """Record the ledger: the facts the answer needs (slots) and the steps that fill them.

    Required before any delegation — call it in the same turn as the first one. Code keeps
    every slot's status and facts and shows them as SLOTS each turn. Call again to revise
    after a STALLED or blocked slot; filled slots and done steps cannot change.
    """
    state = dict(runtime.state or {})
    problems = ledger.plan_problems(slots, steps, state)
    if problems:
        return Command(update={
            "tool_events": [{"tool": "set_plan", "agent": "orchestrator", "at": _now(),
                             "error": "rejected: " + "; ".join(problems)[:400]}],
            "messages": [ToolMessage("Plan rejected by code: " + "; ".join(problems),
                                     tool_call_id=runtime.tool_call_id)]})

    existing = state.get("slots") or {}
    slot_update = {}
    for s in slots:
        definition = s.model_dump(mode="json")
        # Never write status for a new slot: set_plan shares a turn with the first delegation
        # and parallel updates merge in either order. A revised, unfilled slot starts over.
        if s.slot_id in existing and existing[s.slot_id].get("status") != "filled":
            definition.update(status="pending", attempts_failed=0, missing=[])
        slot_update[s.slot_id] = definition
    step_update = {st.step_id: ledger.step_record(st) for st in steps}
    summary = ("slots: " + " · ".join(f"{s.slot_id} {s.kind}/{s.aggregation}" for s in slots)
               + " | steps: " + " · ".join(
                   f"{st.step_id} {st.agent}→{','.join(st.slots)}"
                   + (f" after {','.join(st.depends_on)}" if st.depends_on else "") for st in steps))
    return Command(update={
        "slots": slot_update,
        "plan": step_update,
        "rounds": {f"p:{runtime.tool_call_id}": {"kind": "replan", "at": ledger.now_iso()}},
        "tool_events": [{"tool": "set_plan", "agent": "orchestrator", "at": _now(), "plan": summary}],
        "messages": [ToolMessage(f"Plan recorded — {summary}", tool_call_id=runtime.tool_call_id)]})


TEAM = [graph_agent, sql_agent, coder_agent, set_plan]


@before_agent
def _fresh_plan(state, runtime) -> dict:
    """Each question starts with an empty ledger; artifacts from earlier turns stay usable."""
    return {"plan": PLAN_RESET, "slots": PLAN_RESET, "facts": PLAN_RESET,
            "rounds": PLAN_RESET, "checks": PLAN_RESET}


@dynamic_prompt
def _ledger_view(request) -> str:
    """Append SLOTS, PLAN, PROGRESS and ARTIFACTS — kept by code — to the orchestrator prompt."""
    view = ledger.ledger_view(request.state or {})
    return (request.system_prompt or "") + (f"\n\n{view}" if view else "")


#: Kept for callers of the previous name.
def ledger_text(state: dict) -> str:
    return ledger.ledger_view(state)


def build_agent(checkpointer: Any | None = None):
    """Compile the orchestrator. Pass a checkpointer for multi-turn (thread_id) sessions."""
    return create_agent(
        model=build_model(),
        tools=TEAM,
        system_prompt=supervisor_prompt(ORCHESTRATOR_MODEL_CALLS),
        state_schema=MASState,
        checkpointer=checkpointer,
        middleware=[
            _fresh_plan,
            OrchestratorGuard(ORCHESTRATOR_MODEL_CALLS),
            _ledger_view,
        ],
        name="orchestrator",
    )


def run(query: str, *, thread_id: str | None = None, checkpointer: Any | None = None) -> dict:
    """Answer one question. Returns the final state (messages, ledger, blackboard, events)."""
    agent = build_agent(checkpointer)
    config: dict = {"recursion_limit": MAX_SUPERVISOR_STEPS}
    if thread_id is not None:
        config["configurable"] = {"thread_id": thread_id}

    state: dict = {}
    try:
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": query}], "blackboard": {}},
            config=config, stream_mode="values",
        ):
            state = chunk
    except GraphRecursionError:
        state = {**state, "budget_exhausted": True}
    return state


def answer_of(result: dict) -> str:
    """The orchestrator's final message — the answer."""
    messages = result.get("messages") or []
    return content_text(messages[-1].content) if messages else ""
