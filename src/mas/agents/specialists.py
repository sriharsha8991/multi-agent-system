"""The three specialist agents (Problem.md §3).

Each is a full `create_agent` with its own tools, its own brief, and — critically — its
own message history. The orchestrator delegates a Task and receives only the specialist's
final report, so the specialist's internal tool chatter never enters the orchestrator's
context. That context isolation is the point of the multi-agent split.

**Typed reports.** Every specialist ends with a ``SpecialistReport`` (``response_format``
via the provider's native structured output — Gemini 3 supports it alongside tool calls,
and it adds no graph node). Findings are keyed to ledger slots, so code can check them
(``orchestrator.ledger.apply_report``) instead of reading prose.

**Tools, strictly by role (doc 10, S3).** Each specialist writes its own queries or code with
one capable tool (plus a catalog lookup for sql_agent); nothing is pre-written for it. The
coder has no database tool at all: it works on artifacts it is given, so it can no longer
re-fetch data with guessed column names.

**Why the middleware.** Each LLM call re-sends the whole accumulated history, so an agent
that makes N tool calls costs ~N²/2. Two native mechanisms cap that:

* ``ContextEditingMiddleware(ClearToolUsesEdit)`` prunes *old tool results* once the window
  passes a trigger, keeping the last few. Payloads live in ``memory.store``, the trail in
  ``tool_events``.
* ``ToolCallLimitMiddleware`` gives the agent a per-run tool budget, so it is *told* it is
  out of budget — and can still write its report — instead of running into the recursion
  limit, which raises and takes the whole invocation's work with it.
"""
from __future__ import annotations

from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy

from ..llm.schemas import SpecialistReport
from .base import MASState, build_model
from .prompts import coder_agent_prompt, graph_agent_prompt, sql_agent_prompt
from .tools import explore_schema, graph_query, python_analysis, sql_query

# ── budgets ──────────────────────────────────────────────────────────────────────
# LangGraph's ``recursion_limit`` counts *super-steps*, and every middleware that
# contributes an ``after_model`` hook is its own node. With one ToolCallLimitMiddleware the
# real cost of one loop iteration is three super-steps (model -> after_model -> tools),
# plus a final model+after_model to write the report.
#
# Getting this wrong is expensive. A trace ran with ``recursion_limit=20`` believing it
# bought "~10 tool calls"; it actually bought 6 — and the coder, which carried *two*
# limiters (four super-steps per iteration), got 4. Five of ten delegations were killed
# mid-flight, and because the tool budgets (8 / 6) sat above the reachable ceiling they
# could never fire: the recursion limit always got there first.
#
# So derive the step limit from the tool budget, and keep the tool budget binding.
SPECIALIST_TOOL_CALLS = 12
CODER_TOOL_CALLS = 10


#: Super-steps a *refused* over-budget call costs: the limiter answers it in
#: ``after_model`` and jumps straight back to ``model``, so there is no ``tools`` step.
_REFUSED_CALL_STEPS = 2
#: Over-budget attempts to absorb before the report. Models usually try once or twice.
_REFUSED_CALLS_ABSORBED = 2


def _steps_for(tool_calls: int) -> int:
    """Super-steps for ``tool_calls`` iterations, refused attempts, and the final report.

    ``3n + 4`` looked sufficient but ignored the refused call: a traced sql_agent spent
    its 12 calls, tried a 13th (refused, 2 steps), wrote a complete report (2 steps) and
    landed exactly on 40 — so the recursion limit fired *after* the report was written and
    the orchestrator received a finished answer stamped INCOMPLETE.
    """
    return (3 * tool_calls
            + _REFUSED_CALL_STEPS * _REFUSED_CALLS_ABSORBED
            + 2          # final model + after_model that writes the report
            + 2)         # margin for graph entry/exit


#: Ceiling passed as ``recursion_limit``. Sized so the *tool* limiter is what an agent
#: hits first — that returns "you are out of budget" into the conversation and lets the
#: model write its report, instead of raising and losing the run.
SPECIALIST_STEPS = _steps_for(SPECIALIST_TOOL_CALLS)

# Declared once so they can be both bound and introspected (no duplicated lists).
SQL_TOOLS = [sql_query, explore_schema]
GRAPH_TOOLS = [graph_query]
CODER_TOOLS = [python_analysis]


def _context_control(trigger: int = 12_000, keep: int = 3):
    """Prune stale tool output once the window grows past `trigger`, keeping the last `keep`.

    The trigger sits below the window a specialist reaches partway through its budget — at
    20,000 it never fired at all (the largest context in a real run was 18,396) and was
    simply dead configuration.
    """
    return ContextEditingMiddleware(
        edits=[ClearToolUsesEdit(trigger=trigger, keep=keep, clear_tool_inputs=True)]
    )


def _tool_budget(run_limit: int):
    """One *global* tool limiter — deliberately not one per tool name.

    Each limiter is a separate ``after_model`` node, so a per-tool split costs a super-step
    per iteration for every extra tool named.
    """
    return ToolCallLimitMiddleware(run_limit=run_limit, exit_behavior="continue")


def _report_format() -> ProviderStrategy:
    return ProviderStrategy(SpecialistReport)


@lru_cache(maxsize=1)
def sql_agent():
    """PostgreSQL telemetry specialist."""
    return create_agent(
        model=build_model(role="specialist"),
        tools=SQL_TOOLS,
        system_prompt=sql_agent_prompt(SPECIALIST_TOOL_CALLS),
        state_schema=MASState,
        middleware=[_context_control(), _tool_budget(SPECIALIST_TOOL_CALLS)],
        response_format=_report_format(),
        name="sql_agent",
    )


@lru_cache(maxsize=1)
def graph_agent():
    """Neo4j asset-ontology specialist."""
    return create_agent(
        model=build_model(role="specialist"),
        tools=GRAPH_TOOLS,
        system_prompt=graph_agent_prompt(SPECIALIST_TOOL_CALLS),
        state_schema=MASState,
        middleware=[_context_control(), _tool_budget(SPECIALIST_TOOL_CALLS)],
        response_format=_report_format(),
        name="graph_agent",
    )


@lru_cache(maxsize=1)
def coder_agent():
    """Python analysis/visualisation specialist — artifacts in, statistics and one figure out."""
    return create_agent(
        model=build_model(role="specialist"),
        tools=CODER_TOOLS,
        system_prompt=coder_agent_prompt(CODER_TOOL_CALLS),
        state_schema=MASState,
        middleware=[_context_control(), _tool_budget(CODER_TOOL_CALLS)],
        response_format=_report_format(),
        name="coder_agent",
    )
