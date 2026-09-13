"""Maintenance logs, spare-part consumption, and event→work-order linkage.

~120 MaintenanceLogs over 24 months. Event-driven work orders (E1-E7) are linked
to the alert the telemetry produced; the rest are historical, so cost rollups are
interesting. Cost identities are enforced so both natural Cypher formulations of
"total item cost" agree (G-16):

    line_cost         == quantity * unit_cost_at_time
    unit_cost_at_time == Item.unit_cost
    total_item_cost   == sum(line_cost)
    total_cost        == total_item_cost + labor_cost
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .. import catalog
from ..config import Settings, get_settings
from .build_telemetry import GeneratedData
from .events import EVENTS

LABOR_RATE_INR = 1200.0  # per hour
FAILURE_MODES = ["vibration", "overheating", "external_leakage", "plugged_choked",
                 "abnormal_instrument_reading", "structural_deficiency",
                 "electrical_failure", "control_failure", "wear", "looseness"]
CLASSES = ["preventive", "corrective", "predictive", "modification"]
DETECTION = ["condition_monitoring", "periodic_inspection", "alarm", "operator_report"]
TECHS = ["r.iyer", "s.menon", "a.khan", "p.nair", "m.rao", "d.bose", "k.pillai"]

# historical (pre-window) logs per system → ~100 + event/scheduled ≈ 110 total
_HIST_COUNT = {"bfpa": 20, "bfpb": 20, "cepa": 18, "cepb": 20, "turbine": 22}
# items a system's work typically consumes, by preference
_SYS_ITEM_HINT = {
    "bfpa": ["bearing", "seal", "wear_ring", "sleeve", "impeller", "lubricant", "filter"],
    "bfpb": ["bearing", "seal", "wear_ring", "sleeve", "impeller", "lubricant", "filter"],
    "cepa": ["bearing", "seal", "filter", "gasket", "o_ring", "wear_ring", "lubricant"],
    "cepb": ["bearing", "seal", "filter", "gasket", "o_ring", "wear_ring", "lubricant"],
    "turbine": ["bearing", "valve", "gasket", "instrument", "lubricant", "electrical",
                "coupling", "seal", "fastener"],
}
# every pump uses fasteners too — keeps the item pool broad
for _p in ("bfpa", "bfpb", "cepa", "cepb"):
    _SYS_ITEM_HINT[_p].append("fastener")


@dataclass(slots=True)
class MaintenanceOutput:
    logs: list[dict]
    consumed: list[dict]              # {work_order_id, item_code, quantity, unit_cost_at_time, line_cost, currency}


def _cost(consumed_for_wo: list[dict], labor_hours: float) -> tuple[float, float, float]:
    total_item = round(sum(c["line_cost"] for c in consumed_for_wo), 2)
    labor = round(labor_hours * LABOR_RATE_INR, 2)
    return total_item, labor, round(total_item + labor, 2)


def _consume(wo_id: str, plan: list[tuple[str, int]], currency: str) -> list[dict]:
    imap = catalog.item_map()
    rows = []
    for code, qty in plan:
        item = imap[code]
        unit = round(item.unit_cost, 2)
        rows.append(dict(work_order_id=wo_id, item_code=code, quantity=int(qty),
                         unit_cost_at_time=unit, line_cost=round(unit * qty, 2),
                         currency=currency))
    return rows


def _pick_items(rng, system: str, k: int) -> list[tuple[str, int]]:
    hints = _SYS_ITEM_HINT[system]
    pool = [i for i in catalog.items() if i.category in hints]
    if len(pool) < k:
        pool = list(catalog.items())
    chosen = rng.choice(len(pool), size=min(k, len(pool)), replace=False)
    plan = []
    for idx in chosen:
        item = pool[int(idx)]
        qty = int(rng.integers(1, 5))
        plan.append((item.item_code, qty))
    return plan


def build(data: GeneratedData, alerts: list[dict],
          settings: Settings | None = None) -> MaintenanceOutput:
    settings = settings or get_settings()
    currency = settings.currency
    logs: list[dict] = []
    consumed: list[dict] = []
    seq = {s: 0 for s in catalog.systems()}

    def wo_id(system: str) -> str:
        seq[system] += 1
        return f"WO-{system.upper()}-{seq[system]:04d}"

    # index telemetry alerts for event linkage
    def find_alert(system: str, tag: str) -> dict | None:
        cands = [a for a in alerts if a["system"] == system and a["tag_name"] == tag
                 and a.get("has_telemetry")]
        return sorted(cands, key=lambda x: x["start_ts"])[-1] if cands else None

    # ── event-driven work orders (in-window) ─────────────────────────────
    rec_by_event = {r.spec.event_id: r for recs in data.records.values() for r in recs}
    for spec in EVENTS:
        if not spec.creates_work_order:
            continue
        rec = rec_by_event.get(spec.event_id)
        if rec is None:
            continue
        alert = find_alert(spec.system, spec.primary_tag)
        wid = wo_id(spec.system)
        # work order starts a few hours after the trigger, ends at the repair (event end)
        start = rec.end_ts - timedelta(hours=6)
        if alert and datetime.fromisoformat(alert["start_ts"]) >= start:
            start = datetime.fromisoformat(alert["start_ts"]) + timedelta(hours=2)
        end = rec.end_ts
        labor_hours = round(4 + 2 * len(spec.item_plan), 1)
        crows = _consume(wid, spec.item_plan, currency)
        total_item, labor, total = _cost(crows, labor_hours)
        consumed.extend(crows)
        logs.append(dict(
            work_order_id=wid, system=spec.system, maintenance_type=spec.kind,
            maintenance_class=spec.maintenance_class, failure_mode=spec.failure_mode,
            detection_method="alarm" if alert else spec.detection_method,
            description=f"{spec.kind.replace('_',' ').title()} on {spec.system} "
                        f"following {spec.primary_tag} alarm",
            start_ts=start.isoformat(), end_ts=end.isoformat(),
            downtime_hours=round((end - start).total_seconds() / 3600, 1),
            labor_hours=labor_hours, labor_cost=labor, total_item_cost=total_item,
            total_cost=total, currency=currency, technician=TECHS[seq[spec.system] % len(TECHS)],
            status="completed", related_alert_id=alert["alert_id"] if alert else None,
            visible_recovery=spec.visible_recovery and not spec.data_quality,
        ))

    # ── scheduled in-window preventive for CEP-A (guarantees DG-4: >=2 logs) ──
    # placed EARLY in the window so the E3 predictive WO remains the *latest*.
    rng = settings.rng("sched", "cepa")
    wid = wo_id("cepa")
    start = settings.window_start + timedelta(days=3)
    end = start + timedelta(hours=6)
    plan = [("LUB-003", 1), ("FLT-007", 2)]
    crows = _consume(wid, plan, currency)
    total_item, labor, total = _cost(crows, 6.0)
    consumed.extend(crows)
    logs.append(dict(
        work_order_id=wid, system="cepa", maintenance_type="routine_service",
        maintenance_class="preventive", failure_mode="wear",
        detection_method="periodic_inspection",
        description="Scheduled oil service and fine-filter change on cepa",
        start_ts=start.isoformat(), end_ts=end.isoformat(), downtime_hours=6.0,
        labor_hours=6.0, labor_cost=labor, total_item_cost=total_item, total_cost=total,
        currency=currency, technician=TECHS[1], status="completed",
        related_alert_id=None, visible_recovery=False,
    ))

    # ── historical work orders (all before the telemetry window) ─────────
    for system, count in _HIST_COUNT.items():
        rng = settings.rng("hist_wo", system)
        for _ in range(count):
            wid = wo_id(system)
            days_before = float(rng.uniform(31, settings.maintenance_history_months * 30))
            start = settings.window_start - timedelta(days=days_before)
            dur_h = float(rng.uniform(3, 48))
            end = start + timedelta(hours=dur_h)
            mclass = str(rng.choice(CLASSES, p=[0.5, 0.3, 0.15, 0.05]))
            # ~55% of logs consume >=3 items (comfortably clears G-12's 40%)
            k = int(rng.integers(3, 8)) if rng.random() < 0.55 else int(rng.integers(1, 3))
            plan = _pick_items(rng, system, k)
            crows = _consume(wid, plan, currency)
            labor_hours = round(dur_h * 0.5, 1)
            total_item, labor, total = _cost(crows, labor_hours)
            consumed.extend(crows)
            logs.append(dict(
                work_order_id=wid, system=system,
                maintenance_type="overhaul" if mclass == "corrective" else "service",
                maintenance_class=mclass,
                failure_mode=str(rng.choice(FAILURE_MODES)),
                detection_method=str(rng.choice(DETECTION)),
                description=f"{mclass.title()} maintenance on {system}",
                start_ts=start.isoformat(), end_ts=end.isoformat(),
                downtime_hours=round(dur_h, 1), labor_hours=labor_hours,
                labor_cost=labor, total_item_cost=total_item, total_cost=total,
                currency=currency, technician=str(rng.choice(TECHS)),
                status="completed", related_alert_id=None, visible_recovery=False,
            ))

    # ── coverage pass: guarantee no orphan Items (G-10) ──────────────────
    _ensure_all_items_consumed(logs, consumed, currency)

    return MaintenanceOutput(logs=logs, consumed=consumed)


def _ensure_all_items_consumed(logs: list[dict], consumed: list[dict],
                               currency: str) -> None:
    """Attach any never-consumed item to a historical log, preserving cost identities."""
    imap = catalog.item_map()
    used = {c["item_code"] for c in consumed}
    orphans = [code for code in imap if code not in used]
    if not orphans:
        return
    # historical logs only (event/scheduled logs keep their exact planned items)
    hist = [L for L in logs if L["related_alert_id"] is None]
    if not hist:
        hist = logs
    for k, code in enumerate(orphans):
        L = hist[k % len(hist)]
        item = imap[code]
        unit = round(item.unit_cost, 2)
        line = round(unit * 1, 2)
        consumed.append(dict(work_order_id=L["work_order_id"], item_code=code,
                             quantity=1, unit_cost_at_time=unit, line_cost=line,
                             currency=currency))
        L["total_item_cost"] = round(L["total_item_cost"] + line, 2)
        L["total_cost"] = round(L["total_item_cost"] + L["labor_cost"], 2)
