"""The information ledger and every code-only progress check (doc 10: O1, O3, O5, O6).

Pure functions over graph state — no model calls, no graph nodes. The orchestrator states
*what* the answer needs (slots) and *who* fills it (steps); everything that can be decided
exactly is decided here, strictly:

Before a delegation runs (``pre_run_problems``)
    the step exists in the plan and goes to its agent · its dependencies are done · its
    slots are not already filled or blocked · the identical task (same agent, slots, tags
    and windows) has not already produced facts or failed twice · the plan is not stalled.

After it returns (``apply_report``)
    findings must name a slot of the task · artifact ids must exist · units must match the
    catalog · each slot's required fields (value/unit/time/entity/list/figure) must be
    present · a value that contradicts an accepted fact for the same entity, attribute and
    window marks both slots ``conflict`` · a slot that stays unfilled twice is ``blocked``.

Before the answer leaves (``answer_problems``)
    every number with a unit must be an accepted fact, a catalog setpoint of a tag in play,
    a number from the question, or simple arithmetic on those; its unit must match.

These rules replaced an LLM progress ledger: an experiment (``experiments/progress_ledger``)
found an LLM judge believed confident text over missing artifacts and missed repeats,
scope changes and contradictions — the cases these checks decide exactly.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage

from ..agents.capabilities import REGISTRY, can_fill
from ..catalog import glossary, systems, tag_map
from ..execution.timewin import EVENT_PAD_HOURS
from ..llm.schemas import REF_PATTERN, PlanStep, Slot, SpecialistReport, validate_plan
from .trace import content_text

#: Consecutive delegations that fill no slot before code refuses further delegation.
STALL_LIMIT = 2
#: A slot still unfilled after this many attempts is blocked.
SLOT_ATTEMPTS = 2
#: Identical failed tasks allowed before code refuses the same task again.
IDENTICAL_FAILURES = 2
MAX_LINKED_TAGS = 60

_ATTR_SYNONYMS = {
    "maximum": "max", "peak": "max", "peak_value": "max", "highest": "max", "max_value": "max",
    "minimum": "min", "lowest": "min", "min_value": "min",
    "average": "avg", "mean": "avg", "avg_value": "avg",
    "number": "count", "total_count": "count", "n": "count",
    "total": "sum",
    "std": "stddev", "standard_deviation": "stddev",
}


# ── state helpers ────────────────────────────────────────────────────────────────
def question_of(state: dict) -> str:
    for m in reversed(state.get("messages") or []):
        if isinstance(m, HumanMessage):
            return content_text(m.content)
    return ""


def same_turn_plan(state: dict) -> tuple[list[Slot], list[PlanStep]] | None:
    """A ``set_plan`` call in the orchestrator's current turn, parsed.

    ``set_plan`` and the first delegation go out in the same turn, so the delegation's
    snapshot of state does not contain the plan yet. Reading the pending call keeps the
    ledger mandatory without costing an extra turn.
    """
    messages = state.get("messages") or []
    last = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last is None:
        return None
    for call in last.tool_calls or []:
        if call.get("name") == "set_plan":
            args = call.get("args") or {}
            try:
                return ([Slot.model_validate(s) for s in args.get("slots") or []],
                        [PlanStep.model_validate(s) for s in args.get("steps") or []])
            except Exception:  # noqa: BLE001 — set_plan itself reports the validation error
                return None
    return None


def slot_record(slot: Slot) -> dict:
    return {**slot.model_dump(mode="json"), "status": "pending", "facts": [], "missing": [],
            "attempts_failed": 0}


def step_record(step: PlanStep) -> dict:
    return {"agent": step.agent, "slots": list(step.slots), "depends_on": list(step.depends_on)}


def effective_ledger(state: dict) -> tuple[dict, dict]:
    """Slots and steps from state, overlaid with a same-turn ``set_plan`` call if present."""
    slots = dict(state.get("slots") or {})
    steps = dict(state.get("plan") or {})
    pending = same_turn_plan(state)
    if pending:
        for s in pending[0]:
            slots.setdefault(s.slot_id, slot_record(s))
        for st in pending[1]:
            steps[st.step_id] = {**step_record(st), **{k: v for k, v in steps.get(st.step_id, {}).items()
                                                        if k in ("status", "answer", "artifacts", "handoff")}}
    return slots, steps


# ── plan validation beyond the contract ──────────────────────────────────────────
def plan_problems(slots: list[Slot], steps: list[PlanStep], state: dict) -> list[str]:
    """Contract, capability and grounding problems with a proposed ledger ([] == accept)."""
    existing_slots = dict(state.get("slots") or {})
    existing_steps = dict(state.get("plan") or {})
    problems = validate_plan(slots, steps, existing_slots, existing_steps, question_of(state))
    by_id = {s.slot_id: s for s in slots}
    for st in steps:
        cap = REGISTRY[st.agent]
        for sid in st.slots:
            slot = by_id.get(sid)
            if slot is None:
                continue
            problems += [f"{st.step_id}/{sid}: {p}" for p in can_fill(st.agent, slot.kind,
                                                                        slot.aggregation)]
            if cap.needs_systems and not (slot.systems or slot.tags):
                problems.append(f"{sid}: a {slot.kind} slot needs systems or tags")
            if cap.links_tags:
                problems += concept_problems(slot)
        if cap.needs_inputs and not st.depends_on and not state.get("blackboard"):
            problems.append(f"{st.step_id}: {st.agent} works on fetched data — make it depend "
                            "on the step that fetches it")
    return problems


def concept_problems(slot: Slot) -> list[str]:
    problems = []
    for concept in slot.concepts:
        for system in slot.systems:
            if glossary.resolve(concept, system).source == "none":
                near = glossary.suggestions(concept)
                problems.append(f"{slot.slot_id}: concept {concept!r} has no tags on {system}"
                                + (f" (known concepts close to it: {', '.join(near)})" if near
                                   else f" (known concepts: {', '.join(glossary.concept_names())})"))
    return problems


# ── references, tags, fingerprints ───────────────────────────────────────────────
def resolve_ref(ref: str, steps: dict) -> list[str]:
    """``$s1.alert_id`` → ['ALM-...']; raises ValueError with the reason when unresolvable."""
    m = REF_PATTERN.match(ref)
    if not m:
        raise ValueError(f"bad reference {ref!r}")
    step_id, field = m.groups()
    step = steps.get(step_id)
    if not step or step.get("status") not in ("done", "partial"):
        raise ValueError(f"{ref}: step {step_id} has not finished")
    handoff = step.get("handoff") or {}
    values = {"alert_id": handoff.get("alert_ids"), "alert_ids": handoff.get("alert_ids"),
              "work_order_id": handoff.get("work_order_ids"),
              "work_order_ids": handoff.get("work_order_ids"),
              "tags": handoff.get("tags"), "artifacts": step.get("artifacts")}[field] or []
    if not values:
        raise ValueError(f"{ref}: step {step_id} handed over no {field}")
    return values[:1] if field in ("alert_id", "work_order_id") else list(values)


def linked_tags(slot: dict, steps: dict) -> tuple[list, str]:
    """Catalog tags a slot is about, and a one-line note on how they were chosen.

    Explicit tags (and ``$sN.tags``) win. Otherwise each concept resolves on each system:
    measure slots use every matching tag, derive slots the concept's primary tag — so a
    clustering question uses the same features on every run.
    """
    names: list[str] = []
    for item in slot.get("tags") or []:
        names += resolve_ref(item, steps) if item.startswith("$") else [item]
    if names:
        specs = []
        for n in dict.fromkeys(names):
            system, _, tag = n.partition(".")
            spec = tag_map(system).get(tag) if system in systems() else None
            if spec is None:
                raise ValueError(f"unknown tag {n}")
            specs.append(spec)
        return specs, "given"
    specs, notes = [], []
    for concept in slot.get("concepts") or []:
        for system in slot.get("systems") or []:
            r = glossary.resolve(concept, system)
            if r.source == "none":
                raise ValueError(f"concept {concept!r} has no tags on {system}")
            chosen = [r.primary] if slot["kind"] == "derive" and r.primary else list(r.tags)
            specs += chosen
            notes.append(f"{concept}@{system}: {len(chosen)} via {r.source}")
    specs = list({(t.system, t.tag_name): t for t in specs}.values())
    if len(specs) > MAX_LINKED_TAGS:
        raise ValueError(f"{slot['slot_id']}: {len(specs)} tags — too many; name a narrower "
                         "concept or explicit tags")
    return specs, "; ".join(notes)


def slot_signature(slot: dict, window_key: str | None, tag_names: list[str]) -> list:
    return [slot["kind"], slot["aggregation"], sorted(slot.get("systems") or []),
            sorted(tag_names), window_key or "", str(slot.get("threshold"))]


def fingerprint(agent: str, signatures: list[list], inputs: list[str], note: str | None) -> str:
    """Identity of a delegation: agent, data touched (slots, tags, windows), inputs, note.

    Wording of the ask is deliberately absent — a reworded repeat of the same data request is
    the same task. The note is present, so a retry that tells the specialist what was missing
    ("include the time of the max") is a different task; a blind identical retry is not.
    """
    raw = json.dumps([agent, sorted(signatures, key=json.dumps), sorted(inputs),
                      (note or "").strip().lower()])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def ordered_rounds(state: dict) -> list[dict]:
    return sorted((state.get("rounds") or {}).values(), key=lambda r: r.get("at", ""))


def stall_count(rounds: list[dict]) -> int:
    """Consecutive most-recent delegations that filled no slot; a replan resets it."""
    n = 0
    for r in reversed(rounds):
        if r.get("kind") == "replan" or r.get("new_slots"):
            break
        if r.get("kind") == "delegation":
            n += 1
    return n


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# ── strict pre-run checks ────────────────────────────────────────────────────────
def pre_run_problems(state: dict, slots: dict, steps: dict, step_id: str, agent: str,
                     task_slots: list[str], fp: str | None) -> list[str]:
    if not slots or not steps:
        return ["no plan: call set_plan with the slots the answer needs and the steps that "
                "fill them (it can go in the same turn as this delegation)"]
    step = steps.get(step_id)
    if step is None:
        return [f"{step_id} is not in the plan; add it with set_plan"]
    problems = []
    if step.get("agent") != agent:
        problems.append(f"{step_id} is planned for {step.get('agent')}, not {agent}")
    extra = [s for s in task_slots if s not in (step.get("slots") or [])]
    if extra:
        problems.append(f"{step_id} is planned to fill {step.get('slots')}, not {extra}")
    if step.get("status") == "done":
        problems.append(f"{step_id} is already done — its facts are in the ledger")
    waiting = [d for d in step.get("depends_on") or []
               if (steps.get(d) or {}).get("status") not in ("done", "partial")]
    if waiting:
        problems.append(f"{step_id} depends on {waiting}, which have not finished")
    for sid in task_slots:
        rec = slots.get(sid)
        if rec is None:
            problems.append(f"slot {sid} is not in the ledger")
        elif rec.get("status") == "filled":
            problems.append(f"slot {sid} is already filled — use its facts {rec.get('facts')}")
        elif rec.get("status") == "blocked":
            problems.append(f"slot {sid} is blocked after {rec.get('attempts_failed')} failed "
                            "attempts — revise it with set_plan or answer with the gap")
    rounds = ordered_rounds(state)
    stalled = stall_count(rounds)
    if stalled >= STALL_LIMIT:
        problems.append(f"STALLED: the last {stalled} delegations filled no slot — call set_plan "
                        "to revise the ledger, or answer with the gaps")
    if fp is not None:
        same = [r for r in rounds if r.get("fingerprint") == fp]
        if any(r.get("new_slots") or r.get("facts") for r in same):
            problems.append("identical task already ran and returned facts — use them")
        failed = [r for r in same if r.get("status") == "failed"]
        if len(failed) >= IDENTICAL_FAILURES:
            problems.append(f"identical task failed {len(failed)} times "
                            f"({failed[-1].get('error', 'no detail')}) — change the task or "
                            "answer with the gap")
    return problems


# ── strict post-run checks ───────────────────────────────────────────────────────
def norm_attr(attr: str | None) -> str | None:
    if not attr:
        return None
    a = attr.strip().lower().replace(" ", "_")
    return _ATTR_SYNONYMS.get(a, a)


def norm_entity(entity: str | None) -> str | None:
    return entity.strip().lower() if entity else None


def _tolerance(a: float, b: float) -> float:
    return max(0.051, 0.005 * max(abs(a), abs(b)))


def _need_met(need: str, findings: list[dict], figure_ids: list[str]) -> bool:
    if need == "figure":
        return bool(figure_ids)
    field = {"value": "value", "unit": "unit", "time": "time", "entity": "entity",
             "list": "items"}[need]
    return any(f.get(field) is not None for f in findings)


def apply_report(state: dict, slots: dict, steps: dict, *, step_id: str, agent: str,
                 task_slots: list[str], windows: dict[str, str | None],
                 linked: dict[str, list[str]], report: SpecialistReport, created: list[str],
                 blackboard: dict, exhausted: bool, fp: str, round_key: str,
                 failed_error: str | None = None) -> tuple[dict, list[str], str]:
    """Validate a report against the ledger. Returns (state update, notes, step status)."""
    notes: list[str] = []
    accepted: list[dict] = []
    figures = [a for a in created if (blackboard.get(a) or {}).get("kind") == "figure"]
    existing_facts = dict(state.get("facts") or {})

    for i, f in enumerate(report.findings):
        f = f.model_dump()
        if f["slot_id"] not in task_slots:
            notes.append(f"dropped a finding for slot {f['slot_id']!r}, which this step was not "
                         "asked to fill")
            continue
        if f.get("artifact_id") and f["artifact_id"] not in blackboard:
            notes.append(f"{f['slot_id']}: artifact {f['artifact_id']} does not exist — removed")
            f["artifact_id"] = None
        entity = f.get("entity") or ""
        system, _, tag = entity.partition(".")
        spec = tag_map(system).get(tag) if system in systems() and tag else None
        if system in systems() and tag and spec is None:
            notes.append(f"{f['slot_id']}: entity {entity} is not a catalog tag")
        if spec is not None:
            catalog_unit = glossary.display_unit(spec)
            if f.get("unit") and catalog_unit and \
                    glossary.canonical_unit(f["unit"]) != glossary.canonical_unit(catalog_unit):
                notes.append(f"{f['slot_id']}: unit {f['unit']!r} for {entity} corrected to "
                             f"catalog unit {catalog_unit!r}")
                f["unit"] = catalog_unit
            elif not f.get("unit") and catalog_unit and f.get("value") is not None:
                f["unit"] = catalog_unit
        f.update(step_id=step_id, agent=agent, window=windows.get(f["slot_id"]),
                 attribute_norm=norm_attr(f.get("attribute")), entity_norm=norm_entity(entity))
        accepted.append({**f, "key": f"{step_id}.{i + 1}"})

    # contradictions: same entity + attribute + window, different value
    conflicts: set[str] = set()
    pool = list(existing_facts.values()) + accepted
    new_keys = {f["key"] for f in accepted}
    for a, b in itertools.combinations(pool, 2):
        if a.get("value") is None or b.get("value") is None:
            continue
        if a.get("key") not in new_keys and b.get("key") not in new_keys:
            continue  # both already accepted earlier — checked when the later one arrived
        same = (a.get("entity_norm") and a.get("entity_norm") == b.get("entity_norm")
                and a.get("attribute_norm") and a.get("attribute_norm") == b.get("attribute_norm")
                and (a.get("window") or "") == (b.get("window") or ""))
        if same and abs(a["value"] - b["value"]) > _tolerance(a["value"], b["value"]):
            conflicts.update({a["slot_id"], b["slot_id"]})
            notes.append(f"CONFLICT: {a['entity']} {a['attribute']} = {a['value']:g} ({a['step_id']}) "
                         f"vs {b['value']:g} ({b['step_id']}) for the same window")

    slot_updates: dict[str, dict] = {}
    new_slots: list[str] = []
    for sid in task_slots:
        rec = dict(slots.get(sid) or {})
        mine = [f for f in accepted if f["slot_id"] == sid]
        missing = [n for n in rec.get("needs") or ["value"] if not _need_met(n, mine, figures)]
        facts = list(rec.get("facts") or []) + [f["key"] for f in mine]
        if sid in conflicts:
            status = "conflict"
        elif mine and not missing:
            status = "filled"
        elif mine:
            status = "partial"
            notes.append(f"{sid}: finding lacks required {', '.join(missing)}")
        else:
            status = "pending"
            notes.append(f"{sid}: no finding returned")
        attempts = rec.get("attempts_failed", 0) + (0 if status == "filled" else 1)
        if status in ("pending", "partial") and attempts >= SLOT_ATTEMPTS:
            status = "blocked"
        if status == "filled" and rec.get("status") != "filled":
            new_slots.append(sid)
        slot_updates[sid] = {"status": status, "missing": missing, "facts": facts,
                             "attempts_failed": attempts, "linked_tags": linked.get(sid, []),
                             "window": windows.get(sid)}
    for sid in conflicts - set(task_slots):
        slot_updates[sid] = {"status": "conflict"}

    filled = [s for s in task_slots if slot_updates[s]["status"] == "filled"]
    if failed_error or (report.status == "failed" and not accepted):
        step_status = "failed"
    elif len(filled) == len(task_slots):
        step_status = "done"
    else:
        step_status = "partial"
    if exhausted and step_status == "done":
        notes.append("the specialist hit its step budget after filling every slot")

    handoff = report.handoff.model_dump()
    bad_tags = [t for t in handoff["tags"] if t.partition(".")[0] not in systems()
                or t.partition(".")[2] not in tag_map(t.partition(".")[0])]
    if bad_tags:
        notes.append(f"handoff tags {bad_tags} are not catalog tags — removed")
        handoff["tags"] = [t for t in handoff["tags"] if t not in bad_tags]

    update = {
        "facts": {f["key"]: f for f in accepted},
        "slots": slot_updates,
        "plan": {step_id: {"status": step_status, "answer": report.answer[:200],
                           "artifacts": created, "handoff": handoff}},
        "rounds": {round_key: {"kind": "delegation", "at": now_iso(), "step_id": step_id,
                               "agent": agent, "fingerprint": fp, "status": step_status,
                               "new_slots": new_slots, "facts": len(accepted),
                               "error": failed_error}},
    }
    return update, notes, step_status


# ── views ────────────────────────────────────────────────────────────────────────
def fact_line(f: dict) -> str:
    bits = [f.get("slot_id", "?")]
    if f.get("entity"):
        bits.append(f["entity"])
    if f.get("attribute"):
        bits.append(f["attribute"])
    if f.get("value") is not None:
        bits.append(f"= {f['value']:g}" + (f" {f['unit']}" if f.get("unit") else ""))
    if f.get("time"):
        bits.append(f"@{f['time']}")
    if f.get("items") is not None:
        bits.append(f"items={f['items'][:8]}")
    if f.get("artifact_id"):
        bits.append(f"[{f['artifact_id']}]")
    return " ".join(bits) + f" — {f.get('statement', '')}"


def render_report(step_id: str, agent: str, status: str, report: SpecialistReport,
                  update: dict, notes: list[str], raw_fallback: str | None = None) -> str:
    lines = [f"{step_id} {agent} → {status}", f"ANSWER: {report.answer}"]
    facts = list((update.get("facts") or {}).values())
    if facts:
        lines.append("FACTS:")
        lines += ["  " + fact_line(f) for f in facts]
    h = (update.get("plan") or {}).get(step_id, {}).get("handoff") or {}
    handoff = [f"{k} {', '.join(v)}" for k, v in h.items() if v]
    if handoff:
        lines.append("HANDOFF: " + " · ".join(handoff))
    if report.gaps:
        lines.append("GAPS: " + "; ".join(report.gaps))
    if notes:
        lines.append("CODE CHECKS: " + "; ".join(notes))
    if raw_fallback:
        lines.append("UNSTRUCTURED REPORT (not machine-checked): " + raw_fallback[:1500])
    return "\n".join(lines)


def ledger_view(state: dict) -> str:
    """SLOTS, PLAN, PROGRESS and ARTIFACTS for the orchestrator's prompt ("" when empty)."""
    slots = state.get("slots") or {}
    steps = state.get("plan") or {}
    facts = state.get("facts") or {}
    sections = []
    if slots:
        rows = []
        for sid in sorted(slots, key=lambda k: int(k[1:])):
            s = slots[sid]
            extra = f" missing={s['missing']}" if s.get("missing") and s.get("status") != "filled" else ""
            rows.append(f"  {sid} [{s.get('kind')}·{s.get('aggregation')}] {s.get('status', 'pending')}"
                        f"{extra} — {s.get('ask')}")
            rows += ["      " + fact_line(facts[k]) for k in s.get("facts") or [] if k in facts]
        sections.append("## SLOTS (the facts the answer needs; status kept by code)\n" + "\n".join(rows))
    if steps:
        rows = []
        for step_id in sorted(steps, key=lambda k: int(k[1:])):
            st = steps[step_id]
            after = f" after {','.join(st['depends_on'])}" if st.get("depends_on") else ""
            arts = f" [{', '.join(st['artifacts'])}]" if st.get("artifacts") else ""
            h = st.get("handoff") or {}
            hand = "".join(f" {k}={v}" for k, v in h.items() if v)
            rows.append(f"  {step_id} {st.get('agent')} fills {st.get('slots')} "
                        f"{st.get('status', 'pending')}{after}{arts}{hand}")
        sections.append("## PLAN\n" + "\n".join(rows))
    rounds = ordered_rounds(state)
    stalled = stall_count(rounds)
    if rounds:
        msg = f"## PROGRESS\n  delegations so far: {sum(r.get('kind') == 'delegation' for r in rounds)}; " \
              f"without a newly filled slot in a row: {stalled}/{STALL_LIMIT}"
        if stalled >= STALL_LIMIT:
            msg += "\n  STALLED — delegation is refused until set_plan revises the ledger; or answer with the gaps."
        sections.append(msg)
    lines = []
    for art_id, d in (state.get("blackboard") or {}).items():
        if not isinstance(d, dict):
            continue
        kind = d.get("kind", "?")
        if kind == "table":
            cols = [c.split(":")[0] for c in (d.get("columns") or [])][:8]
            lines.append(f"  {art_id}: table, {d.get('row_count')} rows, cols={cols}")
        elif kind == "records":
            lines.append(f"  {art_id}: records, {d.get('count')} rows")
        elif kind == "figure":
            caption = f" '{d['caption']}'" if d.get("caption") else ""
            lines.append(f"  {art_id}: figure{caption} -> {d.get('path')}")
        else:
            lines.append(f"  {art_id}: {kind}")
    if lines:
        sections.append("## ARTIFACTS\n" + "\n".join(lines))
    return "\n\n".join(sections)


