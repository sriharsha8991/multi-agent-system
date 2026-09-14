"""Family defaults, naming→unit/driver inference, and the shared core tag sets.

The catalog is built by *functions*, not typed out row by row: a small set of
family defaults plus name-pattern refinement produces sensible units, sensor
types, alarm setpoints and physics ``driver`` hints, and the per-system modules
(``systems.py``) call group builders to assemble each asset. Gate-critical tags
are overridden explicitly where their exact setpoints matter (e.g. the BFP-A
``bearing_temp_1`` that the flagship demo depends on).
"""

from __future__ import annotations

from typing import Any

from .spec import TagSpec

# ── plant identifiers (KKS) ──────────────────────────────────────────────────
SYSTEM_KKS: dict[str, str] = {
    "bfpa": "LAC10",
    "bfpb": "LAC20",
    "cepa": "LCB10",
    "cepb": "LCB20",
    "turbine": "MAA10",
}
SYSTEM_DISPLAY: dict[str, str] = {
    "bfpa": "BFP-A",
    "bfpb": "BFP-B",
    "cepa": "CEP-A",
    "cepb": "CEP-B",
    "turbine": "Steam Turbine",
}

# ISA-5.1 instrument letters, by family, for the generated KKS tag suffix.
ISA_LETTER: dict[str, str] = {
    "pressure": "CP",
    "temperature": "CT",
    "flow": "CF",
    "vibration": "CY",
    "speed": "CS",
    "level": "CL",
    "electrical": "CE",
    "chemistry": "CQ",
    "derived": "Calc",
    "status": "GH",
}

# ── family defaults ──────────────────────────────────────────────────────────
# Each: unit, sensor_type, precision, noise_sigma, normal_min, normal_max,
# alarm_lolo, alarm_lo, alarm_hi, alarm_hihi, driver, is_derived
FAMILY_DEFAULTS: dict[str, dict[str, Any]] = {
    "pressure": dict(unit="bar", sensor_type="pressure_transmitter", precision=0.01,
                     noise_sigma=0.03, normal_min=1.0, normal_max=15.0,
                     alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                     driver="load_linear", is_derived=False),
    "temperature": dict(unit="degC", sensor_type="RTD_PT100", precision=0.1,
                        noise_sigma=0.15, normal_min=30.0, normal_max=80.0,
                        alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                        driver="thermal_lag", is_derived=False),
    "flow": dict(unit="t/h", sensor_type="flow_transmitter", precision=0.1,
                 noise_sigma=0.4, normal_min=0.0, normal_max=300.0,
                 alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                 driver="load_linear", is_derived=False),
    "vibration": dict(unit="mm/s", sensor_type="accelerometer", precision=0.01,
                      noise_sigma=0.05, normal_min=0.5, normal_max=4.5,
                      alarm_lolo=None, alarm_lo=None, alarm_hi=4.5, alarm_hihi=7.1,
                      driver="vibration_velocity", is_derived=False),
    "speed": dict(unit="rpm", sensor_type="speed_transmitter", precision=1.0,
                  noise_sigma=2.0, normal_min=0.0, normal_max=6000.0,
                  alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                  driver="speed", is_derived=False),
    "level": dict(unit="%", sensor_type="level_transmitter", precision=0.1,
                  noise_sigma=0.25, normal_min=20.0, normal_max=80.0,
                  alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                  driver="level_walk", is_derived=False),
    "electrical": dict(unit="A", sensor_type="transducer", precision=0.1,
                       noise_sigma=0.5, normal_min=0.0, normal_max=500.0,
                       alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                       driver="electrical_load", is_derived=False),
    "chemistry": dict(unit="uS/cm", sensor_type="analyzer", precision=0.01,
                      noise_sigma=0.01, normal_min=0.05, normal_max=0.5,
                      alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                      driver="chem_walk", is_derived=False),
    "derived": dict(unit="", sensor_type="calculated", precision=0.01,
                    noise_sigma=0.0, normal_min=0.0, normal_max=100.0,
                    alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                    driver="derived_generic", is_derived=True),
    "status": dict(unit="bool", sensor_type="digital", precision=1.0,
                   noise_sigma=0.0, normal_min=0.0, normal_max=1.0,
                   alarm_lolo=None, alarm_lo=None, alarm_hi=None, alarm_hihi=None,
                   driver="status_flag", is_derived=False),
}


