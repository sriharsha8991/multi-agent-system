"""Typed contracts (L0).

* ``Provenance`` / ``ValidationVerdict`` — stamped onto artifacts and multimodal checks.
* ``TimeSpec`` / ``TimeWindow`` — time as the orchestrator names it, and as code resolves it.
* ``Slot`` — one fact the answer needs (the **information ledger**, doc 10 O1).
* ``PlanStep`` / ``Task`` — which specialist fills which slots, in what order.
* ``Finding`` / ``SpecialistReport`` — what a specialist hands back, keyed to slots.

**Why typed.** Prose was where drift started: padded briefs, windows computed by a model,
reports carrying SQL, answers with numbers nobody measured. With these contracts code can
check, before and after every delegation, that a fact was asked for exactly once, filled
with the fields it needs, consistent with every other fact, and cited by the answer.
Scope limits, real tag names, no code in text and malformed time all bounce as cheap
validation errors instead of costing a specialist run.
"""
from __future__ import annotations

import difflib
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..catalog import column_names, systems


class Provenance(BaseModel):
    """Where a value came from — attached to every artifact for auditability."""

    capability: str
    query: str | None = None
    timing_ms: int | None = None
    row_count: int | None = None


class ValidationVerdict(BaseModel):
    """Verdict from a multimodal check that an artifact actually answers the question."""

    answers_query: bool = Field(description="true if the artifact answers the user's question")
    reason: str = Field(description="one line: what is present or missing")


# ── shared vocabulary ────────────────────────────────────────────────────────────
SystemName = Literal["bfpa", "bfpb", "cepa", "cepb", "turbine"]
AgentName = Literal["graph_agent", "sql_agent", "coder_agent"]
SlotKind = Literal["lookup", "measure", "derive"]
Aggregation = Literal[
    "value", "count", "sum", "max", "min", "avg", "stddev", "latest", "list", "rank",
    "series", "duration_above", "compare", "correlation", "regression", "cluster", "anomaly",
    "trend", "distribution", "figure", "analysis",
]
Need = Literal["value", "unit", "time", "entity", "list", "figure"]

#: SQL, Cypher or Python in a plan or brief means the orchestrator is writing queries for a
#: specialist that knows the schema better than it does.
CODE_PATTERN = re.compile(
    r"\bSELECT\b[^;]{0,400}?\bFROM\b|\bMATCH\s*\(|^\s*import\s+\w+|\bdatetime\(", re.M)

#: A reference to an earlier step's output, resolved in code: ``$s1.alert_id``.
REF_PATTERN = re.compile(r"^\$(s\d{1,2})\.(alert_id|alert_ids|work_order_id|work_order_ids|"
                         r"tags|artifacts)$")


def _reject_code(text: str, field: str) -> str:
    if CODE_PATTERN.search(text):
        raise ValueError(f"{field} contains code; describe the goal and let the specialist "
                         "write the query")
    return text


def _blank_to_none(data):
    """Gemini fills unused optional fields with "" — read those as unset.

    A live run sent ``{"phrase": "last 1 month", "start": "", "around_alert": ""}``, which
    failed the exactly-one rule and cost the orchestrator a turn to resend.
    """
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if not (isinstance(v, str) and not v.strip())}
    return data


def _check_tags(items: list[str], allow_refs: bool) -> list[str]:
    bad: list[str] = []
    for item in items:
        item = item.strip()
        if allow_refs and REF_PATTERN.match(item):
            continue
        system, _, tag = item.partition(".")
        if system not in systems() or tag not in column_names(system)[1:]:
            pool = column_names(system)[1:] if system in systems() else []
            near = difflib.get_close_matches(tag, pool, n=3)
            bad.append(item + (f" (did you mean {', '.join(near)}?)" if near else ""))
    if bad:
        raise ValueError("unknown tags: " + "; ".join(bad)
                         + ". Use 'system.tag_name' as reported, or name a concept instead.")
    return [i.strip() for i in items]


