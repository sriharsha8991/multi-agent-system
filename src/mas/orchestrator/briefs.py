"""From a Task to the brief a specialist reads — deterministic, no LLM.

A Task only names a plan step and the slots to fill. Everything else in the brief is derived
here from the ledger, the capability registry, the glossary and the clock:

* **references** (``$s1.alert_id``, ``$s1.tags``, ``$s1.artifacts``) resolve to what earlier
  steps handed over — no identifier is retyped by a model;
* **time** resolves in code; telemetry-side agents get the coverage window when none is set;
* **tags** come from explicit names or glossary concepts (every matching tag for measure
  slots, the primary tag for derive slots);
* the **fingerprint** of the resulting data request feeds the strict repeat checks.

Same plan in, same brief out — which is what makes the specialists' inputs deterministic.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from ..agents.capabilities import REGISTRY
from ..catalog import SYSTEM_META, glossary
from ..execution.timewin import data_bounds, resolve_timespec
from ..llm.schemas import Task, TimeSpec, TimeWindow
from . import ledger

@dataclass
class Prepared:
    brief: str = ""
    fingerprint: str = ""
    windows: dict[str, str | None] = field(default_factory=dict)
    linked: dict[str, list[str]] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def coverage_window() -> TimeWindow:
    start, end = data_bounds()
    return TimeWindow(start=datetime.fromisoformat(start), end=datetime.fromisoformat(end),
                      label="full telemetry coverage (no time in the question)", source="explicit")


def prepare(task: Task, agent: str, state: dict) -> Prepared:
    """Resolve, check and render one delegation. ``problems`` non-empty means do not run."""
    cap = REGISTRY[agent]
    slots, steps = ledger.effective_ledger(state)
    blackboard = state.get("blackboard") or {}
    out = Prepared()

    inputs: list[str] = []
    for item in task.inputs:
        try:
            inputs += ledger.resolve_ref(item, steps) if item.startswith("$") else [item]
        except ValueError as e:
            out.problems.append(str(e))
    missing = [a for a in inputs if a not in blackboard]
    if missing:
        out.problems.append(f"inputs {missing} are not artifacts; available: {sorted(blackboard)}")
    if cap.needs_inputs and not inputs:
        out.problems.append(f"{agent} needs `inputs` — the artifact ids (or $sN.artifacts) "
                            "holding its data")
    out.inputs = list(dict.fromkeys(inputs))

    windows: dict[str, TimeWindow | None] = {}
    signatures = []
    for sid in task.slots:
        if sid not in slots:
            continue  # reported by pre_run_problems
        rec = slots[sid] = dict(slots[sid])  # local copy: brief-only fields must not reach state
        try:
            windows[sid] = _window(rec, steps, cap.clamp_time)
        except ValueError as e:
            out.problems.append(f"{sid}: {e}")
            windows[sid] = None
        tags: list = []
        if cap.links_tags:
            try:
                tags, note = ledger.linked_tags(rec, steps)
                rec["_link_note"] = note
            except ValueError as e:
                out.problems.append(f"{sid}: {e}")
        out.linked[sid] = [f"{t.system}.{t.tag_name}" for t in tags]
        rec["_tag_specs"] = tags
        key = windows[sid].key() if windows[sid] else None
        out.windows[sid] = key
        signatures.append(ledger.slot_signature(rec, key, out.linked[sid]))

    out.fingerprint = ledger.fingerprint(agent, signatures, out.inputs, task.note)
    out.problems += ledger.pre_run_problems(state, slots, steps, task.step_id, agent, task.slots,
                                            out.fingerprint)
    if not out.problems:
        out.brief = _render(task, agent, slots, windows, blackboard, out.inputs)
    return out


def _window(rec: dict, steps: dict, clamp: bool) -> TimeWindow | None:
    spec = rec.get("time")
    if not spec:
        # Only a measurement reads the database directly; a derive slot works on its inputs.
        return coverage_window() if clamp and rec.get("kind") == "measure" else None
    spec = dict(spec)
    if isinstance(spec.get("around_alert"), str) and spec["around_alert"].startswith("$"):
        spec["around_alert"] = ledger.resolve_ref(spec["around_alert"], steps)[0]
    return resolve_timespec(TimeSpec.model_validate(spec), clamp=clamp)


def _setpoints(t) -> str:
    bits = [glossary.display_unit(t) or "no unit", f"normal {t.normal_min:g}..{t.normal_max:g}"]
    if t.alarm_hi is not None:
        bits.append(f"alarm_hi {t.alarm_hi:g}")
    if t.alarm_hihi is not None:
        bits.append(f"alarm_hihi {t.alarm_hihi:g}")
    if t.is_derived:
        bits.append("derived")
    return ", ".join(bits)


def _tag_block(tags: list) -> list[str]:
    """Tags grouped by identical setpoints — 14 bearing temps are one line, not 14."""
    groups: dict[str, list[str]] = defaultdict(list)
    for t in tags:
        groups[_setpoints(t)].append(f"{t.system}.{t.tag_name}")
    return [f"    [{sp}] {', '.join(names)}" for sp, names in groups.items()]


def _render(task: Task, agent: str, slots: dict, windows: dict, blackboard: dict,
            inputs: list[str]) -> str:
    lines = [f"STEP {task.step_id} · {agent}"]
    for sid in task.slots:
        rec = slots[sid]
        lines.append(f"SLOT {sid} · {rec['kind']} · {rec['aggregation']} — {rec['ask']}")
        if rec.get("systems"):
            lines.append("  systems: " + ", ".join(
                f"{s} ({SYSTEM_META[s]['display_name']})" for s in rec["systems"]))
        specs = rec.get("_tag_specs") or []
        if specs:
            use = ("use their units for axes and their setpoints for threshold lines"
                   if agent == "coder_agent" else
                   "add related tags only if they sharpen the answer, and say so")
            lines.append(f"  tags ({len(specs)}; {rec.get('_link_note')}) — the slot is about "
                         f"these; {use}:")
            lines += _tag_block(specs)
        elif rec.get("concepts"):
            lines.append(f"  concepts: {', '.join(rec['concepts'])}")
        w = windows.get(sid)
        if w is not None:
            lines.append(f"  window: {w.render()} — resolved in code; use verbatim")
        if rec.get("threshold") is not None:
            lines.append(f"  threshold: {rec['threshold']}")
        lines.append(f"  the finding must carry: {', '.join(rec.get('needs') or ['value'])}")
    if inputs:
        lines.append("INPUTS:")
        for art in inputs:
            d = blackboard.get(art) or {}
            cols = [c.split(":")[0] for c in (d.get("columns") or [])][:12]
            size = d.get("row_count", d.get("count", "?"))
            lines.append(f"  {art}: {d.get('kind', '?')}, {size} rows"
                         + (f", cols={cols}" if cols else ""))
    if task.note:
        lines.append(f"NOTE: {task.note}")
    lines.append("REPORT: at least one finding per slot above, slot_id set. Numbers in value, "
                 "unit in unit, event times in time, the tag / alert / work order in entity, "
                 "list or rank items in items ([] when none were found). Put what else you "
                 "noticed about these slots in the answer.")
    return "\n".join(lines)
