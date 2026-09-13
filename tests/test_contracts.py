"""Typed contracts: slots, tasks, plans, reports, and code-resolved time.

DB-free: alert lookups and telemetry coverage are stubbed.
"""
from __future__ import annotations

import typing
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mas.catalog import systems
from mas.execution import timewin
from mas.llm.schemas import (PlanStep, Slot, SpecialistReport, SystemName, Task, TimeSpec,
                             validate_plan)

UTC = timezone.utc
COVERAGE = ("2026-08-08T00:00:00+00:00", "2026-09-07T00:00:00+00:00")


@pytest.fixture(autouse=True)
def _coverage(monkeypatch):
    monkeypatch.setattr(timewin, "data_bounds", lambda: COVERAGE)


def slot(**over) -> Slot:
    base = {"slot_id": "f1", "kind": "measure", "ask": "max bearing temperature",
            "systems": ["bfpa"], "concepts": ["bearing temperature"], "aggregation": "max",
            "needs": ["value", "time"]}
    return Slot(**{**base, **over})


def test_system_literal_matches_catalog():
    assert set(typing.get_args(SystemName)) == set(systems())


# ── time ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("fields", [
    {},
    {"phrase": "yesterday", "around_alert": "ALM-1"},
    {"start": datetime(2026, 9, 1, tzinfo=UTC)},
    {"start": datetime(2026, 9, 2, tzinfo=UTC), "end": datetime(2026, 9, 1, tzinfo=UTC)},
    {"phrase": "yesterday", "pad_hours": 1},        # padding is fixed in code, not chosen
])
def test_timespec_needs_exactly_one_well_formed_kind(fields):
    with pytest.raises(ValidationError):
        TimeSpec(**fields)


def test_blank_filler_fields_read_as_unset():
    """The exact filler a live Gemini run sent — it bounced and cost a turn."""
    s = slot(time={"phrase": "yesterday", "end": "", "around_alert": "", "start": ""})
    assert s.time.phrase == "yesterday"
    assert slot(time={"phrase": "", "start": ""}).time is None


def test_phrase_resolves_against_frozen_anchor():
    w = timewin.resolve_timespec(TimeSpec(phrase="yesterday"), clamp=True)
    assert (w.start, w.end) == (datetime(2026, 9, 6, tzinfo=UTC), datetime(2026, 9, 7, tzinfo=UTC))


def test_graph_history_is_not_clamped_but_telemetry_is():
    spec = TimeSpec(phrase="last 6 months")
    assert timewin.resolve_timespec(spec, clamp=False).start == datetime(2026, 3, 7, tzinfo=UTC)
    telemetry = timewin.resolve_timespec(spec, clamp=True)
    assert telemetry.start == datetime(2026, 8, 8, tzinfo=UTC) and telemetry.clamped


def test_alert_window_uses_the_fixed_pad_every_time():
    bounds = lambda _id: (datetime(2026, 8, 16, 6, 29, tzinfo=UTC),  # noqa: E731
                          datetime(2026, 8, 16, 8, 23, tzinfo=UTC))
    spec = TimeSpec(around_alert="ALM-TURBINE-0001")
    first = timewin.resolve_timespec(spec, clamp=True, alert_bounds=bounds)
    assert first == timewin.resolve_timespec(spec, clamp=True, alert_bounds=bounds)
    assert (first.start, first.end) == (datetime(2026, 8, 16, 4, 29, tzinfo=UTC),
                                        datetime(2026, 8, 16, 10, 23, tzinfo=UTC))


def test_unsupported_phrase_and_uncovered_range_bounce():
    with pytest.raises(ValueError, match="supported"):
        timewin.resolve_timespec(TimeSpec(phrase="since the trip"), clamp=True)
    old = TimeSpec(start=datetime(2025, 1, 1, tzinfo=UTC), end=datetime(2025, 1, 2, tzinfo=UTC))
    with pytest.raises(ValueError, match="outside telemetry coverage"):
        timewin.resolve_timespec(old, clamp=True)


# ── slots ─────────────────────────────────────────────────────────────────────
def test_unknown_tag_is_rejected_with_suggestions():
    with pytest.raises(ValidationError, match="did you mean"):
        slot(concepts=[], tags=["bfpa.bearing_temp_9x"])


def test_references_are_allowed_where_ids_come_from_earlier_steps():
    s = slot(concepts=[], tags=["$s1.tags"], time={"around_alert": "$s1.alert_id"})
    assert s.tags == ["$s1.tags"] and s.time.around_alert == "$s1.alert_id"


@pytest.mark.parametrize("over, match", [
    ({"ask": "run SELECT max(bearing_temp_1) FROM bfpa"}, "contains code"),
    ({"concepts": [], "tags": []}, "needs concepts or tags"),
    ({"needs": ["figure"]}, "only a derive slot"),
    ({"aggregation": "duration_above"}, "needs a threshold"),
])
def test_incoherent_slots_are_rejected(over, match):
    with pytest.raises(ValidationError, match=match):
        slot(**over)


def test_task_is_bounded_and_code_free():
    with pytest.raises(ValidationError):
        Task(step_id="s1", slots=["f1", "f2", "f3", "f4", "f5"])
    with pytest.raises(ValidationError, match="contains code"):
        Task(step_id="s1", slots=["f1"], note="MATCH (a:Alert) RETURN a")


# ── plan contract ─────────────────────────────────────────────────────────────
def _plan(slots, steps, question="max bearing temperature on BFP-A yesterday"):
    return validate_plan(slots, steps, {}, {}, question)


def test_every_slot_needs_a_step_and_dependencies_point_backwards():
    problems = _plan([slot(), slot(slot_id="f2")],
                     [PlanStep(step_id="s1", agent="sql_agent", slots=["f1"], depends_on=["s2"])])
    assert any("not filled by any step" in p for p in problems)
    assert any("not earlier steps" in p for p in problems)


def test_a_time_window_the_question_does_not_name_is_rejected():
    """The 'last 24 months' trap: a no-time question must cover all data."""
    s = slot(kind="lookup", concepts=[], systems=["turbine"], aggregation="count", needs=["value"],
             time={"phrase": "last 24 months"})
    problems = _plan([s], [PlanStep(step_id="s1", agent="graph_agent", slots=["f1"])],
                     question="How many maintenance activities were performed on the Turbine?")
    assert any("names no time" in p for p in problems)
    assert not _plan([s], [PlanStep(step_id="s1", agent="graph_agent", slots=["f1"])],
                     question="How many work orders on the turbine in the last 24 months?")


def test_references_require_a_dependency():
    s = slot(concepts=[], tags=["$s1.tags"])
    problems = _plan([s], [PlanStep(step_id="s2", agent="sql_agent", slots=["f1"])])
    assert any("does not depend on s1" in p for p in problems)


def test_filled_slots_and_done_steps_cannot_be_rewritten():
    existing_slots = {"f1": {"status": "filled", "kind": "measure", "aggregation": "max",
                             "concepts": ["bearing temperature"], "systems": ["bfpa"]}}
    existing_steps = {"s1": {"status": "done", "agent": "sql_agent", "slots": ["f1"]}}
    problems = validate_plan([slot(aggregation="avg")],
                             [PlanStep(step_id="s1", agent="graph_agent", slots=["f1"])],
                             existing_slots, existing_steps, "max bearing temperature yesterday")
    assert any("already filled" in p for p in problems)
    assert any("already done" in p for p in problems)


def test_report_schema_defaults():
    r = SpecialistReport(status="done", answer="ok")
    assert r.findings == [] and r.handoff.alert_ids == [] and r.gaps == []