# ── the answer check ─────────────────────────────────────────────────────────────
_UNIT_RE = (r"°C|degC|deg C|µm|μm|um|mm/s|mbara|mbar|barg|bar|kW|MW|t/h|m3/h|m³/h|kJ/kWh|"
            r"kg/kWh|%|A|rpm|hours|hour|hrs|h|minutes|minute|min|INR|index")
_NUM_UNIT = re.compile(rf"(?<![\w.])(-?\d[\d,]*(?:\.\d+)?)\s*(k|K|M)?\s*({_UNIT_RE})(?![\w/])")
_CURRENCY = re.compile(r"(?:₹|INR)\s*(-?\d[\d,]*(?:\.\d+)?)\s*(k|K|M|million|lakh|crore)?")
_MULT = {None: 1, "k": 1e3, "K": 1e3, "M": 1e6, "million": 1e6, "lakh": 1e5, "crore": 1e7}


def _evidence(state: dict) -> list[tuple[float, str | None]]:
    """Every number the answer may state as-is: facts, setpoints of tags in play, constants."""
    ev: list[tuple[float, str | None]] = []
    facts = (state.get("facts") or {}).values()
    tags_in_play: set[tuple[str, str]] = set()
    for f in facts:
        if f.get("value") is not None:
            ev.append((float(f["value"]), glossary.canonical_unit(f.get("unit"))))
        system, _, tag = (f.get("entity") or "").partition(".")
        if system in systems() and tag:
            tags_in_play.add((system, tag))
    for s in (state.get("slots") or {}).values():
        for name in s.get("linked_tags") or []:
            system, _, tag = name.partition(".")
            tags_in_play.add((system, tag))
    for system, tag in tags_in_play:
        spec = tag_map(system).get(tag) if system in systems() else None
        if spec is None:
            continue
        unit = glossary.canonical_unit(glossary.display_unit(spec))
        for v in (spec.normal_min, spec.normal_max, spec.alarm_lo, spec.alarm_hi, spec.alarm_hihi,
                  spec.alarm_lolo):
            if v is not None:
                ev.append((float(v), unit))
    for n in re.findall(r"\d+(?:\.\d+)?", question_of(state)):
        ev.append((float(n), None))
    ev.append((float(EVENT_PAD_HOURS), "h"))
    return ev


