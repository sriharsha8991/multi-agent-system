"""Regression tests for the specialist step/tool budgets and partial-work handover.

These cover a failure that was silent and expensive. A trace ran with
``recursion_limit=20`` on the belief that it bought "~10 tool calls"; because every
middleware ``after_model`` hook is its own super-step it actually bought 6 — and 4 for the
coder, which carried two limiters. Five of ten delegations were killed by
``GraphRecursionError``, ``_delegate`` discarded the exception's state, and 41% of all
input tokens in the run went into work the orchestrator never saw.

Nothing failed loudly. So the invariants are asserted here instead:

* the tool budget must be *reachable* within the recursion limit, so the graceful limiter
  is what an agent hits rather than the hard ceiling;
* the orchestrator's recursion ceiling must leave room for its whole model-call budget.
"""
from __future__ import annotations

import pytest

from mas.agents import specialists

#: Super-steps consumed by one loop iteration beyond ``model`` and ``tools``.
_BASE_NODES_PER_ITERATION = 2


@pytest.mark.parametrize(
    "factory, budget",
    [
        (specialists.sql_agent, specialists.SPECIALIST_TOOL_CALLS),
        (specialists.graph_agent, specialists.SPECIALIST_TOOL_CALLS),
        (specialists.coder_agent, specialists.CODER_TOOL_CALLS),
    ],
)
def test_tool_budget_is_reachable_within_the_step_limit(factory, budget):
    """The graceful limit must bind before the hard one.

    Counts the compiled graph's real ``after_model`` nodes rather than trusting the
    arithmetic in ``specialists``, so adding a middleware that pushes an agent over the
    ceiling fails here instead of in production.
    """
    nodes = list(factory().get_graph().nodes)
    after_model = [n for n in nodes if "after_model" in n]
    per_iteration = _BASE_NODES_PER_ITERATION + len(after_model)

    # Every tool call, one refused over-budget attempt (model + its hooks, no tools step —
    # a traced run made exactly this and hit the ceiling after writing its report), plus a
    # final model turn (and its hooks) to write the report.
    turn_without_tools = 1 + len(after_model)
    needed = per_iteration * budget + turn_without_tools * 2
    # Strictly below: landing exactly on the limit still raises GraphRecursionError.
    assert needed < specialists.SPECIALIST_STEPS, (
        f"{factory.__name__} needs {needed} super-steps to spend its {budget}-call tool "
        f"budget ({per_iteration}/iteration x {len(after_model)} after_model hooks) and "
        f"report, but SPECIALIST_STEPS is {specialists.SPECIALIST_STEPS}. The recursion "
        f"limit would fire first — killing the agent or stamping a finished report "
        f"INCOMPLETE."
    )


def test_one_tool_limiter_per_specialist():
    """Each extra per-tool limiter costs a super-step per iteration, so keep it at one."""
    for factory in (specialists.sql_agent, specialists.graph_agent, specialists.coder_agent):
        after_model = [n for n in factory().get_graph().nodes if "after_model" in n]
        assert len(after_model) == 1, (
            f"{factory.__name__} has {len(after_model)} after_model nodes: {after_model}"
        )


def test_context_editing_trigger_is_actually_reachable():
    """A trigger above the largest window a specialist reaches is dead configuration."""
    edit = specialists._context_control().edits[0]
    ceiling = specialists.SPECIALIST_TOOL_CALLS * 2_000  # ~2k tokens per tool round trip
    assert edit.trigger < ceiling, (
        f"ClearToolUsesEdit trigger {edit.trigger} is above the ~{ceiling} tokens a "
        f"specialist accumulates over its whole budget, so it would never fire."
    )


def test_orchestrator_step_limit_covers_its_model_call_budget():
    """Same invariant at the supervisor level, where the per-turn cost is higher.

    The guard and ledger view wrap the model call and add no node, so a turn costs two
    super-steps (it was four under ModelCallLimitMiddleware's hooks, five with
    TodoListMiddleware). The old flat limit of 60 bought 11 tool calls while a real run made
    15. One-off ``before_agent`` nodes run once per question and must fit too.
    """
    from mas.orchestrator import agent as orch

    nodes = list(orch.build_agent().get_graph().nodes)
    hooks = [n for n in nodes if "after_model" in n or "before_model" in n]
    once = [n for n in nodes if "before_agent" in n or "after_agent" in n]
    per_turn = _BASE_NODES_PER_ITERATION + len(hooks)

    assert per_turn == orch._SUPER_STEPS_PER_TURN, (
        f"orchestrator middleware changed: {len(hooks)} hooks ({hooks}) means "
        f"{per_turn} super-steps/turn, but _SUPER_STEPS_PER_TURN says "
        f"{orch._SUPER_STEPS_PER_TURN}. Re-derive MAX_SUPERVISOR_STEPS."
    )
    needed = per_turn * orch.ORCHESTRATOR_MODEL_CALLS + per_turn + len(once)
    assert needed < orch.MAX_SUPERVISOR_STEPS, (
        f"orchestrator needs {needed} super-steps for its "
        f"{orch.ORCHESTRATOR_MODEL_CALLS}-call budget but MAX_SUPERVISOR_STEPS is "
        f"{orch.MAX_SUPERVISOR_STEPS}; the recursion limit would kill the run before "
        f"the guard could end it with an answer."
    )


def test_specialist_report_is_typed_and_adds_no_node():
    """``response_format`` must not change the super-step arithmetic above."""
    for factory in (specialists.sql_agent, specialists.graph_agent, specialists.coder_agent):
        nodes = list(factory().get_graph().nodes)
        assert nodes == ["__start__", "model", "tools", "ToolCallLimitMiddleware.after_model",
                         "__end__"], nodes


def test_coder_has_no_database_tool():
    """Role enforcement: the coder analyses artifacts; it cannot fetch with guessed columns."""
    names = {t.name for t in specialists.CODER_TOOLS}
    assert names == {"python_analysis"}


def test_every_graph_publishes_a_state_schema():
    """Studio builds each graph's input/output JSON schema from the state type. A payload
    class in a channel annotation (``blackboard: dict[str, Artifact]`` held a DataFrame) made
    that fail with 'Unable to generate pydantic-core schema for DataFrame'."""
    from mas.orchestrator import agent as orch

    for graph in (orch.build_agent(), specialists.sql_agent(), specialists.graph_agent(),
                  specialists.coder_agent()):
        assert graph.get_input_jsonschema() and graph.get_output_jsonschema()
