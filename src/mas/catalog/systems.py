"""Per-system tag assembly → exactly 130 / 130 / 108 / 108 / 160 = 636 tags.

Group sizes follow doc 02 §5.2. Each group is built from name lists via the
family helpers; gate-critical setpoints/drivers are set with explicit overrides.
"""

from __future__ import annotations

from .families import assign_kks, make_tag, pump_core, universal_core
from .spec import TagSpec

# expected per-system counts — asserted after assembly (also gate G-02)
EXPECTED_COUNTS: dict[str, int] = {
    "bfpa": 130, "bfpb": 130, "cepa": 108, "cepb": 108, "turbine": 160,
}


def _rng(prefix: str, a: int, b: int) -> list[str]:
    return [f"{prefix}{i}" for i in range(a, b + 1)]


class _Builder:
    """Small DSL: family helpers that append fully-built tags for one system."""

    def __init__(self, system: str) -> None:
        self.system = system
        self.tags: list[TagSpec] = []

    def add(self, name: str, family: str, **ov) -> None:
        self.tags.append(make_tag(self.system, name, family, **ov))

    # family shortcuts
    def T(self, *names, **ov): [self.add(n, "temperature", **ov) for n in names]
    def P(self, *names, **ov): [self.add(n, "pressure", **ov) for n in names]
    def F(self, *names, **ov): [self.add(n, "flow", **ov) for n in names]
    def V(self, *names, **ov): [self.add(n, "vibration", **ov) for n in names]
    def SPD(self, *names, **ov): [self.add(n, "speed", **ov) for n in names]
    def L(self, *names, **ov): [self.add(n, "level", **ov) for n in names]
    def E(self, *names, **ov): [self.add(n, "electrical", **ov) for n in names]
    def C(self, *names, **ov): [self.add(n, "chemistry", **ov) for n in names]
    def D(self, *names, **ov): [self.add(n, "derived", **ov) for n in names]
    def St(self, *names, **ov): [self.add(n, "status", **ov) for n in names]

    def result(self) -> list[TagSpec]:
        assign_kks(self.tags)
        return self.tags


def _pump_common(b: _Builder) -> None:
    """Shared derived + status groups common to all four pumps."""
    b.D("pump_head", driver="pump_head")
    b.D("hydraulic_power", driver="hydraulic_power")
    b.D("pump_efficiency", driver="efficiency")
    b.D("specific_energy", "flow_deviation_from_bep", "vibration_severity_zone",
        "bearing_temp_margin", "health_index", "power_consumed", "cavitation_index")
    b.D("running_hours", "start_count")
    b.St("pump_running", "standby_mode", "auto_mode", "trip_status", "alarm_active",
         "recirc_valve_open", "aux_oil_pump_running")


