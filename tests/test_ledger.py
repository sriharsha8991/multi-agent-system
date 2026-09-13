"""The information ledger and its strict, code-only progress checks.

Each test mirrors a failure seen in traces or in ``experiments/progress_ledger``: reworded
repeats, contradictions between reports, a report that omits a requested field, confident
text over no artifacts, stalls, invented numbers and units in the final answer.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from mas.llm.schemas import Finding, Handoff, PlanStep, Slot, SpecialistReport
from mas.orchestrator import ledger

Q = "What was the maximum bearing temperature on BFP-A yesterday, and when?"


def slot(**over) -> Slot:
    base = {"slot_id": "f1", "kind": "measure", "ask": "max bearing temperature and when",
            "systems": ["bfpa"], "concepts": ["bearing temperature"], "aggregation": "max",
            "needs": ["value", "time", "entity"], "time": {"phrase": "yesterday"}}
    return Slot(**{**base, **over})


def state_with(slots=None, steps=None, facts=None, rounds=None, question=Q, **extra) -> dict:
    return {"messages": [HumanMessage(content=question)],
            "slots": {s.slot_id: ledger.slot_record(s) for s in (slots or [slot()])},
            "plan": steps if steps is not None else {"s1": {"agent": "sql_agent", "slots": ["f1"],
                                                            "depends_on": []}},
            "facts": facts or {}, "rounds": rounds or {}, **extra}


# ── plan validation ───────────────────────────────────────────────────────────
def test_plan_checks_capability_and_concepts():
    st = state_with(slots=[], steps={})
    problems = ledger.plan_problems(
        [slot(), slot(slot_id="f2", concepts=["eccentricity"], systems=["cepa"])],
        [PlanStep(step_id="s1", agent="graph_agent", slots=["f1"]),
         PlanStep(step_id="s2", agent="sql_agent", slots=["f2"])], st)
    assert any("graph_agent does not fill measure slots" in p for p in problems)
    assert any("'eccentricity' has no tags on cepa" in p for p in problems)


def test_coder_step_must_depend_on_a_data_step():
    derive = slot(slot_id="f2", kind="derive", aggregation="figure", needs=["figure"], time=None)
    problems = ledger.plan_problems([slot(), derive],
                                    [PlanStep(step_id="s1", agent="sql_agent", slots=["f1"]),
                                     PlanStep(step_id="s2", agent="coder_agent", slots=["f2"])],
                                    state_with(slots=[], steps={}))
    assert any("works on fetched data" in p for p in problems)


def test_same_turn_set_plan_is_read_from_the_pending_call():
    call = {"name": "set_plan", "id": "c1", "args": {
        "slots": [slot().model_dump(mode="json")],
        "steps": [{"step_id": "s1", "agent": "sql_agent", "slots": ["f1"]}]}}
    st = {"messages": [HumanMessage(content=Q), AIMessage(content="", tool_calls=[call])]}
    slots, steps = ledger.effective_ledger(st)
    assert "f1" in slots and steps["s1"]["agent"] == "sql_agent"


# ── pre-run refusals ──────────────────────────────────────────────────────────
def test_no_plan_is_refused():
    assert "no plan" in ledger.pre_run_problems({}, {}, {}, "s1", "sql_agent", ["f1"], None)[0]


def test_refusals_for_wrong_agent_filled_slot_blocked_slot_and_unmet_dependency():
    st = state_with()
    slots = dict(st["slots"])
    slots["f1"] = {**slots["f1"], "status": "filled", "facts": ["s0.1"]}
    steps = {"s1": {"agent": "sql_agent", "slots": ["f1"], "depends_on": ["s0"]},
             "s0": {"agent": "graph_agent", "slots": [], "status": "pending"}}
    problems = " | ".join(ledger.pre_run_problems(st, slots, steps, "s1", "graph_agent", ["f1"], None))
    assert "planned for sql_agent" in problems
    assert "already filled" in problems
    assert "have not finished" in problems
    slots["f1"]["status"] = "blocked"
    assert "blocked" in " ".join(ledger.pre_run_problems(st, slots, steps, "s1", "sql_agent", ["f1"], None))


def test_reworded_repeat_is_the_same_fingerprint():
    """E1: the same data request in different words must not run twice."""
    a = slot(ask="average bearing temperature on both pumps")
    b = slot(ask="which pump's bearings ran hotter on average")
    tags = ["bfpa.bearing_temp_1", "bfpa.bearing_temp_2"]
    sig_a = ledger.slot_signature(ledger.slot_record(a), "w", tags)
    sig_b = ledger.slot_signature(ledger.slot_record(b), "w", tags)
    assert ledger.fingerprint("sql_agent", [sig_a], [], None) == ledger.fingerprint("sql_agent", [sig_b], [], None)
    # a retry that says what was missing is a different task
    assert ledger.fingerprint("sql_agent", [sig_a], [], "include the time") != \
        ledger.fingerprint("sql_agent", [sig_a], [], None)
    # a different aggregation on the same tags is a different task (no false loop)
    sig_c = ledger.slot_signature(ledger.slot_record(slot(aggregation="series", needs=["entity"])), "w", tags)
    assert ledger.fingerprint("sql_agent", [sig_c], [], None) != ledger.fingerprint("sql_agent", [sig_a], [], None)


def test_identical_task_with_facts_or_two_failures_is_refused():
    st = state_with(rounds={"r:1": {"kind": "delegation", "at": "1", "fingerprint": "abc",
                                    "new_slots": ["f1"], "facts": 1}})
    slots, steps = ledger.effective_ledger(st)
    assert any("already ran and returned facts" in p
               for p in ledger.pre_run_problems(st, slots, steps, "s1", "sql_agent", ["f1"], "abc"))
    failing = {f"r:{i}": {"kind": "delegation", "at": str(i), "fingerprint": "xyz",
                          "status": "failed", "error": "boom", "new_slots": []} for i in (1, 2)}
    st = state_with(rounds=failing)
    assert any("failed 2 times" in p
               for p in ledger.pre_run_problems(st, slots, steps, "s1", "sql_agent", ["f1"], "xyz"))


def test_stall_blocks_delegation_until_replan():
    rounds = {"r:1": {"kind": "delegation", "at": "1", "new_slots": []},
              "r:2": {"kind": "delegation", "at": "2", "new_slots": []}}
    st = state_with(rounds=rounds)
    slots, steps = ledger.effective_ledger(st)
    assert any("STALLED" in p for p in ledger.pre_run_problems(st, slots, steps, "s1", "sql_agent", ["f1"], "n"))
    rounds["p:3"] = {"kind": "replan", "at": "3"}
    assert ledger.stall_count(ledger.ordered_rounds({"rounds": rounds})) == 0


def test_references_resolve_from_finished_steps_only():
    steps = {"s1": {"status": "done", "handoff": {"alert_ids": ["ALM-BFPA-0009"], "tags": ["bfpa.bearing_temp_1"]},
                    "artifacts": ["g1"]},
             "s2": {"status": "pending"}}
    assert ledger.resolve_ref("$s1.alert_id", steps) == ["ALM-BFPA-0009"]
    assert ledger.resolve_ref("$s1.artifacts", steps) == ["g1"]
    for ref in ("$s2.tags", "$s1.work_order_id"):
        try:
            ledger.resolve_ref(ref, steps)
            raise AssertionError(ref)
        except ValueError:
            pass


def test_derive_slots_use_the_primary_tag_per_concept():
    rec = ledger.slot_record(slot(kind="derive", aggregation="cluster", needs=["value"],
                                  concepts=["load", "efficiency", "vibration"], time=None))
    tags, _ = ledger.linked_tags(rec, {})
    assert [t.tag_name for t in tags] == ["motor_power", "pump_efficiency", "vibration_overall"]


# ── post-run validation ───────────────────────────────────────────────────────
def _apply(report, st=None, created=("t1",), blackboard=None, exhausted=False):
    st = st or state_with()
    slots, steps = ledger.effective_ledger(st)
    return ledger.apply_report(
        st, slots, steps, step_id="s1", agent="sql_agent", task_slots=["f1"],
        windows={"f1": "2026-09-06/2026-09-07"}, linked={"f1": ["bfpa.bearing_temp_8"]},
        report=report, created=list(created), blackboard=blackboard or {"t1": {"kind": "table"}},
        exhausted=exhausted, fp="fp1", round_key="r:1")


def test_complete_finding_fills_the_slot():
    report = SpecialistReport(status="done", answer="65.8 degC", findings=[Finding(
        slot_id="f1", statement="max 65.8", entity="bfpa.bearing_temp_8", attribute="max", value=65.8,
        unit="°C", time="2026-09-06T12:51:00+00:00", artifact_id="t1")])
    update, notes, status = _apply(report)
    assert status == "done" and update["slots"]["f1"]["status"] == "filled"
    assert update["rounds"]["r:1"]["new_slots"] == ["f1"]
    assert not notes  # °C is the catalog's degC


def test_missing_required_field_leaves_the_slot_partial():
    """E4: 'GAPS: none' but the time the user asked for is missing."""
    report = SpecialistReport(status="done", answer="65.8", findings=[Finding(
        slot_id="f1", statement="max 65.8", entity="bfpa.bearing_temp_8", attribute="max", value=65.8)])
    update, notes, status = _apply(report)
    assert update["slots"]["f1"]["status"] == "partial" and update["slots"]["f1"]["missing"] == ["time"]
    assert status == "partial" and any("lacks required time" in n for n in notes)


def test_confident_text_with_no_findings_is_not_progress():
    """C6: 'All deliverables delivered successfully' over a budget stop and no artifacts."""
    report = SpecialistReport(status="done", answer="All deliverables delivered successfully.")
    update, _, status = _apply(report, created=(), exhausted=True)
    assert update["slots"]["f1"]["status"] == "pending" and status == "partial"
    assert update["rounds"]["r:1"]["new_slots"] == []


def test_wrong_slot_fake_artifact_and_wrong_unit_are_corrected():
    report = SpecialistReport(status="done", answer="x", findings=[
        Finding(slot_id="f9", statement="stray"),
        Finding(slot_id="f1", statement="flow", entity="bfpa.flow_rate", attribute="max", value=267.2,
                unit="m3/h", time="2026-09-06T01:00:00+00:00", artifact_id="t99")])
    update, notes, _ = _apply(report)
    fact = next(iter(update["facts"].values()))
    assert fact["unit"] == "t/h" and fact["artifact_id"] is None
    assert any("f9" in n for n in notes) and any("t99" in n for n in notes) and any("t/h" in n for n in notes)


def test_contradiction_between_reports_marks_conflict():
    """E5: 115.7 um from one step, 98.4 um from another, same entity/attribute/window."""
    earlier = {"s0.1": {"key": "s0.1", "slot_id": "f0", "step_id": "s0", "entity": "turbine.eccentricity",
                        "entity_norm": "turbine.eccentricity", "attribute": "max", "attribute_norm": "max",
                        "value": 115.7, "window": "2026-09-06/2026-09-07"}}
    st = state_with(facts=earlier)
    report = SpecialistReport(status="done", answer="98.4", findings=[Finding(
        slot_id="f1", statement="peak 98.4", entity="turbine.eccentricity", attribute="peak", value=98.4,
        unit="um", time="2026-09-06T07:10:00+00:00", artifact_id="t1")])
    update, notes, _ = _apply(report, st=st)
    assert update["slots"]["f1"]["status"] == "conflict" and update["slots"]["f0"]["status"] == "conflict"
    assert any("CONFLICT" in n for n in notes)


def test_a_slot_unfilled_twice_is_blocked():
    st = state_with()
    st["slots"]["f1"]["attempts_failed"] = 1
    update, _, _ = _apply(SpecialistReport(status="failed", answer="nothing"), st=st, created=())
    assert update["slots"]["f1"]["status"] == "blocked"


def test_empty_list_is_an_answer():
    """E3: 'no maintenance followed' is a finding, not a failure."""
    st = state_with(slots=[slot(kind="lookup", concepts=[], aggregation="list", needs=["list"], time=None)],
                    steps={"s1": {"agent": "graph_agent", "slots": ["f1"]}})
    slots, steps = ledger.effective_ledger(st)
    update, _, status = ledger.apply_report(
        st, slots, steps, step_id="s1", agent="graph_agent", task_slots=["f1"], windows={}, linked={},
        report=SpecialistReport(status="done", answer="none", findings=[
            Finding(slot_id="f1", statement="no work orders followed", items=[])],
            handoff=Handoff()), created=["g1"], blackboard={"g1": {"kind": "records"}},
        exhausted=False, fp="x", round_key="r:1")
    assert status == "done" and update["slots"]["f1"]["status"] == "filled"


# ── final answer ──────────────────────────────────────────────────────────────
def _answer_state():
    st = state_with()
    st["slots"]["f1"].update(status="filled", facts=["s1.1"], linked_tags=["bfpa.bearing_temp_8"])
    st["facts"] = {"s1.1": {"key": "s1.1", "slot_id": "f1", "step_id": "s1", "entity": "bfpa.bearing_temp_8",
                            "attribute": "max", "value": 65.8, "unit": "degC", "artifact_id": "t1",
                            "statement": "max 65.8 degC"}}
    return st


def test_supported_numbers_and_arithmetic_pass():
    text = ("The maximum was 65.8 °C on bearing_temp_8 at 12:51 UTC, 24.2 °C below alarm_hi (90 °C) "
            "and 34.2 °C below the trip setpoint of 100 °C.")
    assert ledger.answer_problems(text, _answer_state()) == []


def test_invented_numbers_and_wrong_units_are_flagged():
    text = "The maximum was 67.2 °C; running time was 60.86%; flow peaked at 65.8 m3/h."
    problems = " | ".join(ledger.answer_problems(text, _answer_state()))
    assert "67.2 °C" in problems and "60.86%" in problems
    assert "65.8 m3/h" in problems


def test_footers_list_evidence_and_gaps():
    st = _answer_state()
    st["slots"]["f2"] = {**ledger.slot_record(slot(slot_id="f2", ask="the figure")), "status": "blocked"}
    text = ledger.footers(st)
    assert "**Evidence:** f1 ← t1 (s1)" in text
    assert "**Gaps:** f2 (the figure) — blocked" in text
