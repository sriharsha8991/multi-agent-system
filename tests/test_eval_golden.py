"""Golden scoring: checks, pass^k and information determinism — on hand-built final states."""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from mas.eval import golden as G

CASE = {"id": "A1", "query": "max bearing_temp_1 yesterday", "expected_route": ["sql"],
        "checks": {"numbers": [65.8]}}


def result(answer: str, value: float = 65.8, tools=("sql_query",), figure=False) -> dict:
    return {
        "messages": [HumanMessage(content="q"), AIMessage(content=answer)],
        "tool_events": [{"tool": "delegate:sql_agent", "windows": ["2026-09-06T00:00"]}]
                       + [{"tool": t} for t in tools],
        "facts": {"s1.1": {"entity": "bfpa.bearing_temp_1", "attribute": "max", "attribute_norm": "max",
                           "value": value, "unit": "degC", "time": "2026-09-06T15:13:00+00:00"}},
        "blackboard": {"f1": {"kind": "figure"}} if figure else {},
    }


def test_same_information_in_different_words_is_deterministic():
    runs = [result("The maximum was 65.8 °C at 15:13 UTC."),
            result("Bearing 1 peaked at 65.8 degC (15:13 UTC) — well within limits.")]
    r = G.score_case(CASE, runs)
    assert r["pass_k"] and r["fact_det"] and r["answer_det"] and r["window_det"] and r["route_ok"]


def test_different_information_breaks_determinism_and_pass_k():
    r = G.score_case(CASE, [result("65.8 °C"), result("66.1 °C", value=66.1)])
    assert r["fact_det"] is False and r["answer_det"] is False and r["pass_k"] is False
    assert r["value_rate"] == 0.5


def test_footers_do_not_count_as_the_model_s_claims():
    text = "No reading was found.\n\n**Evidence:** f1 ← t65 (s1)"
    ok, detail = G.check_value({"checks": {"numbers": [65]}}, {"messages": [AIMessage(content=text)]})
    assert not ok and "missing 65" in detail


def test_out_of_scope_must_not_delegate():
    case = {"checks": {"no_delegation": True, "any_of": [["cannot", "don't have"]]}}
    good = {"messages": [AIMessage(content="I don't have weather data.")], "tool_events": []}
    bad = {"messages": [AIMessage(content="I cannot say.")],
           "tool_events": [{"tool": "delegate:graph_agent"}]}
    assert G.check_value(case, good)[0] and not G.check_value(case, bad)[0]


def test_summary_reports_pass_k_and_determinism():
    scored = [G.score_case(CASE, [result("65.8 °C"), result("65.8 °C")])]
    s = G.summarize(scored)
    assert s["pass_k"] == 1.0 and s["fact_determinism"] == 1.0 and s["k"] == 2
    assert "pass^2 100%" in G.format_report(scored)