def _refine(name: str, family: str, d: dict[str, Any]) -> dict[str, Any]:
    """Name-pattern refinement of unit / sensor_type / driver / ranges."""
    n = name

    # temperature specialisations
    if family == "temperature":
        if n == "ambient_temp":
            d.update(driver="ambient", normal_min=15.0, normal_max=35.0,
                     alarm_hi=None, alarm_hihi=None)
        if "bearing_temp" in n or "guide_bearing" in n or "thrust_bearing" in n:
            d.update(normal_min=45.0, normal_max=85.0, alarm_hi=90.0, alarm_hihi=100.0)
        if "winding_temp" in n or "stator_winding" in n:
            d.update(normal_min=55.0, normal_max=110.0, alarm_hi=120.0, alarm_hihi=130.0)
        if "steam_temp" in n or n in ("main_steam_temp", "hp_inlet_temp", "reheat_inlet_temp"):
            d.update(sensor_type="thermocouple_K", normal_min=180.0, normal_max=540.0,
                     precision=0.5, noise_sigma=0.6, alarm_hi=545.0, alarm_hihi=560.0)

    # pressure specialisations
    if family == "pressure":
        if "vacuum" in n:
            d.update(unit="mbara", normal_min=40.0, normal_max=120.0, precision=0.1,
                     noise_sigma=0.3, driver="vacuum")
        elif "_dp" in n or "differential_pressure" in n or "strainer" in n or "filter_dp" in n:
            d.update(normal_min=0.1, normal_max=1.5, precision=0.001, noise_sigma=0.01,
                     driver="load_linear", alarm_hi=1.6, alarm_hihi=2.0)
        elif "main_steam" in n or "hp_inlet" in n or "throttle" in n:
            d.update(normal_min=20.0, normal_max=170.0, precision=0.05, noise_sigma=0.1)
        elif "suction" in n:
            d.update(normal_min=3.0, normal_max=12.0, driver="suction_pressure")
        elif "discharge" in n:
            d.update(normal_min=60.0, normal_max=185.0, precision=0.05, noise_sigma=0.1,
                     driver="discharge_pressure")
        elif "stage_pressure" in n:
            d.update(normal_min=10.0, normal_max=180.0, precision=0.05, driver="stage_pressure")

    # flow specialisations
    if family == "flow":
        if n == "flow_rate" or "feed_flow" in n or "condensate_flow" in n:
            d.update(driver="pump_flow", normal_min=0.0, normal_max=320.0)
        elif "steam_flow" in n or "throttle_flow" in n:
            d.update(driver="load_linear", normal_min=0.0, normal_max=900.0)
        elif "seal" in n or "leakage" in n or "leakoff" in n:
            d.update(unit="lpm", normal_min=0.0, normal_max=8.0, precision=0.01,
                     noise_sigma=0.02)
        elif "oil_flow" in n:
            d.update(unit="lpm", normal_min=20.0, normal_max=120.0, precision=0.1)

    # vibration: proximity probes read displacement (um); casings read velocity (mm/s)
    if family == "vibration":
        if "_x_" in n or "_y_" in n or n in ("shaft_deflection",):
            d.update(unit="um", sensor_type="proximity_probe", precision=0.1,
                     noise_sigma=0.8, normal_min=5.0, normal_max=60.0,
                     alarm_hi=90.0, alarm_hihi=150.0, driver="vibration_prox")
        elif n == "vibration_overall" or "casing_vibration" in n or "column_vibration" in n \
                or n.endswith("_vibration") or "vibration_de" in n or "vibration_nde" in n \
                or "line_shaft_vibration" in n or "motor_stool" in n:
            d.update(unit="mm/s", driver="vibration_velocity")

    # rotor / expansion mechanicals live in the vibration family here
    if n in ("eccentricity", "shaft_eccentricity"):
        d.update(unit="um", family_hint="mech", precision=0.1, noise_sigma=0.5,
                 normal_min=10.0, normal_max=50.0, alarm_hi=80.0, alarm_hihi=120.0,
                 driver="vibration_prox")
    if "axial" in n or "expansion" in n or "displacement" in n or n in ("thrust_position", "rotor_position"):
        d.update(unit="mm", precision=0.01, noise_sigma=0.02, normal_min=-1.0,
                 normal_max=1.0, driver="expansion",
                 alarm_hi=None, alarm_hihi=None, alarm_lo=None, alarm_lolo=None)

    # electrical specialisations
    if family == "electrical":
        if "voltage" in n:
            d.update(unit="V", normal_min=6200.0, normal_max=6800.0, precision=1.0,
                     noise_sigma=3.0, driver="electrical_voltage")
        elif "power_factor" in n:
            d.update(unit="", normal_min=0.80, normal_max=0.95, precision=0.001,
                     noise_sigma=0.002, driver="power_factor")
        elif "frequency" in n:
            d.update(unit="Hz", normal_min=49.8, normal_max=50.2, precision=0.01,
                     noise_sigma=0.01, driver="frequency")
        elif "insulation" in n or "resistance" in n:
            d.update(unit="Mohm", normal_min=50.0, normal_max=500.0, precision=1.0,
                     noise_sigma=2.0, driver="constant_slow")
        elif "reactive" in n or n == "mvar":
            d.update(unit="MVAr", normal_min=-20.0, normal_max=80.0, driver="electrical_load")
        elif "gross_power" in n or n == "gross_mw":
            d.update(unit="MW", normal_min=0.0, normal_max=250.0, driver="electrical_load")
        elif "rotor_current" in n:
            d.update(unit="A", normal_min=0.0, normal_max=2500.0, driver="electrical_load")
        elif "power" in n:
            d.update(unit="kW", normal_min=0.0, normal_max=9000.0, driver="electrical_power")
        elif "current" in n:
            d.update(unit="A", normal_min=0.0, normal_max=600.0, driver="electrical_current")

    # speed specialisations
    if family == "speed":
        if "setpoint" in n:
            d.update(driver="load_linear")

    # level specialisations
    if family == "level":
        if "hotwell" in n:
            d.update(unit="mm", normal_min=300.0, normal_max=900.0, precision=1.0,
                     noise_sigma=2.0)
        elif "tank_level" in n or "oil_level" in n or "oil_tank" in n:
            d.update(normal_min=40.0, normal_max=90.0)

    # chemistry specialisations
    if family == "chemistry":
        if n.endswith("_ph"):
            d.update(unit="pH", normal_min=8.8, normal_max=9.4, precision=0.01,
                     noise_sigma=0.02)
        elif "conductivity" in n:
            d.update(unit="uS/cm", normal_min=0.05, normal_max=0.35, precision=0.001,
                     noise_sigma=0.005)
        elif "oxygen" in n:
            d.update(unit="ppb", normal_min=2.0, normal_max=20.0, precision=0.1,
                     noise_sigma=0.3)
        elif "silica" in n:
            d.update(unit="ppb", normal_min=2.0, normal_max=20.0, precision=0.1)
        elif "iron" in n:
            d.update(unit="ppb", normal_min=1.0, normal_max=15.0, precision=0.1)
        elif "sodium" in n:
            d.update(unit="ppb", normal_min=1.0, normal_max=10.0, precision=0.1)
        elif "water_content" in n:
            d.update(unit="ppm", normal_min=50.0, normal_max=400.0, precision=1.0,
                     driver="drift_up")
        elif "particle_count" in n:
            d.update(unit="count/ml", normal_min=100.0, normal_max=2000.0, precision=1.0,
                     driver="drift_up")
        elif "purity" in n:
            d.update(unit="%", normal_min=95.0, normal_max=99.5, precision=0.1)
        elif "air_ingress" in n:
            d.update(unit="index", normal_min=0.0, normal_max=1.0, precision=0.01)

    # valve / scoop position → percent open (NOT thrust/rotor position, which are mm)
    if ("valve" in n and "position" in n) or "scoop_position" in n:
        d.update(unit="%", family="level", normal_min=0.0, normal_max=100.0,
                 precision=0.1, noise_sigma=0.3, driver="valve_position",
                 alarm_hi=None, alarm_hihi=None)

    # status specialisations
    if family == "status":
        if "running" in n and "hours" not in n:
            d.update(driver="status_running")
        elif "standby" in n:
            d.update(driver="status_standby")
        elif n in ("auto_mode", "on_load", "recirc_valve_open", "barring_gear_engaged",
                   "turning_gear_running", "aux_oil_pump_running"):
            d.update(driver="status_running")
        else:  # trip_status, alarm_active, etc: mostly 0
            d.update(driver="status_flag")

    # counters
    if n == "running_hours":
        d.update(unit="h", family="derived", is_derived=True, normal_min=0.0,
                 normal_max=1e6, precision=0.01, driver="counter_hours")
    if n == "start_count":
        d.update(unit="count", family="derived", is_derived=True, normal_min=0.0,
                 normal_max=1e5, precision=1.0, driver="counter_starts")

    d.pop("family_hint", None)
    return d


