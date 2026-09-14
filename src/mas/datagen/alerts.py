"""Deterministic alert detection over the *final* telemetry.

The alerts this emits ARE the Alert nodes — so no alert exists that the telemetry
does not support (the §8 invariant, obtained structurally). Threshold excursions
(hi/hi_hi/lo/lo_lo) are found by scanning with ISA-18.2 hygiene (deadband,
on/off-delay, merge); the frozen-sensor (data_quality) alert is taken from the
event record (generic frozen-scanning would false-trigger on standby zeros).

A handful of older alerts (``has_telemetry=false``) are added for realism; they
are all before the telemetry window, so the latest bfpa alert is still E1 (DG-1).
"""

from __future__ import annotations

from datetime import timedelta, timezone

import numpy as np

from .. import catalog
from ..catalog import SYSTEM_META
from .build_telemetry import GeneratedData

DEADBAND = 0.02          # 2% of setpoint
ON_DELAY_S = 180         # 3 min: suppresses single-sample instrument spikes
OFF_DELAY_S = 60
MERGE_GAP_S = 600        # 10 min

# how many older (pre-window) alerts to add per system for realism
_HISTORICAL = {"bfpa": 12, "bfpb": 12, "cepa": 8, "cepb": 8, "turbine": 16}


def _ts(axis: np.ndarray, idx: int):
    idx = int(np.clip(idx, 0, axis.shape[0] - 1))
    return axis[idx].astype("datetime64[s]").astype("O").replace(tzinfo=timezone.utc)


def _severity_priority(system: str, family: str, level: str, peak: float) -> tuple[str, str]:
    crit = SYSTEM_META[system]["criticality"]
    if family == "vibration":  # ISO 20816-3 zones on velocity
        if peak >= 7.1:
            return "critical", "critical"
        if peak >= 4.5:
            return "high", "high"
        if peak >= 2.8:
            return "medium", "medium"
        return "low", "low"
    if level in ("hi_hi", "lo_lo"):
        return ("critical", "critical") if crit in ("critical", "high") else ("high", "high")
    if level in ("hi", "lo"):
        return "high" if crit in ("critical", "high") else "medium", "medium"
    return "medium", "medium"


