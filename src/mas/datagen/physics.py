"""Per-tag physics: every signal is a function of a latent driver plus lag.

``generate(system, ctx)`` returns ``{tag_name: ndarray}`` of *clean* physics
values (before events and instrument noise). Values sit comfortably inside each
tag's normal band so generic tags never spuriously alarm — only the injected
events (``events.py``) push a signal across a setpoint.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import catalog
from ..catalog import SYSTEM_META, TagSpec
from . import dsp
from .modes import GenContext, OFFLINE


@dataclass(slots=True)
class Primaries:
    system: str
    n: int
    load: np.ndarray        # effective load fraction [0,1]
    nf: np.ndarray          # load normalised to peak (0..~1)
    running: np.ndarray     # 1.0 / 0.0
    speed_frac: np.ndarray  # shaft speed as fraction of rated
    flow: np.ndarray        # t/h
    q: np.ndarray           # flow / rated_flow
    efficiency: np.ndarray  # 0..1
    hour: np.ndarray
    tau_steps: float
    rated_speed: float
    rated_flow: float


def _primaries(system: str, ctx: GenContext) -> Primaries:
    meta = SYSTEM_META[system]
    load = np.clip(ctx.system_load(system), 0.0, 1.0)
    running = ctx.is_running(system).astype(float)
    nf = np.clip(load / 0.96, 0.0, 1.0)
    tau = (25 * 60) / ctx.settings.sample_seconds
    rated_speed = float(meta["rated_speed_rpm"]) or 3000.0
    rated_flow = float(meta["rated_flow_tph"]) or 300.0

    if system == "turbine":
        speed_frac = dsp.first_order_lag(running * 1.0, tau * 0.5)  # governed 3000 rpm
        flow = load * float(meta["rated_flow_tph"])
    else:
        # hydraulic-coupling / VFD: speed follows load between ~55% and 100%
        sp_target = running * (0.55 + 0.45 * nf)
        speed_frac = dsp.first_order_lag(sp_target, tau * 0.4)
        flow = np.clip(dsp.first_order_lag(load * rated_flow, tau * 0.2), 0.0, None)

    q = flow / rated_flow
    # pump/turbine efficiency curve, peaking near BEP (q≈0.8)
    eta_max = 0.85 if system != "turbine" else 0.42
    eff = eta_max - 1.1 * (q - 0.80) ** 2
    eff = np.where(running > 0, np.clip(eff, 0.05, eta_max), 0.0)
    return Primaries(system, ctx.grid.n, load, nf, running, speed_frac, flow, q,
                     eff, ctx.grid.hour, tau, rated_speed, rated_flow)


def _band(t: TagSpec, x01: np.ndarray) -> np.ndarray:
    """Map a [0,1] activity level into the tag's central normal band."""
    lo, hi = t.normal_min, t.normal_max
    return lo + (hi - lo) * (0.18 + 0.64 * np.clip(x01, 0.0, 1.0))


# ── driver handlers ──────────────────────────────────────────────────────────
def _h_ambient(t, P, ctx):
    return dsp.scale01_to(dsp.diurnal(P.hour, peak_hour=15.0), t.normal_min, t.normal_max)


def _h_thermal(t, P, ctx):
    dp = t.driver_params or {}
    amb = float(dp.get("ambient_offset", 22.0))
    lo, hi = t.normal_min, t.normal_max
    target = np.where(P.running > 0, _band(t, P.nf), lo + 0.05 * (hi - lo) + 0.0 * amb)
    tau = float(dp.get("tau_min", 25)) * 60 / ctx.settings.sample_seconds
    return dsp.first_order_lag(target, tau)


def _h_speed(t, P, ctx):
    if t.tag_name in ("speed_setpoint", "coupling_input_speed", "coupling_output_speed"):
        return P.speed_frac * P.rated_speed
    if t.tag_name == "phase_reference":
        return np.full(P.n, 180.0) + 5.0 * np.sin(np.linspace(0, 40 * np.pi, P.n))
    return P.speed_frac * P.rated_speed


def _h_load_linear(t, P, ctx):
    return _band(t, P.load)