# ── time ─────────────────────────────────────────────────────────────────────────
class TimeSpec(BaseModel):
    """Name the time — code resolves it. Set exactly one of: phrase, start+end, around_alert."""

    model_config = ConfigDict(extra="forbid")

    phrase: str | None = Field(
        None, description="relative phrase, verbatim: 'yesterday', 'today', 'last week', "
                          "'last N hours', 'last N days', 'last N weeks', 'last N months'")
    start: datetime | None = Field(
        None, description="explicit ISO start (inclusive) — only a date/time the user wrote "
                          "or a report gave; needs end")
    end: datetime | None = Field(None, description="explicit ISO end (exclusive); needs start")
    around_alert: str | None = Field(
        None, description="an alert_id, or '$sN.alert_id' for the alert an earlier step found; "
                          "code pads that alert's start/end by a fixed margin")

    @model_validator(mode="before")
    @classmethod
    def _blanks(cls, data):
        return _blank_to_none(data)

    @model_validator(mode="after")
    def _exactly_one(self) -> TimeSpec:
        kinds = [self.phrase is not None,
                 self.start is not None or self.end is not None,
                 self.around_alert is not None]
        if sum(kinds) != 1:
            raise ValueError("set exactly one of: phrase, start+end, around_alert")
        if (self.start is None) != (self.end is None):
            raise ValueError("an explicit range needs both start and end")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("start must be before end")
        return self


class TimeWindow(BaseModel):
    """A resolved ``[start, end)`` window. Produced by code, never by a model."""

    start: datetime
    end: datetime
    label: str
    source: Literal["phrase", "explicit", "alert"]
    clamped: bool = False

    def render(self) -> str:
        note = " (clamped to telemetry coverage)" if self.clamped else ""
        return f"[{self.start.isoformat()}, {self.end.isoformat()})  {self.label}{note}"

    def key(self) -> str:
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


# ── the information ledger ───────────────────────────────────────────────────────
class Slot(BaseModel):
    """One fact the final answer needs. Written once per question in ``set_plan``."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str = Field(pattern=r"^f\d{1,2}$", description="'f1', 'f2', ...")
    kind: SlotKind = Field(description="lookup: graph facts (tags, alerts, work orders, parts, "
                                       "costs) · measure: sensor values · derive: statistics or "
                                       "figures computed from fetched data")
    ask: str = Field(max_length=160, description="the fact in plain words, e.g. 'maximum "
                                                 "bearing temperature and when it occurred'")
    systems: list[SystemName] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list,
                                description="glossary concepts to measure, e.g. ['bearing "
                                            "temperature'] — for measure/derive slots")
    tags: list[str] = Field(default_factory=list,
                            description="exact 'system.tag_name' pairs, or '$sN.tags' — only "
                                        "when known")
    aggregation: Aggregation
    needs: list[Need] = Field(min_length=1, description="fields the finding must carry: value, "
                                                        "unit, time, entity, list, figure")
    time: TimeSpec | None = Field(
        None, description="ONLY when the user's question names a time or an event defines one. "
                          "No time in the question → omit: the fact covers all data.")
    threshold: float | Literal["alarm_hi", "alarm_hihi"] | None = Field(
        None, description="for duration_above: a number or 'alarm_hi' / 'alarm_hihi'")

    @model_validator(mode="before")
    @classmethod
    def _blanks(cls, data):
        return _blank_to_none(data)

    @field_validator("time", mode="before")
    @classmethod
    def _empty_time_is_none(cls, v):
        if isinstance(v, dict) and not _blank_to_none(v):
            return None
        return v

    @field_validator("ask")
    @classmethod
    def _no_code(cls, v: str) -> str:
        return _reject_code(v, "ask")

    @field_validator("tags")
    @classmethod
    def _real_tags(cls, items: list[str]) -> list[str]:
        return _check_tags(items, allow_refs=True)

    @model_validator(mode="after")
    def _coherent(self) -> Slot:
        for item in self.tags:
            system = item.partition(".")[0]
            if not item.startswith("$") and system not in self.systems:
                self.systems.append(system)  # type: ignore[arg-type]
        if self.kind in ("measure", "derive") and not (self.concepts or self.tags):
            raise ValueError(f"{self.slot_id}: a {self.kind} slot needs concepts or tags")
        if "figure" in self.needs and self.kind != "derive":
            raise ValueError(f"{self.slot_id}: only a derive slot can need a figure")
        if self.aggregation == "duration_above" and self.threshold is None:
            raise ValueError(f"{self.slot_id}: duration_above needs a threshold")
        return self


class PlanStep(BaseModel):
    """One delegation in the plan. Status, facts and artifacts are kept by code."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(pattern=r"^s\d{1,2}$", description="'s1', 's2', ... in execution order")
    agent: AgentName
    slots: list[str] = Field(min_length=1, description="slot ids this step fills")
    depends_on: list[str] = Field(default_factory=list,
                                  description="step ids whose results this step needs")


