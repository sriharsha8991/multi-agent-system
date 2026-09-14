"""Shared agent primitives: the state schema and the model factory.

Kept separate from the specialists and the supervisor so both can import them without a
cycle.
"""
from __future__ import annotations

import operator
from typing import Annotated

from langchain.agents import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import get_settings


def merge_blackboard(left: dict | None, right: dict | None) -> dict:
    """Artifacts are keyed uniquely, so a shallow merge is safe across agents.

    Tolerates a missing side so a client (e.g. LangGraph Studio) can submit only
    ``messages`` without pre-seeding the blackboard.
    """
    return {**(left or {}), **(right or {})}


#: Sent into the per-question channels at the start of each question so a thread's next
#: question does not inherit the last one's ledger.
PLAN_RESET = {"__reset__": True}


def merge_keyed(left: dict | None, right: dict | None) -> dict:
    """Records keyed by id; an update merges into its record, PLAN_RESET clears all.

    Merging per record (not replacing the dict) lets parallel delegations in one turn each
    update their own step, slots and facts without clobbering each other.
    """
    if right and right.get("__reset__"):
        return {}
    merged = dict(left or {})
    for key, fields in (right or {}).items():
        merged[key] = {**merged.get(key, {}), **fields}
    return merged


#: Backwards-compatible name.
merge_plan = merge_keyed


class MASState(AgentState):
    """Agent state + the out-of-prompt channels shared by every agent.

    ``blackboard`` indexes artifact digests and ``tool_events`` is the full observability
    trail; neither is rendered into a prompt. The per-question ledger channels are kept by
    code and shown to the orchestrator only as a compact view:

    * ``slots`` — the facts the answer needs, with status (pending/filled/partial/conflict/
      blocked) and the fact keys that fill them;
    * ``plan``  — steps (agent, slots, depends_on) with status, handoff and artifacts;
    * ``facts`` — every accepted finding, keyed ``<step_id>.<n>``;
    * ``rounds`` — one record per delegation attempt (fingerprint, outcome, new slots), the
      input to the code-only progress checks;
    * ``checks`` — notes from the answer guard (e.g. that the pending-slot nudge was used).
    """

    #: artifact id → its JSON-safe digest. Payloads (DataFrames, PNGs) live in ``memory.store``;
    #: typing this as the artifact classes broke Studio's state schema (a DataFrame has none).
    blackboard: Annotated[dict[str, dict], merge_blackboard]
    tool_events: Annotated[list[dict], operator.add]
    plan: Annotated[dict[str, dict], merge_keyed]
    slots: Annotated[dict[str, dict], merge_keyed]
    facts: Annotated[dict[str, dict], merge_keyed]
    rounds: Annotated[dict[str, dict], merge_keyed]
    checks: Annotated[dict[str, dict], merge_keyed]


def build_model(fast: bool = False, *, role: str = "orchestrator") -> ChatGoogleGenerativeAI:
    """The chat model for a role. Sampling comes from settings (doc 10, O8 experiment).

    Only explicitly configured sampling fields are passed: the LangChain wrapper otherwise
    applies its own defaults, which are neither ours nor the provider's.
    """
    s = get_settings()
    kwargs: dict = {"model": s.gemini_fast_model if fast else s.gemini_reasoning_model,
                    "google_api_key": s.gemini_api_key}
    if s.gemini_temperature is not None:
        kwargs["temperature"] = s.gemini_temperature
    if s.gemini_seed is not None:
        kwargs["seed"] = s.gemini_seed
    if role == "specialist" and s.specialist_thinking_budget is not None:
        kwargs["thinking_budget"] = s.specialist_thinking_budget
    return ChatGoogleGenerativeAI(**kwargs)