def _close(written: float, decimals: int, target: float, mult: float = 1.0) -> bool:
    """Equal at the precision the number was written with (65.8 matches 65.8049, not 65.9).

    Deliberately no relative slack: with it, "60.86%" passed as (85-45)/65.8×100 = 60.79.
    """
    tol = max(0.5 * 10 ** -decimals * mult, 1e-9)
    return abs(written - target) <= tol


def _derivable(written: float, decimals: int, unit: str | None, ev: list[tuple[float, str | None]],
               mult: float = 1.0) -> bool:
    values = [v for v, u in ev if unit is None or u is None or u == unit or unit == "%"]
    for v in values:
        if _close(written, decimals, v, mult):
            return True
    for a, b in itertools.permutations(values, 2):
        if _close(written, decimals, a - b, mult) or _close(written, decimals, a + b, mult):
            return True
        if b and unit == "%" and (_close(written, decimals, a / b * 100, mult)
                                  or _close(written, decimals, (a - b) / b * 100, mult)):
            return True
    return False


def answer_problems(text: str, state: dict) -> list[str]:
    """Numbers with units in the answer that no fact, setpoint or simple arithmetic supports,
    and numbers whose unit contradicts the fact they match."""
    ev = _evidence(state)
    problems: list[str] = []
    body = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?", " ", text)
    body = re.sub(r"\b[A-Z]{2,}-[A-Z]+-\d+\b", " ", body)  # alert / work order ids
    seen: set[str] = set()
    for m in _NUM_UNIT.finditer(body):
        raw, mult_raw, unit_raw = m.group(1), m.group(2), m.group(3)
        mult = _MULT.get(mult_raw, 1)
        written = float(raw.replace(",", "")) * mult
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        unit = glossary.canonical_unit(unit_raw)
        token = m.group(0).strip()
        if token in seen:
            continue
        seen.add(token)
        exact = [(v, u) for v, u in ev if _close(written, decimals, v, mult)]
        if exact and unit and all(u and u != unit and unit != "%" for _, u in exact):
            problems.append(f"'{token}': the matching fact is in {exact[0][1]}, not {unit_raw}")
            continue
        if not _derivable(written, decimals, unit, ev, mult):
            problems.append(f"'{token}' is not an accepted fact, a setpoint, or arithmetic on them")
    for m in _CURRENCY.finditer(body):
        raw, mult_raw = m.group(1), m.group(2)
        mult = _MULT.get(mult_raw, 1)
        written = float(raw.replace(",", "")) * mult
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if not _derivable(written, decimals, "INR", ev, mult):
            problems.append(f"'{m.group(0).strip()}' is not an accepted fact or arithmetic on them")
    return problems


