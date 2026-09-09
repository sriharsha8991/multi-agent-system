"""Plant operating-mode state machine + pump duty/standby schedule.

This is the fix for MOD-04: instead of one smooth diurnal curve (which clusters
into a single blob), the plant moves through six discrete modes and the pump
pairs alternate duty/standby. That makes (load, efficiency, vibration) genuinely
separable into operating regions (gate G-18) while staying physically justified.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import Settings, get_settings
from . import dsp

# ── mode codes ───────────────────────────────────────────────────────────────
OFFLINE, STARTUP, LOW_LOAD, BASE_LOAD, PEAK_LOAD, SHUTDOWN = range(6)
MODE_NAMES = {
    OFFLINE: "OFFLINE", STARTUP: "STARTUP", LOW_LOAD: "LOW_LOAD",
    BASE_LOAD: "BASE_LOAD", PEAK_LOAD: "PEAK_LOAD", SHUTDOWN: "SHUTDOWN",
}
# target load fraction (0..1) per mode center; STARTUP/SHUTDOWN emerge from the lag
_MODE_LOAD = {OFFLINE: 0.0, STARTUP: 0.30, LOW_LOAD: 0.50, BASE_LOAD: 0.82,
              PEAK_LOAD: 0.96, SHUTDOWN: 0.15}

# duty schedule segments (start_day, end_day) and per-pump DUTY(True)/STANDBY(False)
_SEGMENTS = [
    (0.0, 8.0,  dict(bfpa=True,  bfpb=False, cepa=True,  cepb=False)),
    (8.0, 16.0, dict(bfpa=False, bfpb=True,  cepa=True,  cepb=False)),
    (16.0, 23.0, dict(bfpa=True, bfpb=False, cepa=False, cepb=True)),
    (23.0, 26.0, dict(bfpa=True, bfpb=True,  cepa=True,  cepb=True)),
    (26.0, 30.1, dict(bfpa=True, bfpb=True,  cepa=True,  cepb=True)),
]
PUMPS = ("bfpa", "bfpb", "cepa", "cepb")

# outage window (days from window start): one ~2-day planned outage
OUTAGE_START, OUTAGE_END = 6.0, 8.0


@dataclass(slots=True)
class TimeGrid:
    settings: Settings
    axis: np.ndarray          # datetime64[s], length N
    n: int
    day_float: np.ndarray     # days since window start (float)
    day_index: np.ndarray     # int day index
    hour: np.ndarray          # hour of day [0,24)
    is_weekend: np.ndarray    # bool

    @classmethod
    def build(cls, settings: Settings) -> "TimeGrid":
        axis = settings.time_axis()
        n = axis.shape[0]
        secs = (axis - axis[0]).astype("timedelta64[s]").astype(np.int64)
        day_float = secs / 86400.0
        day_index = np.floor(day_float).astype(int)
        day0 = axis[0].astype("datetime64[D]")
        hour = (axis - axis.astype("datetime64[D]")).astype("timedelta64[s]").astype(np.int64) / 3600.0
        # weekday of each timestamp: days since epoch mod 7 (1970-01-01 was Thursday=3)
        abs_day = axis.astype("datetime64[D]").astype(int)
        dow = (abs_day + 4) % 7  # 0=Mon .. 6=Sun
        is_weekend = dow >= 5
        return cls(settings, axis, n, day_float, day_index, hour, is_weekend)


@dataclass(slots=True)
class PlantProfile:
    mode: np.ndarray          # int code per step
    load: np.ndarray          # smoothed plant load fraction [0,1]


@dataclass(slots=True)
class DutyState:
    running: np.ndarray       # bool: machine energised and loaded
    standby: np.ndarray       # bool: available but not loaded
    load_share: np.ndarray    # float [0,1] fraction of full duty this machine carries


def plant_profile(grid: TimeGrid) -> PlantProfile:
    n = grid.n
    d = grid.day_float
    h = grid.hour
    mode = np.full(n, BASE_LOAD, dtype=int)

    # planned outage + transitions
    mode[(d >= OUTAGE_START - 0.25) & (d < OUTAGE_START)] = SHUTDOWN
    mode[(d >= OUTAGE_START) & (d < OUTAGE_END)] = OFFLINE
    mode[(d >= OUTAGE_END) & (d < OUTAGE_END + 0.5)] = STARTUP

    online = ~np.isin(mode, [OFFLINE, STARTUP, SHUTDOWN])

    # low-load nights (not in the final week, to keep recent data operational)
    night = (h < 5.0) | (h >= 23.0)
    mode[online & night & (grid.day_index < 23) & (grid.day_index % 2 == 0)] = LOW_LOAD

    # peak-load daytime on selected days (incl. two in the final week)
    peak_day = np.isin(grid.day_index, [2, 5, 9, 13, 17, 20, 24, 28])
    daytime = (h >= 10.0) & (h < 20.0)
    mode[online & peak_day & daytime] = PEAK_LOAD

    # target load from mode + diurnal + weekday modulation, then first-order lag
    diur = dsp.diurnal(h)
    target = np.array([_MODE_LOAD[int(m)] for m in mode])
    amp = np.where(mode == LOW_LOAD, 0.08,
          np.where(mode == BASE_LOAD, 0.08,
          np.where(mode == PEAK_LOAD, 0.04, 0.0)))
    target = target + amp * (diur - 0.5) * 2.0
    target = target * np.where(grid.is_weekend & (mode == BASE_LOAD), 0.94, 1.0)
    target = np.clip(target, 0.0, 1.0)
    # lag ~30 min so startups/shutdowns ramp smoothly rather than stepping
    tau = (30 * 60) / grid.settings.sample_seconds
    load = dsp.first_order_lag(target, tau)
    load = np.clip(load, 0.0, 1.0)
    return PlantProfile(mode=mode, load=load)


def duty_profile(grid: TimeGrid, plant: PlantProfile) -> dict[str, DutyState]:
    online = plant.mode != OFFLINE
    # per-pump duty flag per timestep from the segment schedule
    duty = {p: np.zeros(grid.n, dtype=bool) for p in PUMPS}
    both = np.zeros(grid.n, dtype=bool)
    for start, end, seg in _SEGMENTS:
        mask = (grid.day_float >= start) & (grid.day_float < end)
        n_duty = sum(1 for p in ("bfpa", "bfpb") if seg[p])
        for p in PUMPS:
            if seg[p]:
                duty[p][mask] = True
        if n_duty == 2:
            both[mask] = True

    out: dict[str, DutyState] = {}
    for p in PUMPS:
        running = online & duty[p]
        standby = ~duty[p] | (~online & duty[p])
        # both BFPs sharing → each ~0.55 of full; single duty → full load
        pair_both = both if p in ("bfpa", "bfpb") else np.zeros(grid.n, dtype=bool)
        share = np.where(running, np.where(pair_both, 0.55, 1.0), 0.0)
        out[p] = DutyState(running=running, standby=standby,
                           load_share=share * plant.load)
    return out


@dataclass(slots=True)
class GenContext:
    settings: Settings
    grid: TimeGrid
    plant: PlantProfile
    duty: dict[str, DutyState]

    def system_load(self, system: str) -> np.ndarray:
        """Effective load fraction driving a given system's physics."""
        if system == "turbine":
            return self.plant.load
        return self.duty[system].load_share

    def is_running(self, system: str) -> np.ndarray:
        if system == "turbine":
            return self.plant.mode != OFFLINE
        return self.duty[system].running


def build_context(settings: Settings | None = None) -> GenContext:
    settings = settings or get_settings()
    grid = TimeGrid.build(settings)
    plant = plant_profile(grid)
    duty = duty_profile(grid, plant)
    return GenContext(settings=settings, grid=grid, plant=plant, duty=duty)