def make_tag(system: str, name: str, family: str, description: str | None = None,
             **overrides: Any) -> TagSpec:
    """Build one fully-populated ``TagSpec`` from family defaults + refinement."""
    if family not in FAMILY_DEFAULTS:
        raise ValueError(f"unknown family {family!r} for tag {name!r}")
    d: dict[str, Any] = dict(FAMILY_DEFAULTS[family])
    d = _refine(name, family, d)
    fam = d.pop("family", family)
    driver = d.pop("driver")
    is_derived = d.pop("is_derived")
    # explicit caller overrides win over inference
    d.update(overrides)
    driver = overrides.get("driver", driver)
    fam = overrides.get("family", fam)
    is_derived = overrides.get("is_derived", is_derived)
    for k in ("driver", "family", "is_derived"):
        d.pop(k, None)

    # temperature tags without an explicit setpoint get alarms relative to their
    # own range, so the normal operating band can never spuriously alarm — only
    # an injected event pushes them across.
    if fam == "temperature":
        nmin = d.get("normal_min", 0.0)
        nmax = d.get("normal_max", 100.0)
        span = max(nmax - nmin, 1.0)
        if d.get("alarm_hi") is None and name != "ambient_temp":
            d["alarm_hi"] = round(nmax + max(0.10 * span, 3.0), 1)
        if d.get("alarm_hihi") is None and name != "ambient_temp":
            d["alarm_hihi"] = round(nmax + max(0.20 * span, 6.0), 1)

    if description is None:
        description = f"{SYSTEM_DISPLAY[system]} {name.replace('_', ' ')}"

    return TagSpec(
        tag_name=name, system=system, family=fam, driver=driver,
        is_derived=is_derived, description=description,
        driver_params=overrides.get("driver_params", {}),
        unit=d.get("unit", ""), sensor_type=d.get("sensor_type", ""),
        precision=d.get("precision", 0.1), noise_sigma=d.get("noise_sigma", 0.1),
        normal_min=d.get("normal_min", 0.0), normal_max=d.get("normal_max", 100.0),
        alarm_lolo=d.get("alarm_lolo"), alarm_lo=d.get("alarm_lo"),
        alarm_hi=d.get("alarm_hi"), alarm_hihi=d.get("alarm_hihi"),
        location=d.get("location", ""),
    )


