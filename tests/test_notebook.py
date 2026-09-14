"""Notebook helpers read a finished run's state; no model is called."""
from __future__ import annotations

from langchain_core.messages import AIMessage

from mas.notebook import figures_of, run_summary, show_tool_calls


def _result():
    return {
        "messages": [AIMessage(content="answer", usage_metadata={"input_tokens": 100, "output_tokens": 10,
                                                                  "total_tokens": 110})],
        "blackboard": {"t1": {"kind": "table", "row_count": 5}, "f2": {"kind": "figure", "caption": "BFP-A plot",
                                                                         "path": "outputs/figures/f2_bfp-a-plot.png"}},
        "tool_events": [
            {"tool": "delegate:sql_agent", "step_id": "s1", "slots": ["f1"], "ms": 1000, "status": "done",
             "model_calls": 2, "input_tokens": 400, "output_tokens": 40, "inner_calls": 2},
            {"tool": "sql_query", "agent": "sql_agent", "ms": 50, "error": "unknown column", "sql": "SELECT x FROM bfpa"},
            {"tool": "sql_query", "agent": "sql_agent", "ms": 60, "rows": 5, "artifact_id": "t1", "sql": "SELECT 1"},
            {"tool": "delegate:coder_agent", "step_id": "s2", "slots": ["f2"], "error": "rejected: needs inputs"},
        ],
    }


def test_run_summary_counts_calls_tokens_and_figures():
    s = run_summary(_result())
    assert s["delegations"] == 2 and s["rejected_delegations"] == 1
    assert s["tool_calls"] == 2 and s["failed_tool_calls"] == 1
    assert s["input_tokens"] == 500 and s["output_tokens"] == 50 and s["figures"] == 1


def test_figures_and_tool_calls_render_from_state(capsys):
    assert figures_of(_result()) == [{"artifact_id": "f2", "title": "BFP-A plot",
                                      "path": "outputs/figures/f2_bfp-a-plot.png"}]
    show_tool_calls(_result())
    out = capsys.readouterr().out
    assert "s1 · sql_agent → **done**" in out and "```sql\nSELECT x FROM bfpa\n```" in out
    assert "unknown column" in out and "REJECTED" in out
