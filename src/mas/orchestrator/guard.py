"""Orchestrator guard — budget and final-answer checks around every model call (doc 10, O6/O7).

A ``wrap_model_call`` middleware, so it adds **no graph node**. It replaces
``ModelCallLimitMiddleware``, whose "end" behaviour finished a run with the literal text
"Model call limits exceeded" instead of an answer, and whose two hooks cost two super-steps
on every turn.

Per model call:

* **Budget.** Calls are counted from the messages since the question. The last allowed call
  runs without tools, so the model must answer from the ledger; past the budget, code writes
  the answer from the accepted facts.
* **Unattempted slots.** A final answer while planned slots were never delegated (and the
  plan is not stalled) gets one strict nudge: delegate them, or answer and they are listed
  as gaps.
* **Numbers.** Every number with a unit must be an accepted fact, a setpoint of a tag in
  play, a number from the question, or simple arithmetic on those
  (``ledger.answer_problems``). Violations get one repair call; anything still unsupported is
  listed under "Unverified by code".
* **Footers.** Evidence (slot ← artifacts) and Gaps are appended by code, not written by the
  model.
"""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from . import ledger
from .trace import content_text

MAX_REPAIRS = 2


def calls_this_question(messages: list) -> int:
    n = 0
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage):
            n += 1
    return n


def _last_ai(response: ModelResponse) -> AIMessage | None:
    return next((m for m in reversed(response.result or []) if isinstance(m, AIMessage)), None)


def _unattempted(state: dict) -> list[str]:
    return sorted((sid for sid, s in (state.get("slots") or {}).items()
                   if s.get("status", "pending") == "pending" and not s.get("attempts_failed")),
                  key=lambda k: int(k[1:]))


class OrchestratorGuard(AgentMiddleware):
    def __init__(self, model_calls: int):
        super().__init__()
        self.model_calls = model_calls

    # ── shared logic ─────────────────────────────────────────────────────────
    def _budget(self, request) -> tuple[Any, bool, AIMessage | None]:
        used = calls_this_question(request.messages)
        if used >= self.model_calls:
            return request, True, AIMessage(content=ledger.budget_answer(request.state or {}))
        if used >= self.model_calls - 1:
            note = HumanMessage(content="BUDGET: this is your last turn. Answer the question now "
                                        "from the SLOTS ledger; code will list the gaps.")
            return request.override(tools=[], messages=[*request.messages, note]), True, None
        return request, False, None

    def _next_feedback(self, text: str, state: dict, last_turn: bool, done: set[str]) -> tuple[str | None, str, bool]:
        """(feedback, kind, keep_tools) for the next repair, or (None, '', False) to release."""
        slots = state.get("slots") or {}
        stalled = ledger.stall_count(ledger.ordered_rounds(state)) >= ledger.STALL_LIMIT
        pending = _unattempted(state)
        nudged = bool((state.get("checks") or {}).get("pending_nudge"))
        if slots and pending and not last_turn and not stalled and not nudged and "nudge" not in done:
            asks = "; ".join(f"{s} ({slots[s].get('ask')})" for s in pending)
            return (f"CODE CHECK: planned slots were never delegated: {asks}. Delegate them now, "
                    "or answer again and they will be listed as gaps.", "nudge", True)
        problems = ledger.answer_problems(text, state)
        if problems and "numbers" not in done:
            return ("CODE CHECK: these statements are not supported by the accepted facts: "
                    + "; ".join(problems) + ". Rewrite the answer using only numbers from the "
                    "SLOTS ledger (or arithmetic on them, shown), with the catalog units.",
                    "numbers", False)
        return None, "", False

    def _finalise(self, response: ModelResponse, state: dict, nudged: bool) -> Any:
        ai = _last_ai(response)
        command = Command(update={"checks": {"pending_nudge": {"used": True}}}) if nudged else None
        if ai is None or ai.tool_calls or not (state.get("slots") or {}):
            return ExtendedModelResponse(model_response=response, command=command) if command else response
        text = content_text(ai.content)
        unverified = ledger.answer_problems(text, state)
        final = AIMessage(content=text + ledger.footers(state, unverified or None), id=ai.id,
                          response_metadata=ai.response_metadata, usage_metadata=ai.usage_metadata)
        result = [final if m is ai else m for m in response.result]
        new = ModelResponse(result=result, structured_response=response.structured_response)
        return ExtendedModelResponse(model_response=new, command=command) if command else new

    # ── sync ─────────────────────────────────────────────────────────────────
    def wrap_model_call(self, request, handler):
        request, last_turn, early = self._budget(request)
        if early is not None:
            return early
        state = request.state or {}
        response = handler(request)
        extra: list = []
        done: set[str] = set()
        for _ in range(MAX_REPAIRS):
            ai = _last_ai(response)
            if ai is None or ai.tool_calls:
                break
            feedback, kind, keep_tools = self._next_feedback(content_text(ai.content), state,
                                                             last_turn, done)
            if feedback is None:
                break
            done.add(kind)
            extra += [ai, HumanMessage(content=feedback)]
            retry = request.override(messages=[*request.messages, *extra],
                                     tools=request.tools if keep_tools else [])
            response = handler(retry)
        return self._finalise(response, state, "nudge" in done)

    # ── async ────────────────────────────────────────────────────────────────
    async def awrap_model_call(self, request, handler):
        request, last_turn, early = self._budget(request)
        if early is not None:
            return early
        state = request.state or {}
        response = await handler(request)
        extra: list = []
        done: set[str] = set()
        for _ in range(MAX_REPAIRS):
            ai = _last_ai(response)
            if ai is None or ai.tool_calls:
                break
            feedback, kind, keep_tools = self._next_feedback(content_text(ai.content), state,
                                                             last_turn, done)
            if feedback is None:
                break
            done.add(kind)
            extra += [ai, HumanMessage(content=feedback)]
            retry = request.override(messages=[*request.messages, *extra],
                                     tools=request.tools if keep_tools else [])
            response = await handler(retry)
        return self._finalise(response, state, "nudge" in done)