def _scan_side(arr: np.ndarray, setpoint: float,
               sample_s: int, high_side: bool) -> list[tuple[int, int, float]]:
    """Return merged (start_idx, end_idx, peak) excursions past ``setpoint``."""
    on_steps = max(3, ON_DELAY_S // sample_s)
    merge_steps = max(1, MERGE_GAP_S // sample_s)
    db = abs(setpoint) * DEADBAND
    with np.errstate(invalid="ignore"):
        if high_side:
            active = arr >= setpoint
            clear = arr < (setpoint - db)
        else:
            active = arr <= setpoint
            clear = arr > (setpoint + db)

    intervals: list[list[int]] = []
    i, n = 0, arr.shape[0]
    in_ev = False
    start = 0
    run = 0
    for i in range(n):
        if active[i]:
            if not in_ev:
                run += 1
                if run >= on_steps:
                    in_ev = True
                    start = i - run + 1
            # stay in event
        else:
            run = 0
            if in_ev and clear[i]:
                intervals.append([start, i - 1])
                in_ev = False
    if in_ev:
        intervals.append([start, n - 1])

    # merge close intervals
    merged: list[list[int]] = []
    for iv in intervals:
        if merged and iv[0] - merged[-1][1] <= merge_steps:
            merged[-1][1] = iv[1]
        else:
            merged.append(iv)

    out = []
    for a, b in merged:
        seg = arr[a:b + 1]
        peak = float(np.nanmax(seg) if high_side else np.nanmin(seg))
        out.append((a, b, peak))
    return out


def detect(data: GeneratedData) -> list[dict]:
    settings = data.ctx.settings
    axis = data.timestamps
    sample_s = settings.sample_seconds
    alerts: list[dict] = []

    for system in catalog.systems():
        arrays = data.arrays[system]
        for spec in catalog.tags_for(system):
            if spec.family == "status":
                continue
            arr = arrays[spec.tag_name]
            for level, setp, is_high in (
                ("hi", spec.alarm_hi, True),
                ("lo", spec.alarm_lo, False),
            ):
                if setp is None:
                    continue
                for a, b, peak in _scan_side(arr, setp, sample_s, is_high):
                    # promote to hi_hi / lo_lo if the extreme setpoint is crossed
                    lvl = level
                    thr = setp
                    if is_high and spec.alarm_hihi is not None and peak >= spec.alarm_hihi:
                        lvl, thr = "hi_hi", spec.alarm_hihi
                    if (not is_high) and spec.alarm_lolo is not None and peak <= spec.alarm_lolo:
                        lvl, thr = "lo_lo", spec.alarm_lolo
                    sev, pri = _severity_priority(system, spec.family, lvl, peak)
                    atype = "vibration" if spec.family == "vibration" else "process"
                    alerts.append(dict(
                        system=system, tag_name=spec.tag_name, alert_type=atype,
                        alert_level=lvl, severity=sev, priority=pri,
                        threshold_value=float(thr), peak_value=peak,
                        start_idx=a, end_idx=b, has_telemetry=True,
                    ))

        # frozen-sensor (data_quality) alerts from event records
        for rec in data.records[system]:
            if not rec.spec.freeze:
                continue
            ftag = rec.spec.freeze[0]
            fspec = catalog.tag_map(system)[ftag]
            a = int(np.searchsorted(data.ctx.grid.day_float, rec.spec.freeze[1]))
            b = int(np.searchsorted(data.ctx.grid.day_float, rec.spec.freeze[2]))
            val = rec.frozen_value if rec.frozen_value is not None else float(arrays[ftag][a])
            alerts.append(dict(
                system=system, tag_name=ftag, alert_type="data_quality",
                alert_level="frozen", severity="low", priority="low",
                threshold_value=float(fspec.alarm_hi or 0.0), peak_value=val,
                start_idx=a, end_idx=b, has_telemetry=True,
            ))

    # finalise telemetry alerts into node dicts (ids ordered by start time)
    alerts.sort(key=lambda x: (x["start_idx"], x["system"], x["tag_name"]))
    nodes: list[dict] = []
    seq = 0
    ack_users = ["r.iyer", "s.menon", "a.khan", "p.nair", "m.rao"]
    for al in alerts:
        seq += 1
        a, b = al["start_idx"], al["end_idx"]
        start_ts = _ts(axis, a)
        end_ts = _ts(axis, b)
        dur_min = round((end_ts - start_ts).total_seconds() / 60.0, 1)
        # near-anchor open alerts stay 'active'; else cleared/acknowledged
        is_open = b >= data.ctx.grid.n - 1
        status = "active" if is_open else "cleared"
        ack_by = ack_users[seq % len(ack_users)] if al["severity"] in ("high", "critical") else None
        nodes.append(dict(
            alert_id=f"ALM-{al['system'].upper()}-{seq:04d}",
            system=al["system"], tag_name=al["tag_name"], alert_type=al["alert_type"],
            severity=al["severity"], priority=al["priority"],
            message=_message(al), threshold_value=round(al["threshold_value"], 4),
            peak_value=round(al["peak_value"], 4),
            start_ts=start_ts.isoformat(), end_ts=end_ts.isoformat(),
            duration_min=dur_min, status=status, acknowledged_by=ack_by,
            acknowledged_ts=(start_ts + timedelta(minutes=8)).isoformat() if ack_by else None,
            has_telemetry=True, alert_level=al["alert_level"],
        ))

    nodes.extend(_historical_alerts(data))
    return nodes


def _message(al: dict) -> str:
    disp = SYSTEM_META[al["system"]]["display_name"]
    if al["alert_type"] == "data_quality":
        return f"{disp}: {al['tag_name']} frozen/stuck reading (sensor fault)"
    lvl = al["alert_level"].replace("_", "-").upper()
    return (f"{disp}: {al['tag_name']} {lvl} alarm "
            f"(peak {al['peak_value']:.2f}, setpoint {al['threshold_value']:.2f})")


def _historical_alerts(data: GeneratedData) -> list[dict]:
    """Older alerts (before the telemetry window) for realism; has_telemetry=false."""
    settings = data.ctx.settings
    window_start = settings.window_start
    out: list[dict] = []
    for system, count in _HISTORICAL.items():
        rng = settings.rng(system, "hist_alerts")
        alarmable = [t for t in catalog.tags_for(system)
                     if t.alarm_hi is not None or t.alarm_lo is not None]
        if not alarmable:
            continue
        for k in range(count):
            days_before = float(rng.uniform(31, 24 * 30))  # 31 days .. 24 months back
            start = window_start - timedelta(days=days_before)
            dur = float(rng.uniform(20, 480))
            end = start + timedelta(minutes=dur)
            t = alarmable[int(rng.integers(0, len(alarmable)))]
            level = "hi" if t.alarm_hi is not None else "lo"
            sev = rng.choice(["low", "medium", "high", "critical"], p=[0.35, 0.4, 0.2, 0.05])
            setp = t.alarm_hi if level == "hi" else t.alarm_lo
            peak = float(setp) * (1.05 if level == "hi" else 0.95)
            out.append(dict(
                alert_id=f"ALH-{system.upper()}-{k+1:04d}",
                system=system, tag_name=t.tag_name,
                alert_type="vibration" if t.family == "vibration" else "process",
                severity=str(sev), priority=str(sev),
                message=f"{SYSTEM_META[system]['display_name']}: historical {t.tag_name} {level} alarm",
                threshold_value=round(float(setp), 4), peak_value=round(peak, 4),
                start_ts=start.isoformat(), end_ts=end.isoformat(),
                duration_min=round(dur, 1), status="cleared",
                acknowledged_by="history", acknowledged_ts=end.isoformat(),
                has_telemetry=False, alert_level=level,
            ))
    return out