class Task(BaseModel):
    """One delegation: which planned slots to fill now. Code builds the brief from the slots."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(pattern=r"^s\d{1,2}$", description="the plan step this fulfils")
    slots: list[str] = Field(min_length=1, max_length=4, description="slot ids to fill")
    inputs: list[str] = Field(default_factory=list,
                              description="artifact ids, or '$sN.artifacts', holding data "
                                          "this step needs")
    note: str | None = Field(None, max_length=200,
                             description="optional clarification; never a query")

    @model_validator(mode="before")
    @classmethod
    def _blanks(cls, data):
        return _blank_to_none(data)

    @field_validator("note")
    @classmethod
    def _no_code(cls, v: str | None) -> str | None:
        return None if v is None else _reject_code(v, "note")


# ── what specialists hand back ───────────────────────────────────────────────────
class Finding(BaseModel):
    """One fact, keyed to the slot it fills. Numbers go in ``value``, never only in text."""

    slot_id: str = Field(description="the slot id this finding fills")
    statement: str = Field(max_length=400, description="the fact with its context: what, where, "
                                                   "when, and how it compares to the setpoints")
    entity: str | None = Field(None, description="what it is about: 'bfpa', "
                                                 "'bfpa.bearing_temp_8', 'ALM-BFPA-0009', ...")
    attribute: str | None = Field(None, description="'max', 'avg', 'count', 'total_item_cost', "
                                                    "'peak_value', 'minutes_above', ...")
    value: float | None = Field(None, description="the number, if the fact is numeric")
    unit: str | None = None
    time: str | None = Field(None, description="ISO timestamp of the event (e.g. when the max "
                                               "occurred), if the slot needs time")
    items: list[str] | None = Field(None, description="for list/rank facts: the items, in order; "
                                                      "[] means none were found")
    artifact_id: str | None = None


class Handoff(BaseModel):
    tags: list[str] = Field(default_factory=list, description="'system.tag_name' for later steps")
    alert_ids: list[str] = Field(default_factory=list)
    work_order_ids: list[str] = Field(default_factory=list)


class SpecialistReport(BaseModel):
    """A specialist's final message. Only this crosses back to the orchestrator."""

    status: Literal["done", "partial", "failed"]
    answer: str = Field(max_length=1500, description="what you found and what stands out — the key "
                                                 "numbers, how they were computed, patterns or "
                                                 "anomalies worth the orchestrator's attention, "
                                                 "and the figures drawn; no queries, no code")
    findings: list[Finding] = Field(default_factory=list)
    handoff: Handoff = Field(default_factory=Handoff)
    artifacts: list[str] = Field(default_factory=list,
                                 description="artifact ids produced that back the findings")
    gaps: list[str] = Field(default_factory=list,
                            description="anything asked for but not delivered, with why")