def assign_kks(tags: list[TagSpec]) -> None:
    """Populate ``kks_tag`` deterministically from system KKS + ISA letter + index."""
    counters: dict[str, int] = {}
    base = SYSTEM_KKS[tags[0].system] if tags else ""
    for t in tags:
        letter = ISA_LETTER.get(t.family, "CX")
        counters[letter] = counters.get(letter, 0) + 1
        t.kks_tag = f"{base} {letter}{counters[letter]:03d}"


# ── shared core sets ─────────────────────────────────────────────────────────
def universal_core(system: str) -> list[TagSpec]:
    """15 tags present with identical names/units on every system (§5.1)."""
    disp = SYSTEM_DISPLAY[system]
    return [
        make_tag(system, "bearing_temp_1", "temperature",
                 f"{disp} bearing #1 metal temperature", location="drive_end"),
        make_tag(system, "bearing_temp_2", "temperature",
                 f"{disp} bearing #2 metal temperature", location="non_drive_end"),
        make_tag(system, "bearing_temp_3", "temperature",
                 f"{disp} bearing #3 metal temperature"),
        make_tag(system, "bearing_temp_4", "temperature",
                 f"{disp} bearing #4 metal temperature"),
        make_tag(system, "vibration_x_1", "vibration",
                 f"{disp} bearing #1 shaft vibration X"),
        make_tag(system, "vibration_y_1", "vibration",
                 f"{disp} bearing #1 shaft vibration Y"),
        make_tag(system, "vibration_x_2", "vibration",
                 f"{disp} bearing #2 shaft vibration X"),
        make_tag(system, "vibration_y_2", "vibration",
                 f"{disp} bearing #2 shaft vibration Y"),
        make_tag(system, "vibration_overall", "vibration",
                 f"{disp} overall casing vibration velocity"),
        make_tag(system, "vibration_axial", "vibration",
                 f"{disp} overall axial vibration velocity"),
        make_tag(system, "shaft_speed", "speed", f"{disp} shaft rotational speed"),
        make_tag(system, "lube_oil_pressure", "pressure",
                 f"{disp} lube oil header pressure", normal_min=1.5, normal_max=3.0,
                 alarm_lo=1.2, alarm_lolo=0.9, driver="lube_oil_pressure"),
        make_tag(system, "lube_oil_temp", "temperature",
                 f"{disp} lube oil supply temperature", normal_min=35.0, normal_max=55.0,
                 alarm_hi=60.0, alarm_hihi=65.0),
        make_tag(system, "lube_oil_level", "level", f"{disp} lube oil tank level"),
        make_tag(system, "ambient_temp", "temperature", f"{disp} ambient air temperature"),
    ]


def pump_core(system: str) -> list[TagSpec]:
    """10 tags present with identical names/units on the four pumps (§5.1)."""
    disp = SYSTEM_DISPLAY[system]
    return [
        make_tag(system, "suction_pressure", "pressure", f"{disp} suction pressure"),
        make_tag(system, "discharge_pressure", "pressure", f"{disp} discharge pressure"),
        make_tag(system, "differential_pressure", "pressure",
                 f"{disp} differential pressure", driver="diff_pressure"),
        make_tag(system, "flow_rate", "flow", f"{disp} feedwater flow rate"),
        make_tag(system, "motor_current", "electrical", f"{disp} motor current"),
        make_tag(system, "motor_power", "electrical", f"{disp} motor active power"),
        make_tag(system, "motor_voltage", "electrical", f"{disp} motor terminal voltage"),
        make_tag(system, "winding_temp_1", "temperature", f"{disp} motor winding U temperature"),
        make_tag(system, "winding_temp_2", "temperature", f"{disp} motor winding V temperature"),
        make_tag(system, "winding_temp_3", "temperature", f"{disp} motor winding W temperature"),
    ]
