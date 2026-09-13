"""The orchestrator guard: budget, unattempted-slot nudge, answer check, code-written footers.

A scripted fake model stands in for Gemini — no LLM calls.
"""
from __future__ import annotations

from langchain.agents.middleware.types import ExtendedModelResponse, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from mas.llm.schemas import Slot
from mas.orchestrator import ledger
from mas.orchestrator.guard import OrchestratorGuard

Q = "What was the maximum bearing temperature on BFP-A yesterday?"


def _state(filled: bool = True) -> dict:
    s = Slot(slot_id="f1", kind="measure", ask="max bearing temperature", systems=["bfpa"],
             concepts=["bearing temperature"], aggregation="max", needs=["value"],
             time={"phrase": "yesterday"})
    rec = ledger.slot_record(s)
    st = {"messages": [HumanMessage(content=Q)], "slots": {"f1": rec}, "plan": {}, "rounds": {},
          "checks": {}, "facts": {}}
    if filled:
        rec.update(status="filled", facts=["s1.1"], linked_tags=["bfpa.bearing_temp_8"])
        st["facts"] = {"s1.1": {"key": "s1.1", "slot_id": "f1", "step_id": "s1", "value": 65.8,
                                "unit": "degC", "entity": "bfpa.bearing_temp_8", "attribute": "max",
                                "artifact_id": "t1", "statement": "max 65.8 degC"}}
    return st


class ScriptedModel:
    """handler(request) → the next scripted AIMessage; records what each call received."""

    def __init__(self, *replies: AIMessage):
        self.replies = list(replies)
        self.requests: list[ModelRequest] = []

    def __call__(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(result=[self.replies.pop(0)])


def _request(state: dict, messages: list | None = None) -> ModelRequest:
    return ModelRequest(model=None, messages=messages or list(state["messages"]), tools=["tool"],
                        state=state)


def _final(result) -> AIMessage:
    response = result.model_response if isinstance(result, ExtendedModelResponse) else result
    return response.result[-1]


def test_supported_answer_passes_once_and_gets_code_footers():
    model = ScriptedModel(AIMessage(content="The maximum was 65.8 °C, 24.2 °C below alarm_hi."))
    result = OrchestratorGuard(20).wrap_model_call(_request(_state()), model)
    text = _final(result).content
    assert len(model.requests) == 1
    assert "**Evidence:** f1 ← t1 (s1)" in text and "Unverified" not in text


def test_unsupported_number_gets_one_repair_then_is_flagged():
    model = ScriptedModel(AIMessage(content="The maximum was 67.2 °C."),
                          AIMessage(content="The maximum was 67.9 °C."))
    result = OrchestratorGuard(20).wrap_model_call(_request(_state()), model)
    assert len(model.requests) == 2
    feedback = model.requests[1].messages[-1].content
    assert "CODE CHECK" in feedback and "67.2 °C" in feedback
    assert model.requests[1].tools == []                 # a repair is an answer, not more tools
    assert "**Unverified by code:** '67.9 °C'" in _final(result).content


def test_answer_before_attempting_planned_slots_is_nudged_once():
    model = ScriptedModel(AIMessage(content="I think it was fine."),
                          AIMessage(content="", tool_calls=[{"name": "sql_agent", "id": "c1",
                                                             "args": {"task": {"step_id": "s1", "slots": ["f1"]}}}]))
    result = OrchestratorGuard(20).wrap_model_call(_request(_state(filled=False)), model)
    assert isinstance(result, ExtendedModelResponse)
    assert result.command.update["checks"]["pending_nudge"]["used"] is True
    assert "never delegated" in model.requests[1].messages[-1].content
    assert model.requests[1].tools == ["tool"]           # the nudge keeps tools available
    assert _final(result).tool_calls


def test_last_turn_runs_without_tools_and_budget_end_is_written_by_code():
    st = _state()
    history = [HumanMessage(content=Q)] + [AIMessage(content="", tool_calls=[]) for _ in range(19)]
    model = ScriptedModel(AIMessage(content="The maximum was 65.8 °C."))
    OrchestratorGuard(20).wrap_model_call(_request(st, history), model)
    assert model.requests[0].tools == [] and "last turn" in model.requests[0].messages[-1].content

    over = [HumanMessage(content=Q)] + [AIMessage(content="") for _ in range(20)]
    result = OrchestratorGuard(20).wrap_model_call(_request(st, over), ScriptedModel())
    assert isinstance(result, AIMessage) and "budget" in result.content and "max 65.8 degC" in result.content


def test_tool_calls_pass_through_untouched():
    call = AIMessage(content="", tool_calls=[{"name": "set_plan", "id": "c1", "args": {}}])
    model = ScriptedModel(call)
    assert _final(OrchestratorGuard(20).wrap_model_call(_request(_state()), model)) is call