def footers(state: dict, unverified: list[str] | None = None) -> str:
    """Code-written Evidence / Gaps / Unverified lines appended to the final answer."""
    slots = state.get("slots") or {}
    facts = state.get("facts") or {}
    lines = []
    ev = []
    for sid in sorted(slots, key=lambda k: int(k[1:])):
        arts = sorted({facts[k]["artifact_id"] for k in slots[sid].get("facts") or []
                       if k in facts and facts[k].get("artifact_id")})
        steps_ = sorted({facts[k]["step_id"] for k in slots[sid].get("facts") or [] if k in facts})
        if arts or steps_:
            ev.append(f"{sid} ← {', '.join(arts) or 'report'} ({', '.join(steps_)})")
    if ev:
        lines.append("**Evidence:** " + "; ".join(ev))
    gaps = [f"{sid} ({s.get('ask')}) — {s.get('status')}"
            + (f", missing {', '.join(s['missing'])}" if s.get("missing") else "")
            for sid, s in sorted(slots.items(), key=lambda kv: int(kv[0][1:]))
            if s.get("status") != "filled"]
    if gaps:
        lines.append("**Gaps:** " + "; ".join(gaps))
    if unverified:
        lines.append("**Unverified by code:** " + "; ".join(unverified))
    return "\n\n" + "\n".join(lines) if lines else ""


def budget_answer(state: dict) -> str:
    """Answer composed by code when the model-call budget is spent."""
    facts = state.get("facts") or {}
    lines = ["The step budget for this question was reached. Facts established so far:"]
    lines += ["- " + f.get("statement", "") for f in facts.values()] or ["- none"]
    return "\n".join(lines) + footers(state)
