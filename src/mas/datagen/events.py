"""Event timeline (E1-E8) + demo-guarantee constraints (MOD-06 / §9).

Events are scheduled first; they shape the telemetry (a degradation ramp on a
specific tag, reset after the corrective repair), and the alert detector then
rediscovers them from the final series. Each event knows which tag/window it
affects and which spare items its work order consumes, so maintenance can be
linked deterministically.

Windows are placed so the affected machine is actually *running* (duty), and so
the demo guarantees hold — most importantly DG-1: the latest bfpa alert is the
E1 bearing-temperature excursion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from .modes import GenContext


@dataclass(slots=True)
class Degradation:
    tag: str
    start_day: float
    end_day: float
    magnitude: float          # additive; peak reached at end_day, reset after
    sign: float = 1.0


@dataclass(slots=True)
class EventSpec:
    event_id: str
    system: str
    kind: str
    primary_tag: str
    degradations: list[Degradation]
    failure_mode: str
    maintenance_class: str          # preventive|corrective|predictive|modification
    detection_method: str
    creates_work_order: bool
    item_plan: list[tuple[str, int]]   # (item_code, quantity)
    data_quality: bool = False
    visible_recovery: bool = True      # eligible for the G-20 repair-visible check
    freeze: tuple[str, float, float] | None = None  # (tag, start_day, end_day)


@dataclass(slots=True)
class EventRecord:
    spec: EventSpec
    start_idx: int
    end_idx: int
    start_ts: datetime
    end_ts: datetime
    frozen_value: float | None = None


# ── the timeline ─────────────────────────────────────────────────────────────
EVENTS: list[EventSpec] = [
    # E1 — BFP-A bearing degradation. Bearing crosses its setpoint AFTER the
    # vibration rise, so the *latest* bfpa alert is the bearing one (DG-1).
    EventSpec(
        "E1", "bfpa", "bearing_degradation", "bearing_temp_1",
        [Degradation("vibration_overall", 24.0, 26.5, 6.0),
         Degradation("bearing_temp_1", 24.5, 27.0, 42.0)],
        failure_mode="overheating", maintenance_class="corrective",
        detection_method="condition_monitoring", creates_work_order=True,
        item_plan=[("BRG-005", 1), ("SEL-001", 1), ("LUB-001", 2)],
    ),
    # E2 — BFP-B seal leakage (while B is on duty, days 8-16).
    EventSpec(
        "E2", "bfpb", "seal_leakage", "seal_leakage_rate",
        [Degradation("seal_leakage_rate", 10.0, 14.0, 7.5),
         Degradation("gland_seal_pressure", 10.0, 14.0, 1.6, sign=-1.0)],
        failure_mode="external_leakage", maintenance_class="corrective",
        detection_method="operator_report", creates_work_order=True,
        item_plan=[("SEL-001", 1), ("ORG-002", 4), ("GSK-005", 2)],
    ),
    # E3 — CEP-A cavitation (while A is on duty, days 8-16). Latest cepa WO,
    # consumes 3 distinct items with distinct quantities (DG-4).
    EventSpec(
        "E3", "cepa", "cavitation", "npsh_margin",
        [Degradation("npsh_margin", 12.0, 13.0, 6.0, sign=-1.0),
         Degradation("vibration_overall", 12.0, 13.0, 4.5),
         Degradation("cavitation_index", 12.0, 13.0, 60.0)],
        failure_mode="cavitation", maintenance_class="predictive",
        detection_method="condition_monitoring", creates_work_order=True,
        item_plan=[("FLT-004", 1), ("GSK-006", 2), ("ORG-001", 6)],
    ),
    # E4 — CEP-B lube-oil filter clogging (while B is on duty, days 16-30).
    EventSpec(
        "E4", "cepb", "oil_filter_clog", "lube_oil_filter_dp",
        [Degradation("lube_oil_filter_dp", 18.0, 21.0, 1.6)],
        failure_mode="plugged_choked", maintenance_class="preventive",
        detection_method="condition_monitoring", creates_work_order=True,
        item_plan=[("FLT-001", 2)],
    ),
    # E5 — Turbine condenser vacuum deterioration + heat-rate rise.
    EventSpec(
        "E5", "turbine", "vacuum_deterioration", "condenser_vacuum",
        [Degradation("condenser_vacuum", 18.0, 20.0, 40.0),
         Degradation("heat_rate", 18.0, 20.0, 1800.0)],
        failure_mode="external_leakage", maintenance_class="corrective",
        detection_method="condition_monitoring", creates_work_order=True,
        item_plan=[("GSK-001", 2), ("SEL-003", 1), ("ORG-005", 4)],
    ),
    # E6 — Turbine restart eccentricity spike (post-outage, ~day 8.2). Critical,
    # short, no work order.
    EventSpec(
        "E6", "turbine", "eccentricity_transient", "eccentricity",
        [Degradation("eccentricity", 8.15, 8.35, 90.0)],
        failure_mode="vibration", maintenance_class="corrective",
        detection_method="alarm", creates_work_order=False, item_plan=[],
        visible_recovery=False,
    ),
    # E7 — BFP-B frozen bearing RTD (sensor fault), while B is on duty (days 23-30).
    EventSpec(
        "E7", "bfpb", "sensor_fault", "bearing_temp_3",
        [], failure_mode="abnormal_instrument_reading", maintenance_class="corrective",
        detection_method="condition_monitoring", creates_work_order=True,
        item_plan=[("INS-001", 1)], data_quality=True, visible_recovery=False,
        freeze=("bearing_temp_3", 25.0, 26.0),
    ),
]


def _idx_for_day(ctx: GenContext, day: float) -> int:
    return int(np.searchsorted(ctx.grid.day_float, day, side="left"))


def _ts(ctx: GenContext, idx: int) -> datetime:
    idx = int(np.clip(idx, 0, ctx.grid.n - 1))
    dt = ctx.grid.axis[idx].astype("datetime64[s]").astype("O")
    return dt.replace(tzinfo=timezone.utc)


def _ramp_reset(n: int, i0: int, i1: int, mag: float) -> np.ndarray:
    """0 before i0, linear 0→mag across [i0,i1], 0 after i1 (post-repair reset)."""
    out = np.zeros(n)
    if i1 <= i0:
        i1 = i0 + 1
    seg = np.arange(i0, min(i1, n))
    out[seg] = mag * (seg - i0) / (i1 - i0)
    return out


def apply_degradations(system: str, arrays: dict[str, np.ndarray],
                       ctx: GenContext) -> list[EventRecord]:
    """Add each event's additive degradation to the system's clean arrays."""
    n = ctx.grid.n
    records: list[EventRecord] = []
    for spec in EVENTS:
        if spec.system != system:
            continue
        # window = union of degradation/freeze windows
        starts = [d.start_day for d in spec.degradations]
        ends = [d.end_day for d in spec.degradations]
        if spec.freeze:
            starts.append(spec.freeze[1])
            ends.append(spec.freeze[2])
        i0 = _idx_for_day(ctx, min(starts))
        i1 = _idx_for_day(ctx, max(ends))

        for deg in spec.degradations:
            if deg.tag not in arrays:
                continue
            d0 = _idx_for_day(ctx, deg.start_day)
            d1 = _idx_for_day(ctx, deg.end_day)
            arrays[deg.tag] = arrays[deg.tag] + deg.sign * _ramp_reset(n, d0, d1, deg.magnitude)

        frozen_value = None
        if spec.freeze:
            ftag, fs, _ = spec.freeze
            if ftag in arrays:
                frozen_value = float(arrays[ftag][_idx_for_day(ctx, fs)])

        # alarm_active flag on during the event window (a real status tag moving)
        if "alarm_active" in arrays and not spec.data_quality:
            arrays["alarm_active"][i0:i1] = 1.0

        records.append(EventRecord(
            spec=spec, start_idx=i0, end_idx=i1,
            start_ts=_ts(ctx, i0), end_ts=_ts(ctx, i1), frozen_value=frozen_value,
        ))
    return records


def apply_frozen(system: str, arrays: dict[str, np.ndarray],
                 records: list[EventRecord], ctx: GenContext) -> None:
    """Freeze sensor-fault tags to a constant — call AFTER the instrument layer
    so the noise does not un-freeze the signal."""
    for rec in records:
        if rec.spec.system != system or not rec.spec.freeze:
            continue
        ftag, fs, fe = rec.spec.freeze
        if ftag not in arrays:
            continue
        i0 = _idx_for_day(ctx, fs)
        i1 = _idx_for_day(ctx, fe)
        val = rec.frozen_value if rec.frozen_value is not None else float(arrays[ftag][i0])
        arrays[ftag][i0:i1] = val