def build_bfp(system: str) -> list[TagSpec]:
    """Boiler feed pump — multistage centrifugal, motor + hydraulic coupling (130)."""
    b = _Builder(system)
    b.tags.extend(universal_core(system))   # 15
    b.tags.extend(pump_core(system))        # 10

    # Bearings extended (10)
    b.T(*_rng("bearing_temp_", 5, 8))
    b.T("thrust_bearing_temp_active", "thrust_bearing_temp_inactive")
    b.V(*_rng("bearing_vibration_", 1, 4))

    # Stage pressures (8)
    b.P(*_rng("stage_pressure_", 1, 8))

    # Process (13)
    b.F("recirc_flow")
    b.L("min_flow_valve_position", "discharge_valve_position")
    b.P("suction_strainer_dp")
    b.P("npsh_available", unit="m", normal_min=6.0, normal_max=18.0, driver="npsh",
        alarm_lo=4.0, alarm_lolo=2.5)
    b.P("npsh_margin", unit="m", normal_min=3.0, normal_max=12.0, driver="npsh_margin",
        alarm_lo=1.5, alarm_lolo=0.5)
    b.F("balance_leakoff_flow")
    b.T("balance_leakoff_temp")
    b.T("suction_temp", normal_min=140.0, normal_max=180.0, alarm_hi=190.0, alarm_hihi=200.0)
    b.T("discharge_temp", normal_min=150.0, normal_max=195.0, alarm_hi=205.0, alarm_hihi=215.0)
    b.T("temp_rise", normal_min=2.0, normal_max=18.0, driver="derived_generic", is_derived=True)
    b.L("deaerator_level")
    b.P("deaerator_pressure", normal_min=5.0, normal_max=12.0)

    # Seals (5)
    b.P("gland_seal_pressure", normal_min=1.0, normal_max=4.0, driver="gland_seal_pressure",
        alarm_lo=1.2, alarm_lolo=0.8)
    b.F("gland_seal_flow")
    b.T("mech_seal_temp_1", "mech_seal_temp_2")
    b.F("seal_leakage_rate", driver="seal_leakage", alarm_hi=4.0, alarm_hihi=6.0)

    # Lube oil extended (9)
    b.P("lube_oil_filter_dp")
    b.T("lube_oil_supply_temp", "lube_oil_return_temp", "lube_oil_cooler_inlet_temp",
        "lube_oil_cooler_outlet_temp")
    b.F("lube_oil_flow")
    b.C("lube_oil_water_content", "lube_oil_particle_count")
    b.P("aux_oil_pump_pressure", normal_min=1.5, normal_max=3.5)

    # Motor extended (18)
    b.E(*_rng("motor_current_phase_", 1, 3))
    b.E(*_rng("motor_voltage_phase_", 1, 3))
    b.E("motor_power_factor", "motor_frequency")
    b.T("motor_bearing_temp_de", "motor_bearing_temp_nde")
    b.V("motor_vibration_de", "motor_vibration_nde")
    b.T("motor_cooling_air_inlet_temp", "motor_cooling_air_outlet_temp")
    b.E("motor_insulation_resistance")
    b.T(*_rng("winding_temp_", 4, 6))

    # Hydraulic coupling (5)
    b.L("coupling_scoop_position")
    b.T("coupling_oil_temp")
    b.D("coupling_slip", unit="%", normal_min=1.0, normal_max=6.0)
    b.SPD("coupling_input_speed", "coupling_output_speed", normal_max=6000.0)

    # Booster pump (7)
    b.P("booster_suction_pressure", normal_min=3.0, normal_max=10.0,
        driver="suction_pressure")
    b.P("booster_discharge_pressure", normal_min=15.0, normal_max=45.0,
        driver="discharge_pressure")
    b.F("booster_flow")
    b.E("booster_motor_current")
    b.T("booster_bearing_temp_1", "booster_bearing_temp_2")
    b.V("booster_vibration")

    # Water chemistry (5)
    b.C("feedwater_conductivity", "feedwater_ph", "feedwater_dissolved_oxygen",
        "feedwater_silica", "feedwater_iron")

    # Rotor / mechanical (6)
    b.V("axial_displacement", "shaft_eccentricity", "thrust_position")
    b.V("casing_vibration_h", "casing_vibration_v", "casing_vibration_a")

    # Derived (12) + Status (7)
    _pump_common(b)

    return b.result()