# ── plan validation ──────────────────────────────────────────────────────────────
#: Words that mean the user named a time. Without any of them, a slot may not add one — a
#: traced orchestrator added 'last 24 months' to "how many turbine work orders" and silently
#: dropped a record (doc 10, O5 R3).
TIME_WORDS = re.compile(
    r"\b(yesterday|today|tonight|last|past|recent|recently|since|between|during|before|after|"
    r"week|weeks|month|months|day|days|hour|hours|year|years|minute|minutes|morning|evening|"
    r"weekly|daily|hourly|monthly|\d{4}-\d{2}-\d{2}|"
    r"january|february|march|april|june|july|august|september|october|november|december)\b",
    re.I)


def validate_plan(slots: list[Slot], steps: list[PlanStep], existing_slots: dict[str, dict],
                  existing_steps: dict[str, dict], question: str) -> list[str]:
    """Structural problems with a proposed ledger and plan ([] == acceptable).

    Capability, concept and time-scope checks that need the registry or the glossary live in
    ``orchestrator.ledger.plan_problems``; this covers the contract itself.
    """
    problems: list[str] = []
    slot_ids = [s.slot_id for s in slots]
    for sid in {x for x in slot_ids if slot_ids.count(x) > 1}:
        problems.append(f"duplicate slot_id {sid}")
    known_slots = set(slot_ids) | set(existing_slots)

    for s in slots:
        prior = existing_slots.get(s.slot_id)
        if prior and prior.get("status") == "filled":
            same = {k: prior.get(k) for k in ("kind", "aggregation", "concepts", "systems")} == \
                   {"kind": s.kind, "aggregation": s.aggregation, "concepts": s.concepts,
                    "systems": s.systems}
            if not same:
                problems.append(f"{s.slot_id} is already filled; add a new slot instead of "
                                "changing it")
        if s.time is not None and s.time.around_alert is None and not TIME_WORDS.search(question):
            problems.append(f"{s.slot_id} adds a time window, but the question names no time — "
                            "omit `time` so the fact covers all data")

    seen_steps: set[str] = set()
    assigned: set[str] = set()
    for st in steps:
        if st.step_id in seen_steps:
            problems.append(f"duplicate step_id {st.step_id}")
        unknown = [x for x in st.slots if x not in known_slots]
        if unknown:
            problems.append(f"{st.step_id} fills unknown slots {unknown}")
        bad_deps = [d for d in st.depends_on if d not in seen_steps and d not in existing_steps]
        if bad_deps:
            problems.append(f"{st.step_id} depends on {bad_deps}, which are not earlier steps")
        prior = existing_steps.get(st.step_id)
        if prior and prior.get("status") == "done" and (
                prior.get("agent") != st.agent or sorted(prior.get("slots") or []) != sorted(st.slots)):
            problems.append(f"{st.step_id} is already done; add a new step instead of changing it")
        assigned.update(st.slots)
        seen_steps.add(st.step_id)

    already_assigned = {x for v in existing_steps.values() for x in (v.get("slots") or [])}
    orphan = [s.slot_id for s in slots if s.slot_id not in assigned | already_assigned]
    if orphan:
        problems.append(f"slots {orphan} are not filled by any step")

    by_step = {st.step_id: st for st in steps}
    for st in steps:
        for sid in st.slots:
            slot = next((s for s in slots if s.slot_id == sid), None)
            if slot is None:
                continue
            refs = [x for x in slot.tags if x.startswith("$")]
            if slot.time and slot.time.around_alert and slot.time.around_alert.startswith("$"):
                refs.append(slot.time.around_alert)
            for ref in refs:
                m = REF_PATTERN.match(ref)
                if not m:
                    problems.append(f"{sid}: bad reference {ref!r} (use $sN.alert_id, $sN.tags, "
                                    "$sN.artifacts, $sN.work_order_id)")
                elif m.group(1) not in st.depends_on:
                    problems.append(f"{st.step_id} uses {ref} but does not depend on {m.group(1)}")
                elif m.group(1) not in by_step and m.group(1) not in existing_steps:
                    problems.append(f"{ref} points at an unknown step")
    return problems
