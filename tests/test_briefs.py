"""Brief building: references, windows, glossary tags, fingerprints, rendering — in code.

DB-free: telemetry coverage and alert bounds are stubbed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from langchain_core.messages import HumanMessage

from mas.execution import timewin
from mas.llm.schemas import Slot, Task
from mas.orchestrator import briefs, ledger

UTC = timezone.utc
COVERAGE = ("2026-08-08T00:00:00+00:00", "2026-09-07T00:00:00+00:00")


@pytest.fixture(autouse=True)
def _stubs(monkeypatch):
    monkeypatch.setattr(timewin, "data_bounds", lambda: COVERAGE)
    monkeypatch.setattr(briefs, "data_bounds", lambda: COVERAGE)
    monkeypatch.setattr(timewin, "_alert_bounds", lambda _id: (
        datetime(2026, 9, 3, 2, 26, tzinfo=UTC), datetime(2026, 9, 3, 23, 59, tzinfo=UTC)))


def _state(slots: list[Slot], steps: dict, question: str, blackboard=None) -> dict:
    return {"messages": [HumanMessage(content=question)],
            "slots": {s.slot_id: ledger.slot_record(s) for s in slots},
            "plan": steps, "blackboard": blackboard or {}, "rounds": {}, "facts": {}}


def test_measure_brief_has_linked_tags_and_resolved_window_but_no_prewritten_query():
    s = Slot(slot_id="f1", kind="measure", ask="max bearing temperature and when", systems=["bfpa"],
             concepts=["bearing temperature"], aggregation="max", needs=["value", "time"],
             time={"phrase": "yesterday"})
    st = _state([s], {"s1": {"agent": "sql_agent", "slots": ["f1"], "depends_on": []}},
                "max bearing temperature on BFP-A yesterday")
    p = briefs.prepare(Task(step_id="s1", slots=["f1"]), "sql_agent", st)
    assert p.problems == []
    assert len(p.linked["f1"]) == 14
    assert "window: [2026-09-06T00:00:00+00:00, 2026-09-07T00:00:00+00:00)" in p.brief
    assert p.brief.count("alarm_hihi 100") == 1          # shared setpoints collapse to one line
    assert "recipe" not in p.brief.lower()               # the specialist writes its own query
    assert "the finding must carry: value, time" in p.brief


def test_references_resolve_to_what_earlier_steps_handed_over():
    f2 = Slot(slot_id="f2", kind="measure", ask="series in the alert window", systems=["bfpa"],
              tags=["$s1.tags"], aggregation="series", needs=["entity"],
              time={"around_alert": "$s1.alert_id"})
    steps = {"s1": {"agent": "graph_agent", "slots": ["f1"], "status": "done", "artifacts": ["g1"],
                    "handoff": {"alert_ids": ["ALM-BFPA-0009"], "tags": ["bfpa.bearing_temp_1"]}},
             "s2": {"agent": "sql_agent", "slots": ["f2"], "depends_on": ["s1"]}}
    st = _state([f2], steps, "latest alert on BFP-A and plot the bearing temperature during that alert window")
    p = briefs.prepare(Task(step_id="s2", slots=["f2"]), "sql_agent", st)
    assert p.problems == []
    assert p.linked["f2"] == ["bfpa.bearing_temp_1"]
    assert "ALM-BFPA-0009 ± 2 h" in p.brief
    assert "2026-09-03T00:26:00+00:00" in p.brief


def test_coder_brief_needs_inputs_and_uses_no_default_window():
    f3 = Slot(slot_id="f3", kind="derive", ask="plot with thresholds", systems=["bfpa"],
              tags=["bfpa.bearing_temp_1"], aggregation="figure", needs=["figure"])
    steps = {"s2": {"agent": "sql_agent", "slots": ["f2"], "status": "done", "artifacts": ["t4"]},
             "s3": {"agent": "coder_agent", "slots": ["f3"], "depends_on": ["s2"]}}
    st = _state([f3], steps, "plot it", blackboard={"t4": {"kind": "table", "row_count": 10}})
    assert any("needs `inputs`" in p for p in briefs.prepare(Task(step_id="s3", slots=["f3"]),
                                                             "coder_agent", st).problems)
    p = briefs.prepare(Task(step_id="s3", slots=["f3"], inputs=["$s2.artifacts"]), "coder_agent", st)
    assert p.problems == [] and p.inputs == ["t4"]
    assert "window:" not in p.brief and "t4: table, 10 rows" in p.brief


def test_same_plan_gives_the_same_brief_and_fingerprint():
    s = Slot(slot_id="f1", kind="measure", ask="average bearing temperature", systems=["bfpa", "bfpb"],
             concepts=["bearing temperature"], aggregation="avg", needs=["value"],
             time={"phrase": "last 7 days"})
    steps = {"s1": {"agent": "sql_agent", "slots": ["f1"], "depends_on": []}}
    a = briefs.prepare(Task(step_id="s1", slots=["f1"]), "sql_agent", _state([s], steps, "last 7 days"))
    b = briefs.prepare(Task(step_id="s1", slots=["f1"]), "sql_agent", _state([s], steps, "last 7 days"))
    assert a.brief == b.brief and a.fingerprint == b.fingerprint


def test_brief_only_fields_never_reach_state():
    s = Slot(slot_id="f1", kind="measure", ask="max", systems=["bfpa"], concepts=["bearing temperature"],
             aggregation="max", needs=["value"])
    st = _state([s], {"s1": {"agent": "sql_agent", "slots": ["f1"], "depends_on": []}}, "max bearing temp")
    briefs.prepare(Task(step_id="s1", slots=["f1"]), "sql_agent", st)
    assert "_tag_specs" not in st["slots"]["f1"] and "_link_note" not in st["slots"]["f1"]