def build_cep(system: str) -> list[TagSpec]:
    """Condensate extraction pump — vertical can pump under condenser vacuum (108)."""
    b = _Builder(system)
    b.tags.extend(universal_core(system))   # 15
    b.tags.extend(pump_core(system))        # 10

    # Vertical-pump specifics (10)
    b.T("upper_guide_bearing_temp", "lower_guide_bearing_temp", "thrust_bearing_temp")
    b.V(*_rng("column_vibration_", 1, 3))
    b.V("motor_stool_vibration")
    b.V("shaft_deflection")
    b.T("bowl_assembly_temp")
    b.V("line_shaft_vibration")

    # Stage pressures (4)
    b.P(*_rng("stage_pressure_", 1, 4), normal_min=1.0, normal_max=45.0)

    # Condenser / vacuum (8)
    b.L("hotwell_level")
    b.P("condenser_vacuum", driver="vacuum")
    b.P("condenser_pressure", normal_min=0.04, normal_max=0.12, precision=0.001,
        noise_sigma=0.002)
    b.T("condensate_temp", normal_min=30.0, normal_max=55.0)
    b.C("air_ingress_rate")
    b.T("cw_inlet_temp", normal_min=20.0, normal_max=35.0)
    b.T("cw_outlet_temp", normal_min=28.0, normal_max=45.0)
    b.T("condenser_ttd", normal_min=2.0, normal_max=8.0, driver="derived_generic",
        is_derived=True)

    # Process (9)
    b.F("recirc_flow")
    b.L("min_flow_valve_position", "discharge_valve_position")
    b.P("npsh_available", unit="m", normal_min=3.0, normal_max=12.0, driver="npsh",
        alarm_lo=2.0, alarm_lolo=1.0)
    b.P("npsh_margin", unit="m", normal_min=1.5, normal_max=8.0, driver="npsh_margin",
        alarm_lo=0.8, alarm_lolo=0.3)
    b.D("cavitation_index")
    b.P("suction_pressure_abs", unit="mbara", normal_min=40.0, normal_max=120.0,
        driver="vacuum")
    b.T("discharge_temp", normal_min=30.0, normal_max=55.0)
    b.L("deaerator_level")

    # Condensate chemistry (5)
    b.C("condensate_conductivity", "condensate_ph", "dissolved_oxygen", "sodium_content",
        "condensate_iron")

    # Seals / gland (4)
    b.F("gland_seal_water_flow")
    b.P("gland_seal_water_pressure", normal_min=1.0, normal_max=4.0)
    b.T("mech_seal_temp")
    b.F("seal_leakage_rate", driver="seal_leakage", alarm_hi=4.0, alarm_hihi=6.0)

    # Lube oil (7)
    b.P("lube_oil_filter_dp")
    b.T("lube_oil_supply_temp", "lube_oil_return_temp")
    b.F("lube_oil_flow")
    b.C("lube_oil_water_content", "lube_oil_particle_count")
    b.P("aux_oil_pump_pressure", normal_min=1.5, normal_max=3.5)

    # Motor extended (16)
    b.E(*_rng("motor_current_phase_", 1, 3))
    b.E(*_rng("motor_voltage_phase_", 1, 3))
    b.E("motor_power_factor", "motor_frequency")
    b.T("motor_bearing_temp_de", "motor_bearing_temp_nde")
    b.V("motor_vibration_de", "motor_vibration_nde")
    b.T("motor_cooling_air_inlet_temp", "motor_cooling_air_outlet_temp")
    b.E("motor_insulation_resistance")
    b.E("motor_reactive_power", unit="kVAr", normal_min=0.0, normal_max=400.0,
        driver="electrical_load")

    # Derived (13)
    b.D("pump_head", driver="pump_head")
    b.D("hydraulic_power", driver="hydraulic_power")
    b.D("pump_efficiency", driver="efficiency")
    b.D("specific_energy", "flow_deviation_from_bep", "vibration_severity_zone",
        "bearing_temp_margin", "health_index", "power_consumed")
    b.D("running_hours", "start_count")
    b.D("vacuum_margin", "subcooling")

    # Status (7)
    b.St("pump_running", "standby_mode", "auto_mode", "trip_status", "alarm_active",
         "recirc_valve_open", "aux_oil_pump_running")

    return b.result()