def _h_pump_flow(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.clip(P.flow, lo, hi) if hi > lo else P.flow


def _h_suction(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    base = lo + 0.55 * (hi - lo)
    return base + 0.15 * (hi - lo) * (P.load - 0.5) * 2.0 * P.running


def _h_discharge(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    # head falls with flow^2 (pump curve): high head at low flow
    head01 = 0.35 + 0.6 * P.nf - 0.15 * P.q ** 2
    return np.where(P.running > 0, lo + (hi - lo) * np.clip(head01, 0.1, 1.0),
                    lo + 0.05 * (hi - lo))


def _h_diff(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.where(P.running > 0, lo + (hi - lo) * (0.4 + 0.5 * P.nf),
                    lo + 0.02 * (hi - lo))


def _h_stage(t, P, ctx):
    # stage index from name suffix
    try:
        idx = int(t.tag_name.rsplit("_", 1)[1])
    except ValueError:
        idx = 1
    lo, hi = t.normal_min, t.normal_max
    frac = 0.15 + 0.1 * idx
    return np.where(P.running > 0, lo + (hi - lo) * np.clip(frac + 0.3 * P.nf, 0, 1),
                    lo + 0.02 * (hi - lo))


def _h_vacuum(t, P, ctx):
    # worse vacuum (higher mbara) at higher load / lower CW; keep mid-band
    lo, hi = t.normal_min, t.normal_max
    return lo + (hi - lo) * (0.3 + 0.35 * P.load)


def _h_npsh(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.where(P.running > 0, lo + (hi - lo) * (0.6 - 0.25 * P.q + 0.2),
                    hi * 0.9)


def _h_npsh_margin(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.where(P.running > 0, lo + (hi - lo) * (0.6 - 0.2 * P.q), hi * 0.8)


def _h_seal_leakage(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return lo + (hi - lo) * (0.08 + 0.05 * P.running)


def _h_gland_seal_pressure(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return lo + (hi - lo) * (0.5 + 0.25 * P.running)


def _h_lube_oil_pressure(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    # aux oil pump keeps pressure alive even on standby
    return np.where(P.running > 0, lo + (hi - lo) * 0.65, lo + (hi - lo) * 0.45)


def _h_vibration_velocity(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    base = np.where(P.running > 0, 1.0 + 1.7 * P.nf, 0.35 * (lo + 0.5))
    return np.clip(base, lo * 0.4, None)


def _h_vibration_prox(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.where(P.running > 0, lo + (hi - lo) * (0.3 + 0.35 * P.nf),
                    lo + 0.1 * (hi - lo))


def _h_expansion(t, P, ctx):
    # differential/axial expansion tracks integral of load change during ramps
    dl = np.gradient(P.load)
    val = np.cumsum(dl) * 2.0
    lo, hi = t.normal_min, t.normal_max
    val = np.clip(val, lo, hi)
    return val * P.running + (1 - P.running) * 0.0


def _h_electrical_load(t, P, ctx):
    return _band(t, P.load)


def _h_electrical_power(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.where(P.running > 0, lo + (hi - lo) * (0.15 + 0.75 * P.nf),
                    lo + 0.01 * (hi - lo))


def _h_electrical_current(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.where(P.running > 0, lo + (hi - lo) * (0.2 + 0.7 * P.nf),
                    lo + 0.02 * (hi - lo))


def _h_electrical_voltage(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.full(P.n, lo + 0.5 * (hi - lo))


def _h_power_factor(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    return np.where(P.running > 0, lo + (hi - lo) * (0.4 + 0.5 * P.nf),
                    lo + 0.5 * (hi - lo))


def _h_frequency(t, P, ctx):
    return np.full(P.n, 50.0)


def _h_level_walk(t, P, ctx):
    rng = ctx.settings.rng(P.system, t.tag_name)
    return dsp.random_walk(rng, P.n, step=(t.normal_max - t.normal_min) * 0.002,
                           lo=t.normal_min, hi=t.normal_max)


def _h_valve_position(t, P, ctx):
    # recirc valves open at low flow; discharge valves open when running
    if "recirc" in t.tag_name or "min_flow" in t.tag_name:
        return np.clip(100.0 * (0.6 - P.q) * (P.running > 0), 0.0, 100.0)
    return np.where(P.running > 0, 85.0 + 10.0 * P.nf, 0.0)


def _h_chem_walk(t, P, ctx):
    rng = ctx.settings.rng(P.system, t.tag_name)
    mean_shift = 1.0 + 0.15 * (P.load - 0.5)
    base = dsp.random_walk(rng, P.n, step=(t.normal_max - t.normal_min) * 0.0015,
                           lo=t.normal_min, hi=t.normal_max)
    return np.clip(base * mean_shift, t.normal_min, t.normal_max)


def _h_drift_up(t, P, ctx):
    # oil water content / particle count drift up between changes (reset at maint)
    rng = ctx.settings.rng(P.system, t.tag_name)
    lo, hi = t.normal_min, t.normal_max
    ramp = np.linspace(0.2, 0.75, P.n)
    return lo + (hi - lo) * ramp + rng.normal(0, (hi - lo) * 0.01, P.n)


def _h_constant_slow(t, P, ctx):
    rng = ctx.settings.rng(P.system, t.tag_name)
    return dsp.random_walk(rng, P.n, step=(t.normal_max - t.normal_min) * 0.0005,
                           lo=t.normal_min, hi=t.normal_max)


def _h_status_running(t, P, ctx):
    return (P.running > 0).astype(float)


def _h_status_standby(t, P, ctx):
    if P.system == "turbine":
        return np.zeros(P.n)
    return ctx.duty[P.system].standby.astype(float)


def _h_status_flag(t, P, ctx):
    return np.zeros(P.n)  # baseline normal; events set alarm/trip flags


def _h_counter_hours(t, P, ctx):
    dt_h = ctx.settings.sample_seconds / 3600.0
    return 40000.0 + np.cumsum(P.running) * dt_h


def _h_counter_starts(t, P, ctx):
    starts = np.diff(np.concatenate([[0.0], (P.running > 0).astype(float)]))
    return 1200.0 + np.cumsum((starts > 0).astype(float))


def _h_efficiency(t, P, ctx):
    if t.unit == "%":
        return P.efficiency * 100.0
    return P.efficiency * 100.0


def _h_pump_head(t, P, ctx):
    rated_head = float(SYSTEM_META[P.system].get("rated_head_m") or 100.0)
    return np.where(P.running > 0, rated_head * (1.15 - 0.4 * P.q ** 2), 0.0)


def _h_hydraulic_power(t, P, ctx):
    rated_kw = float(SYSTEM_META[P.system].get("rated_power_kw") or 1000.0)
    return np.clip(rated_kw * 0.9 * P.q * (1.1 - 0.3 * P.q ** 2), 0.0, None)


def _h_heat_rate(t, P, ctx):
    lo, hi = t.normal_min, t.normal_max
    base = hi - (hi - lo) * (0.2 + 0.6 * P.load)
    return np.where(P.running > 0, base, hi)


def _h_derived_generic(t, P, ctx):
    return _band(t, P.load)


_HANDLERS = {
    "ambient": _h_ambient,
    "thermal_lag": _h_thermal,
    "speed": _h_speed,
    "load_linear": _h_load_linear,
    "pump_flow": _h_pump_flow,
    "suction_pressure": _h_suction,
    "discharge_pressure": _h_discharge,
    "diff_pressure": _h_diff,
    "stage_pressure": _h_stage,
    "vacuum": _h_vacuum,
    "npsh": _h_npsh,
    "npsh_margin": _h_npsh_margin,
    "seal_leakage": _h_seal_leakage,
    "gland_seal_pressure": _h_gland_seal_pressure,
    "lube_oil_pressure": _h_lube_oil_pressure,
    "vibration_velocity": _h_vibration_velocity,
    "vibration_prox": _h_vibration_prox,
    "expansion": _h_expansion,
    "electrical_load": _h_electrical_load,
    "electrical_power": _h_electrical_power,
    "electrical_current": _h_electrical_current,
    "electrical_voltage": _h_electrical_voltage,
    "power_factor": _h_power_factor,
    "frequency": _h_frequency,
    "level_walk": _h_level_walk,
    "valve_position": _h_valve_position,
    "chem_walk": _h_chem_walk,
    "drift_up": _h_drift_up,
    "constant_slow": _h_constant_slow,
    "status_running": _h_status_running,
    "status_standby": _h_status_standby,
    "status_flag": _h_status_flag,
    "counter_hours": _h_counter_hours,
    "counter_starts": _h_counter_starts,
    "efficiency": _h_efficiency,
    "pump_head": _h_pump_head,
    "hydraulic_power": _h_hydraulic_power,
    "heat_rate": _h_heat_rate,
    "derived_generic": _h_derived_generic,
}


def generate(system: str, ctx: GenContext) -> dict[str, np.ndarray]:
    """Clean physics values for every tag in a system (pre-event, pre-noise)."""
    P = _primaries(system, ctx)
    out: dict[str, np.ndarray] = {}
    for t in catalog.tags_for(system):
        handler = _HANDLERS.get(t.driver, _h_derived_generic)
        arr = np.asarray(handler(t, P, ctx), dtype=float)
        if arr.shape[0] != P.n:
            arr = np.full(P.n, float(np.mean(arr)))
        out[t.tag_name] = arr
    # expose primaries for downstream (clustering proxy, events)
    out["__load__"] = P.load
    return out