def build_turbine(system: str = "turbine") -> list[TagSpec]:
    """Steam turbine + generator, 3000 rpm (160)."""
    b = _Builder(system)
    b.tags.extend(universal_core(system))   # 15

    # Bearings extended (20) — 8-pedestal machine
    b.T(*_rng("bearing_temp_", 5, 10))
    b.T("thrust_bearing_temp_active", "thrust_bearing_temp_inactive")
    b.V(*_rng("bearing_vibration_x_", 3, 8))
    b.V(*_rng("bearing_vibration_y_", 3, 8))

    # Steam path (28)
    b.P("main_steam_pressure")
    b.T("main_steam_temp")
    b.F("main_steam_flow")
    b.P("hp_inlet_pressure"); b.T("hp_inlet_temp")
    b.P("hp_exhaust_pressure", normal_min=20.0, normal_max=45.0); b.T("hp_exhaust_temp",
        normal_min=280.0, normal_max=360.0)
    b.P("reheat_inlet_pressure", normal_min=20.0, normal_max=45.0); b.T("reheat_inlet_temp")
    b.P("ip_inlet_pressure", normal_min=18.0, normal_max=42.0); b.T("ip_inlet_temp")
    b.P("ip_exhaust_pressure", normal_min=3.0, normal_max=12.0); b.T("ip_exhaust_temp",
        normal_min=180.0, normal_max=320.0)
    b.P("lp_inlet_pressure", normal_min=3.0, normal_max=12.0); b.T("lp_inlet_temp",
        normal_min=180.0, normal_max=320.0)
    b.P("lp_exhaust_pressure", unit="mbara", normal_min=40.0, normal_max=120.0,
        driver="vacuum"); b.T("lp_exhaust_temp", normal_min=30.0, normal_max=60.0)
    b.F("throttle_flow")
    b.P(*_rng("extraction_pressure_", 1, 5), normal_min=1.0, normal_max=40.0)
    b.T(*_rng("extraction_temp_", 1, 5), normal_min=120.0, normal_max=400.0)

    # Governor / valves (12)
    b.L(*_rng("gov_valve_position_", 1, 4))
    b.L(*_rng("stop_valve_position_", 1, 2))
    b.L("reheat_stop_valve_position")
    b.L(*_rng("intercept_valve_position_", 1, 2))
    b.SPD("speed_setpoint", normal_max=3300.0)
    b.E("load_setpoint", unit="MW", normal_min=0.0, normal_max=250.0, driver="load_linear")
    b.P("governor_oil_pressure", normal_min=8.0, normal_max=16.0)

    # Rotor / expansion (9)
    b.V("eccentricity")
    b.V("axial_shift")
    b.V("differential_expansion_hp", "differential_expansion_ip", "differential_expansion_lp")
    b.V("casing_expansion_1", "casing_expansion_2")
    b.V("rotor_position")
    b.SPD("phase_reference", unit="deg", normal_min=0.0, normal_max=360.0,
          driver="derived_generic")

    # Oil systems (11)
    b.P("control_oil_pressure", normal_min=8.0, normal_max=16.0)
    b.P(*_rng("jacking_oil_pressure_", 1, 4), normal_min=100.0, normal_max=160.0)
    b.L("lube_oil_tank_level")
    b.T("lube_oil_tank_temp", normal_min=35.0, normal_max=55.0)
    b.P("lube_oil_filter_dp")
    b.T("lube_oil_cooler_outlet_temp", normal_min=35.0, normal_max=50.0)
    b.P("aux_oil_pump_pressure", normal_min=1.5, normal_max=3.5)
    b.St("emergency_oil_pump_running")

    # Condenser / CW (8)
    b.P("condenser_vacuum", driver="vacuum", normal_min=45.0, normal_max=90.0,
        alarm_hi=100.0, alarm_hihi=115.0)
    b.P("condenser_pressure", normal_min=0.04, normal_max=0.12, precision=0.001,
        noise_sigma=0.002)
    b.L("hotwell_level")
    b.T("cw_inlet_temp", normal_min=20.0, normal_max=35.0)
    b.T("cw_outlet_temp", normal_min=28.0, normal_max=45.0)
    b.T("condenser_ttd", normal_min=2.0, normal_max=8.0, driver="derived_generic",
        is_derived=True)
    b.F("air_ejector_flow", unit="kg/h", normal_min=5.0, normal_max=60.0)
    b.F("cooling_water_flow", normal_max=40000.0)

    # Generator (28)
    b.E("gross_power", unit="MW", normal_min=0.0, normal_max=250.0, driver="electrical_load")
    b.E("reactive_power", unit="MVAr", normal_min=-20.0, normal_max=90.0,
        driver="electrical_load")
    b.E(*_rng("stator_current_", 1, 3), unit="A", normal_min=0.0, normal_max=9000.0)
    b.E(*_rng("stator_voltage_", 1, 3))
    b.T(*_rng("stator_winding_temp_", 1, 6), normal_min=55.0, normal_max=110.0,
        alarm_hi=120.0, alarm_hihi=130.0)
    b.T(*_rng("stator_core_temp_", 1, 2), normal_min=55.0, normal_max=105.0)
    b.E("rotor_current")
    b.E("rotor_voltage")
    b.P("h2_pressure", normal_min=2.0, normal_max=4.0)
    b.C("h2_purity")
    b.T("h2_temp", normal_min=30.0, normal_max=50.0)
    b.P("seal_oil_pressure", normal_min=3.0, normal_max=6.0)
    b.T("seal_oil_temp", normal_min=30.0, normal_max=50.0)
    b.T("exciter_temp", normal_min=40.0, normal_max=90.0)
    b.T("generator_bearing_temp_1", "generator_bearing_temp_2")
    b.E("frequency")
    b.E("power_factor")

    # Performance (8)
    b.D("heat_rate", unit="kJ/kWh", normal_min=7500.0, normal_max=11000.0, driver="heat_rate")
    b.D("hp_efficiency", "ip_efficiency", "lp_efficiency", unit="%", normal_min=70.0,
        normal_max=92.0, driver="efficiency")
    b.D("steam_rate", unit="kg/kWh", normal_min=3.0, normal_max=6.0)
    b.P("backpressure", unit="kPa", normal_min=4.0, normal_max=12.0, driver="vacuum")
    b.D("vacuum_loss", unit="mbar", normal_min=0.0, normal_max=30.0)
    b.D("cycle_efficiency", unit="%", normal_min=30.0, normal_max=45.0, driver="efficiency")

    # Steam/aux extended (14) — brings the total to the design's 160
    b.P("gland_steam_pressure", normal_min=0.1, normal_max=1.5)
    b.T("gland_steam_temp", normal_min=120.0, normal_max=280.0)
    b.T("lp_hood_temp_1", "lp_hood_temp_2", normal_min=30.0, normal_max=80.0,
        alarm_hi=90.0, alarm_hihi=110.0)
    b.F("lp_spray_flow", unit="t/h", normal_min=0.0, normal_max=20.0)
    b.P("crossover_pressure", normal_min=3.0, normal_max=14.0)
    b.T("crossover_temp", normal_min=180.0, normal_max=340.0)
    b.F("stator_coolant_flow", unit="l/min", normal_min=200.0, normal_max=600.0)
    b.T("stator_coolant_temp", normal_min=30.0, normal_max=60.0)
    b.T("h2_cooler_outlet_temp", normal_min=25.0, normal_max=45.0)
    b.V("generator_vibration_de", "generator_vibration_nde")
    b.T("exhaust_hood_temp", normal_min=30.0, normal_max=80.0)
    b.F("condensate_makeup_flow", unit="t/h", normal_min=0.0, normal_max=30.0)

    # Status (7)
    b.St("turbine_running", "on_load", "auto_mode", "trip_status", "alarm_active",
         "barring_gear_engaged", "turning_gear_running")

    return b.result()


def build_all() -> dict[str, list[TagSpec]]:
    catalog = {
        "bfpa": build_bfp("bfpa"),
        "bfpb": build_bfp("bfpb"),
        "cepa": build_cep("cepa"),
        "cepb": build_cep("cepb"),
        "turbine": build_turbine("turbine"),
    }
    for sys, tags in catalog.items():
        got = len(tags)
        want = EXPECTED_COUNTS[sys]
        if got != want:
            raise AssertionError(f"{sys}: built {got} tags, expected {want}")
    return catalog
