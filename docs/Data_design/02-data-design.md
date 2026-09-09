# Data Design & Implementation Plan
**Scope: data layer only** — schemas, tag catalogs, generation engine, quality gates.
Agents and orchestrator are out of scope for this document.

> **Source of truth:** [Problem.md](../Problem.md). Everything in `docs/` is our own working
> material and is subordinate to it. Where this document and Problem.md disagree,
> Problem.md wins and this document is wrong and must be corrected.

---

## 1. Compliance audit — v1 design vs. Problem.md

I re-read Problem.md clause by clause against the design in
[01-problem-analysis.md](01-problem-analysis.md). Nine corrections are required. Three of them
(MOD-01, MOD-04, MOD-06) materially change the data output.

| ID | Problem.md says | v1 design did | Verdict | Correction |
|---|---|---|---|---|
| **MOD-01** | Tag name example is literally `` `bearing_temp_1` `` | Proposed `pump_de_bearing_temp_c` — engineering-realistic but with a unit suffix and DE/NDE jargon | **Drift from spec.** The spec illustrates the naming convention it expects, and reviewers will type the example queries | Adopt `measurement_qualifier_index` snake_case with **no unit in the name**: `bearing_temp_1`, `vibration_x_2`, `discharge_pressure`. Units move to `Tag.unit` / `sensor_catalog.unit` — which forces the schema-linking path to actually be exercised |
| **MOD-02** | "100 to 200 sensor columns **or records**" | Ruled "wide columns", treated the narrow reading as rejected | **Under-delivered.** "or" is inclusive; we can satisfy both readings at once for free | Wide table gives 100–200 *columns*; the `<table>_long` view gives 100–200 *records per timestamp*; the graph gives 100–200 Tag nodes per System. All three readings hold simultaneously. Remove the "narrow is rejected" framing |
| **MOD-03** | Item is "spare parts or consumables"; query asks "total **item costs**" | Had `Item.unit_cost` **and** `CONSUMED.line_cost` | Correct but under-specified | Keep both, and add invariant: `line_cost == quantity × unit_cost_at_time`, and `unit_cost_at_time == Item.unit_cost` for all in-window logs — so `SUM(r.line_cost)` and `SUM(i.unit_cost * r.quantity)` return the **same number**. Either Cypher the agent writes is correct |
| **MOD-04** | Coder Agent must do "clustering telemetry data to identify **different operating regions**" | Load profile was a smooth diurnal curve — produces one diffuse blob, not separable regions | **Data would fail the stated task.** A clustering demo on unimodal data is not a demo | Introduce an explicit 6-state **operating-mode model** plus **duty/standby alternation** for the pump pairs (§7). Regions become genuinely separable and physically justified |
| **MOD-05** | SQL example queries "yesterday" and "last 7 days" | 30-day window ending at wall-clock `NOW`, with a note about a frozen anchor | Ambiguous, and in tension with the reproducibility gate | Persist `NOW_ANCHOR` in a `run_metadata` table at seed time. Telemetry = `[anchor − 30d, anchor]`, anchor truncated to the minute. `.env` can pin it for byte-reproducibility; unset means "now", persisted so agents and notebook agree (§12) |
| **MOD-06** | Flagship flow: "latest alert generated on BFP-A … plot the **bearing temperature** readings during that alert window" | Event timeline produced alerts, but nothing guaranteed the *latest* `bfpa` alert was a bearing-temperature one | **The headline demo could plot a flat line.** Whichever event happened to be last would win | Promote to a hard **demo guarantee** (DG-1..DG-5, §9) enforced by the event scheduler and asserted by a build-failing test |
| **MOD-07** | Exactly 5 node labels, exactly 4 relationship types | Listed the right 5 and 4 | Correct — but needs a guard | Add an explicit "no extra labels/rel-types" test. Any convenience node added later fails the build. Also: **no `Component` node**, no `System→System` hierarchy, however tempting |
| **MOD-08** | "such as pressure, temperature, flow rate, vibration, etc." | Families present but not guaranteed per table | Unenforced | Add coverage gate: every one of the 5 tables carries ≥1 tag in each of `pressure`, `temperature`, `flow`, `vibration`, plus `speed`, `level`, `electrical`, `chemistry`, `derived`, `status` |
| **MOD-09** | Comparison query across `bfpa` and `bfpb` | Both tables had bearing temps, but nothing guaranteed they were *comparable* | Cross-system queries need identical column names | Introduce a **shared core tag set** (§5.1) present in all 5 systems with identical names, units, and semantics. Comparison queries become well-posed by construction |

Everything else in v1 (wide tables, physics-driven generation, event-derived alerts,
cross-DB consistency suite, standards vocabularies) survives the audit unchanged.

---

## 2. Traceability matrix

Every data-bearing clause in Problem.md → design element → the gate that proves it.

| Problem.md clause | Design element | Quality gate |
|---|---|---|
| 5 tables: `bfpa`,`bfpb`,`cepa`,`cepb`,`turbine` | §6 Postgres DDL | `G-01` |
| 100–200 sensor columns *or records* per table | §5 tag catalogs; §6 wide table + `_long` view | `G-02` |
| Time-series over the last 30 days | §7 stage 1; §12 anchor | `G-03` |
| pressure / temperature / flow rate / vibration | §5.1 family coverage | `G-04` |
| 5 node types only | §6.2 | `G-05` |
| 4 relationship types, given directions | §6.2 | `G-06` |
| **Data Separation Rule** — no telemetry in Neo4j | §6.2 property policy | `G-07` (build-failing) |
| Tag: name / unit / description, tied to SQL tables | §5 naming standard (MOD-01) | `G-08` |
| MaintenanceLog categorized per system | §10 | `G-09` |
| Item: spare parts / consumables | §10.2 | `G-10` |
| Alert: anomalous conditions, per system | §9 threshold engine | `G-11` |
| One maintenance CONSUMES multiple items | §10.3 | `G-12` |
| "max bearing temp on bfpa yesterday" | §5.1 core set; §12 anchor; DG-2 | `G-13` |
| "bfpa vs bfpb avg bearing temp, last 7 days" | MOD-09 shared core; DG-3 | `G-14` |
| "how many sensors (tags) on bfpa" | §6.3 cross-DB invariant | `G-15` |
| "turbine maintenance count + total item cost" | §10.3 cost model (MOD-03) | `G-16` |
| "most consumed items in latest CEP-A maintenance" | `CONSUMED.quantity`; DG-4 | `G-17` |
| regression / clustering into operating regions | §7 operating-mode model (MOD-04) | `G-18` |
| "latest alert on BFP-A + plot bearing temp in window" | DG-1 | `G-19` (build-failing) |

---

## 3. Design principles for this data layer

1. **One timeline, two databases.** A single event schedule drives telemetry, alerts, and
   maintenance logs. Nothing about the graph is sampled independently of the telemetry.
2. **Physics before noise.** Every tag is a function of a latent driver plus lag plus noise —
   never an independent random draw.
3. **The graph describes; Postgres measures.** Enforced mechanically, not by convention.
4. **Names are the join.** `Tag.tag_name` ≡ `sensor_catalog.tag_name` ≡ the Postgres column
   name. One string, three places, tested both directions.
5. **The catalog is data, not code.** Tag definitions live in YAML. Adding a sensor is a data
   edit, never a code change.
6. **Every demo query has a guaranteed, interesting answer.** Not "probably works" — asserted.

---

## 4. Volume targets

| System | Tag count | Rows (30d @ 60s) | Scalars |
|---|---:|---:|---:|
| `bfpa` | 130 | 43,200 | 5.62M |
| `bfpb` | 130 | 43,200 | 5.62M |
| `cepa` | 108 | 43,200 | 4.67M |
| `cepb` | 108 | 43,200 | 4.67M |
| `turbine` | 160 | 43,200 | 6.91M |
| **Total** | **636** | **216,000** | **~27.5M** |

Graph: 5 System, 636 Tag, ~120 MaintenanceLog, ~90 Item, ~340 Alert nodes;
~636 MEASURED_AT, ~120 PERFORMED_ON, ~340 GENERATED_ON, ~430 CONSUMED relationships.

All five tag counts sit inside the mandated [100, 200] band with headroom on both sides.

---

## 5. Tag catalog design

### 5.1 Naming standard (MOD-01)

```
<measurement>[_<qualifier>][_<index>]
```
- snake_case, lowercase, ASCII.
- **No unit suffix.** `bearing_temp_1`, not `bearing_temp_1_c`. The unit is `Tag.unit`.
- Numeric suffix only where multiple identical instruments exist (`bearing_temp_1..4`).
- Every name is a valid unquoted Postgres identifier, ≤ 40 chars.

Engineering detail that would have gone into the name goes into Tag properties instead:
`description` ("BFP-A drive-end journal bearing metal temperature"), `unit` ("degC"),
`kks_tag` ("LAC10 AP001 CT001"), `location` ("drive_end"), `family` ("temperature").
This is deliberate: it makes the SQL Agent's schema-linking step load-bearing rather than
decorative, because the model cannot infer units from the column name.

**Universal core — all 5 systems, identical names, units and semantics (15 tags).**
Cross-system comparison queries are well-posed because of this set.

```
bearing_temp_1  bearing_temp_2  bearing_temp_3  bearing_temp_4      degC
vibration_x_1   vibration_y_1   vibration_x_2   vibration_y_2       um
vibration_overall                                                   mm/s
shaft_speed                                                         rpm
lube_oil_pressure  lube_oil_temp  lube_oil_level                    bar / degC / %
ambient_temp                                                        degC
```

**Pump core — the 4 pumps only, identical names (10 tags).**
```
suction_pressure  discharge_pressure  differential_pressure         bar
flow_rate                                                           t/h
motor_current  motor_power  motor_voltage                           A / kW / V
winding_temp_1  winding_temp_2  winding_temp_3                      degC
```

### 5.2 Per-system catalogs

**`bfpa` / `bfpb` — multistage centrifugal boiler feed pump, motor + hydraulic coupling (130)**

| Group | n | Examples |
|---|---:|---|
| Universal core | 15 | see above |
| Pump core | 10 | see above |
| Bearings (extended) | 10 | `bearing_temp_5..8`, `thrust_bearing_temp_active`, `thrust_bearing_temp_inactive`, `bearing_vibration_1..4` |
| Stage pressures | 8 | `stage_pressure_1` … `stage_pressure_8` |
| Process | 13 | `recirc_flow`, `min_flow_valve_position`, `discharge_valve_position`, `suction_strainer_dp`, `npsh_available`, `npsh_margin`, `balance_leakoff_flow`, `balance_leakoff_temp`, `suction_temp`, `discharge_temp`, `temp_rise`, `deaerator_level`, `deaerator_pressure` |
| Seals | 5 | `gland_seal_pressure`, `gland_seal_flow`, `mech_seal_temp_1`, `mech_seal_temp_2`, `seal_leakage_rate` |
| Lube oil (extended) | 9 | `lube_oil_filter_dp`, `lube_oil_supply_temp`, `lube_oil_return_temp`, `lube_oil_cooler_inlet_temp`, `lube_oil_cooler_outlet_temp`, `lube_oil_flow`, `lube_oil_water_content`, `lube_oil_particle_count`, `aux_oil_pump_pressure` |
| Motor (extended) | 18 | `motor_current_phase_1..3`, `motor_voltage_phase_1..3`, `motor_power_factor`, `motor_frequency`, `motor_bearing_temp_de`, `motor_bearing_temp_nde`, `motor_vibration_de`, `motor_vibration_nde`, `motor_cooling_air_inlet_temp`, `motor_cooling_air_outlet_temp`, `motor_insulation_resistance`, `winding_temp_4..6` |
| Hydraulic coupling | 5 | `coupling_scoop_position`, `coupling_oil_temp`, `coupling_slip`, `coupling_input_speed`, `coupling_output_speed` |
| Booster pump | 7 | `booster_suction_pressure`, `booster_discharge_pressure`, `booster_flow`, `booster_motor_current`, `booster_bearing_temp_1..2`, `booster_vibration` |
| Water chemistry | 5 | `feedwater_conductivity`, `feedwater_ph`, `feedwater_dissolved_oxygen`, `feedwater_silica`, `feedwater_iron` |
| Rotor / mechanical | 6 | `axial_displacement`, `shaft_eccentricity`, `thrust_position`, `casing_vibration_h`, `casing_vibration_v`, `casing_vibration_a` |
| Derived | 12 | `pump_head`, `hydraulic_power`, `pump_efficiency`, `specific_energy`, `flow_deviation_from_bep`, `vibration_severity_zone`, `bearing_temp_margin`, `health_index`, `running_hours`, `start_count`, `power_consumed`, `cavitation_index` |
| Status (0/1 numeric) | 7 | `pump_running`, `standby_mode`, `auto_mode`, `trip_status`, `alarm_active`, `recirc_valve_open`, `aux_oil_pump_running` |

**`cepa` / `cepb` — vertical multistage can pump, suction under condenser vacuum (108)**

| Group | n | Examples |
|---|---:|---|
| Universal core | 15 | see above |
| Pump core | 10 | see above |
| Vertical-pump specifics | 10 | `upper_guide_bearing_temp`, `lower_guide_bearing_temp`, `thrust_bearing_temp`, `column_vibration_1..3`, `motor_stool_vibration`, `shaft_deflection`, `bowl_assembly_temp`, `line_shaft_vibration` |
| Stage pressures | 4 | `stage_pressure_1..4` |
| Condenser / vacuum | 8 | `hotwell_level`, `condenser_vacuum`, `condenser_pressure`, `condensate_temp`, `air_ingress_rate`, `cw_inlet_temp`, `cw_outlet_temp`, `condenser_ttd` |
| Process | 9 | `recirc_flow`, `min_flow_valve_position`, `discharge_valve_position`, `npsh_available`, `npsh_margin`, `cavitation_index`, `suction_pressure_abs`, `discharge_temp`, `deaerator_level` |
| Condensate chemistry | 5 | `condensate_conductivity`, `condensate_ph`, `dissolved_oxygen`, `sodium_content`, `condensate_iron` |
| Seals / gland | 4 | `gland_seal_water_flow`, `gland_seal_water_pressure`, `mech_seal_temp`, `seal_leakage_rate` |
| Lube oil | 7 | `lube_oil_filter_dp`, `lube_oil_supply_temp`, `lube_oil_return_temp`, `lube_oil_flow`, `lube_oil_water_content`, `lube_oil_particle_count`, `aux_oil_pump_pressure` |
| Motor (extended) | 16 | `motor_current_phase_1..3`, `motor_voltage_phase_1..3`, `motor_power_factor`, `motor_frequency`, `motor_bearing_temp_de`, `motor_bearing_temp_nde`, `motor_vibration_de`, `motor_vibration_nde`, `motor_cooling_air_inlet_temp`, `motor_cooling_air_outlet_temp`, `motor_insulation_resistance` |
| Derived | 13 | `pump_head`, `hydraulic_power`, `pump_efficiency`, `specific_energy`, `flow_deviation_from_bep`, `vibration_severity_zone`, `bearing_temp_margin`, `health_index`, `running_hours`, `start_count`, `power_consumed`, `vacuum_margin`, `subcooling` |
| Status | 7 | `pump_running`, `standby_mode`, `auto_mode`, `trip_status`, `alarm_active`, `recirc_valve_open`, `aux_oil_pump_running` |

**`turbine` — steam turbine + generator, 3000 rpm (160)**

| Group | n | Examples |
|---|---:|---|
| Universal core | 15 | see above |
| Bearings (extended) | 20 | `bearing_temp_5..10`, `thrust_bearing_temp_active/inactive`, `bearing_vibration_x_3..8`, `bearing_vibration_y_3..8` |
| Steam path | 28 | `main_steam_pressure`, `main_steam_temp`, `main_steam_flow`, `hp_inlet_pressure/temp`, `hp_exhaust_pressure/temp`, `reheat_inlet_pressure/temp`, `ip_inlet_pressure/temp`, `ip_exhaust_pressure/temp`, `lp_inlet_pressure/temp`, `lp_exhaust_pressure/temp`, `throttle_flow`, `extraction_pressure_1..5`, `extraction_temp_1..5` |
| Governor / valves | 12 | `gov_valve_position_1..4`, `stop_valve_position_1..2`, `reheat_stop_valve_position`, `intercept_valve_position_1..2`, `speed_setpoint`, `load_setpoint`, `governor_oil_pressure` |
| Rotor / expansion | 9 | `eccentricity`, `axial_shift`, `differential_expansion_hp/ip/lp`, `casing_expansion_1..2`, `rotor_position`, `phase_reference` |
| Oil systems | 11 | `control_oil_pressure`, `jacking_oil_pressure_1..4`, `lube_oil_tank_level`, `lube_oil_tank_temp`, `lube_oil_filter_dp`, `lube_oil_cooler_outlet_temp`, `aux_oil_pump_pressure`, `emergency_oil_pump_running` |
| Condenser / CW | 8 | `condenser_vacuum`, `condenser_pressure`, `hotwell_level`, `cw_inlet_temp`, `cw_outlet_temp`, `condenser_ttd`, `air_ejector_flow`, `cooling_water_flow` |
| Generator | 28 | `gross_power`, `reactive_power`, `stator_current_1..3`, `stator_voltage_1..3`, `stator_winding_temp_1..6`, `stator_core_temp_1..2`, `rotor_current`, `rotor_voltage`, `h2_pressure`, `h2_purity`, `h2_temp`, `seal_oil_pressure`, `seal_oil_temp`, `exciter_temp`, `generator_bearing_temp_1..2`, `frequency`, `power_factor` |
| Performance | 8 | `heat_rate`, `hp_efficiency`, `ip_efficiency`, `lp_efficiency`, `steam_rate`, `backpressure`, `vacuum_loss`, `cycle_efficiency` |
| Status | 7 | `turbine_running`, `on_load`, `auto_mode`, `trip_status`, `alarm_active`, `barring_gear_engaged`, `turning_gear_running` |

### 5.3 Catalog record schema (`catalog/<system>.yaml`)

One record per tag; this file **is** the design.

```yaml
- tag_name:        bearing_temp_1
  family:          temperature          # temperature|pressure|flow|vibration|speed|
                                        # level|electrical|chemistry|derived|status
  unit:            degC
  description:     "BFP-A drive-end journal bearing metal temperature"
  kks_tag:         "LAC10 AP001 CT001"
  location:        drive_end
  sensor_type:     RTD_PT100
  precision:       0.1                  # ADC quantization step
  noise_sigma:     0.15                 # instrument noise, in `unit`
  normal_min:      45.0
  normal_max:      85.0
  alarm_lolo:      null
  alarm_lo:        null
  alarm_hi:        88.0
  alarm_hihi:      95.0
  driver:          bearing_thermal      # which physics model produces it
  driver_params:   {ambient_offset: 22.0, load_gain: 0.42, tau_min: 28}
  is_derived:      false
```

`sensor_catalog` (Postgres) and `Tag` (Neo4j) are both projections of this file, which is why
they cannot disagree.

---

## 6. Schemas

### 6.1 Postgres

```sql
-- one per system; <n> = 108..160 sensor columns
CREATE TABLE bfpa (
  ts             TIMESTAMPTZ PRIMARY KEY,
  bearing_temp_1 DOUBLE PRECISION,
  ...                                    -- 130 columns from catalog/bfpa.yaml
);

-- metadata (mirror of the YAML catalogs; NOT a separation-rule violation:
-- the rule constrains Neo4j, and this holds no measurements)
CREATE TABLE sensor_catalog (
  system TEXT, tag_name TEXT, family TEXT, unit TEXT, description TEXT,
  kks_tag TEXT, location TEXT, sensor_type TEXT, precision DOUBLE PRECISION,
  normal_min DOUBLE PRECISION, normal_max DOUBLE PRECISION,
  alarm_lolo DOUBLE PRECISION, alarm_lo DOUBLE PRECISION,
  alarm_hi DOUBLE PRECISION, alarm_hihi DOUBLE PRECISION,
  is_derived BOOLEAN,
  PRIMARY KEY (system, tag_name)
);

CREATE TABLE run_metadata (          -- MOD-05
  key TEXT PRIMARY KEY, value TEXT   -- now_anchor, master_seed, window_start,
);                                   -- window_end, sample_seconds, generator_version

-- MOD-02: satisfies the "records" reading of the spec at zero extra storage
CREATE VIEW bfpa_long AS
  SELECT ts, u.tag_name, u.value
  FROM bfpa, LATERAL (VALUES
    ('bearing_temp_1', bearing_temp_1), ...
  ) AS u(tag_name, value);
```

Roles: `mas_writer` (seeder) and `mas_reader` (`SELECT` only,
`default_transaction_read_only = on`, `statement_timeout = '15s'`).

### 6.2 Neo4j — exactly 5 labels, exactly 4 relationship types

```cypher
(:System {name, display_name, kks_code, equipment_class, sub_class, manufacturer, model,
          rated_power_kw, rated_flow_tph, rated_head_m, rated_speed_rpm,
          commissioned_date, criticality, location, sql_table, aliases, tag_count})

(:Tag {tag_name, system, family, unit, description, kks_tag, location, sensor_type,
       precision, normal_min, normal_max, alarm_lolo, alarm_lo, alarm_hi, alarm_hihi,
       sampling_interval_s, is_derived, sql_table, sql_column})

(:MaintenanceLog {work_order_id, system, maintenance_type, maintenance_class, description,
                  failure_mode, detection_method, start_ts, end_ts, downtime_hours,
                  labor_hours, labor_cost, total_item_cost, total_cost, currency,
                  technician, status, related_alert_id})

(:Item {item_code, name, category, description, unit_cost, currency, uom, manufacturer,
        part_number, stock_qty, reorder_level, lead_time_days})

(:Alert {alert_id, system, tag_name, alert_type, severity, priority, message,
         threshold_value, peak_value, start_ts, end_ts, duration_min,
         status, acknowledged_by, acknowledged_ts, has_telemetry})

(:Alert)-[:GENERATED_ON]->(:System)
(:MaintenanceLog)-[:PERFORMED_ON]->(:System)
(:Tag)-[:MEASURED_AT]->(:System)
(:MaintenanceLog)-[:CONSUMED {quantity, unit_cost_at_time, line_cost, currency}]->(:Item)
```

**Property policy enforcing the Data Separation Rule (MOD-07):**
- Allowed on Tag: identity, unit, description, **static** alarm setpoints and design ranges.
- Forbidden anywhere: any list/array of numerics; any property matching
  `/value|reading|measurement|sample|series|history/i` on Tag.
- `Alert.threshold_value` and `Alert.peak_value` are **single scalar event attributes**, not
  time-series — they are the alarm setpoint and the single extremum that characterises the
  event. Documented explicitly so the choice is visible rather than looking like a leak.
  If a reviewer would rather see them gone, dropping `peak_value` costs nothing.

Constraints: `UNIQUE` on `System.name`, `Item.item_code`, `MaintenanceLog.work_order_id`,
`Alert.alert_id`, and composite `(Tag.system, Tag.tag_name)`.
Indexes on `Alert.start_ts`, `Alert.system`, `MaintenanceLog.start_ts`, `Tag.system`.

### 6.3 The cross-database bridge

| Graph property | Postgres counterpart | Purpose |
|---|---|---|
| `System.sql_table` | table name | orchestrator resolves graph → SQL with no hardcoded map |
| `Tag.tag_name` / `Tag.sql_column` | column name | tag identity is one string in both stores |
| `System.aliases` | — | deterministic entity resolution ("BFP-A" → `bfpa`) |
| `System.tag_count` | `COUNT(*)` from `information_schema.columns` − 1 | makes the "how many sensors" query verifiable |

---

## 7. Generation pipeline

Seven stages, each vectorized NumPy over the 43,200-step axis, all seeded from `MASTER_SEED`.

**Stage 1 — time axis.** `[anchor − 30d, anchor]` at 60 s → 43,200 timestamps, UTC.

**Stage 2 — plant state machine (MOD-04).** The fix for clusterable operating regions.
A single `unit_mode(t)` sequence over 6 states, then `unit_load_mw(t)` conditioned on it:

| Mode | Load band | Duration over 30d | Character |
|---|---|---|---|
| `OFFLINE` | 0 | ~2 days (one planned outage) | everything at ambient; aux systems only |
| `STARTUP` | 0 → 40% | ~6 h total | ramping speed, rising metal temps, eccentricity transient |
| `LOW_LOAD` | 40–60% | ~7 days (nights) | recirc valves open, low flow |
| `BASE_LOAD` | 75–90% | ~15 days | the dominant regime |
| `PEAK_LOAD` | 90–100% | ~5 days | both BFPs running, highest temps and vibration |
| `SHUTDOWN` | → 0 | ~4 h total | ramp-down, coast, barring gear |

Within a mode, load follows a smooth diurnal curve plus weekday/weekend modulation, so the
regimes are separable in (load, efficiency, vibration) space but not artificially discrete.
That is exactly what "identify different operating regions" asks for.

**Stage 3 — duty/standby allocation for the pump pairs (MOD-04).**
Real plants run one BFP on duty with the other on standby, alternating, and both together at
peak. Schedule:

```
day 0 ──────── 8 ──────── 16 ─────── 23 ── 26 ─────── 30
BFP-A   DUTY      STANDBY     DUTY      DUTY (both)   DUTY
BFP-B   STANDBY   DUTY        STANDBY   DUTY (both)   DUTY
CEP-A   DUTY      DUTY        STANDBY   DUTY (both)   DUTY
CEP-B   STANDBY   STANDBY     DUTY      DUTY (both)   DUTY
```

A standby pump is **not** dead data: `shaft_speed = 0`, `flow_rate ≈ 0`,
`pump_running = 0`, `standby_mode = 1`, bearings decay toward ambient with the proper thermal
time constant, aux oil pump keeps `lube_oil_pressure` alive, and suction pressure still tracks
the header. This yields three physically-real clusters per pump (running-loaded, running-
unloaded/recirc, standby) plus the transitions — genuinely good clustering material.

Note the last 7 days deliberately have **both** BFPs running (DG-3), so the spec's A-vs-B
comparison query has a meaningful answer rather than a trivial one.

**Stage 4 — physics.** Per system, in dependency order:
- `flow_rate = f(load, duty_share)`; recirc opens below minimum flow.
- Pump curve `H = H₀ − aQ²`; `discharge_pressure = suction_pressure + ρgH/1e5`;
  `differential_pressure = discharge − suction`; stage pressures interpolate the rise.
- Affinity laws for speed scaling: `Q ∝ N`, `H ∝ N²`, `P ∝ N³`, `NPSHr ∝ N²`.
- `hydraulic_power = ρgQH/3.6e6`; `pump_efficiency` peaks ~82% at BEP and falls off either
  side; `motor_power = hydraulic_power / efficiency`;
  `motor_current = motor_power / (√3 · V · pf)`.
- Bearing/winding temps: steady-state target from load and speed, then a **first-order lag**
  (`τ` = 20–40 min from the catalog) so temperature never steps.
- Vibration: baseline by mode + speed-squared term + degradation term (stage 6).
- Turbine: `condenser_vacuum = f(cw_inlet_temp, load, air_ingress)`;
  `heat_rate = f(load, vacuum, main_steam_temp)`; differential expansion integrates
  metal-temperature rate during ramps.
- Plant coupling: CEP discharge feeds the deaerator that feeds BFP suction, so
  `bfpa.suction_pressure` is a lagged function of CEP discharge. Cross-system correlation is
  real, which makes the Coder Agent's correlation plots meaningful rather than decorative.

**Stage 5 — chemistry & slow drift.** Conductivity, dissolved O₂, pH, silica, iron follow slow
random walks with mode-dependent means; oil particle count and water content drift upward
between oil changes and reset at maintenance.

**Stage 6 — event injection.** §9.

**Stage 7 — instrument layer.** Per-tag Gaussian noise at `noise_sigma`, 1/f bias drift,
quantization to `precision`, then a small pathology budget (≤0.15% of samples): frozen
transmitter runs, single-sample spikes, brief NULL dropouts. Deterministic given the seed.

Load path: assemble a CSV buffer per table, `COPY … FROM STDIN`. Target < 60 s total.

---

## 8. Alert derivation

After telemetry is final and immutable, a deterministic detector sweeps every tag using the
catalog setpoints. **The alerts it emits are the Alert nodes.** No alert exists that the
telemetry does not support — that is the invariant, obtained structurally rather than by
checking afterwards.

- Conditions: `hi`, `hi_hi`, `lo`, `lo_lo`, `rate_of_change`, `deviation_from_sibling`
  (e.g. `bearing_temp_1` diverging from `bearing_temp_2`), `frozen_signal`.
- ISA-18.2 hygiene: 2% deadband on clear, 30 s on-delay, 60 s off-delay, chatter suppression.
  Consecutive excursions inside 10 min merge into one Alert.
- `severity` / `priority` from the condition and the tag's criticality:
  `hi_hi` on a critical tag → `critical`; `hi` → `high`; `rate_of_change` → `medium`;
  `frozen_signal` → `low` with `alert_type = data_quality`.
- Vibration severity uses **ISO 20816-3 / ISO 10816-3** zone boundaries
  (≈1.12 / 2.8 / 7.1 mm/s) rather than invented numbers.
- Each Alert records `start_ts`, `end_ts`, `duration_min`, `threshold_value`, `peak_value`,
  `status` (`cleared` / `acknowledged` / `active`), `acknowledged_by`.

Expected yield ≈ 340 alerts over 30 days across 5 systems — busy enough to be realistic,
sparse enough that "the latest alert on BFP-A" is a meaningful question.

---

## 9. Event timeline and demo guarantees (MOD-06)

Events are scheduled first; telemetry, alerts, and maintenance all follow from them.

| Event | System | Window | Telemetry signature | Downstream |
|---|---|---|---|---|
| E1 Bearing degradation | `bfpa` | d−6 → d−3 | `bearing_temp_1` ramps +18 °C; `vibration_overall` crosses Zone B→C | Alert (hi → hi_hi) → corrective WO at d−3 → bearing + seal kit + oil |
| E2 Seal leakage | `bfpb` | d−14 → d−11 | `seal_leakage_rate` rises; `gland_seal_pressure` decays | Alert (high) → corrective WO → mechanical seal set |
| E3 Cavitation | `cepa` | d−9 → d−8 | `npsh_margin` → 0; `suction_pressure` oscillates; broadband vibration | Alert (medium) → predictive WO → suction strainer + gasket |
| E4 Oil filter clogging | `cepb` | d−20 → d−17 | `lube_oil_filter_dp` ramps to setpoint | Alert (low) → preventive WO → 2 × filter element |
| E5 Vacuum deterioration | `turbine` | d−12 → d−10 | `condenser_vacuum` degrades; `heat_rate` rises | Alert (high) → WO: air-ingress survey → gaskets, packing |
| E6 Restart eccentricity | `turbine` | d−22 (post-outage) | `eccentricity` spike at low speed | Alert (critical, short) — no WO |
| E7 Sensor fault | `bfpb` | d−5 → d−4 | `bearing_temp_3` frozen while siblings move | Alert (`data_quality`) → instrument WO → RTD replacement |
| E8 Load-following stress | all | continuous | normal excursions at peak load | background alert traffic |

After a corrective work order's `end_ts`, the degradation term resets to zero, so the
telemetry shows a visible step recovery — which makes maintenance events discoverable from
the data, not just asserted in the graph.

**Demo guarantees — scheduler constraints, each asserted by a build-failing test:**

- **DG-1** The *latest* Alert on `bfpa` is a **bearing-temperature** alert (E1) with
  `start_ts`/`end_ts` strictly inside the telemetry window, and
  `MAX(bearing_temp_1)` over that window exceeds `threshold_value` by ≥ 2 °C.
  *No `bfpa` alert may be scheduled after E1.* → the flagship multi-agent query plots a
  visible excursion. **This is the single most important constraint in the data layer.**
- **DG-2** `bfpa` is running (`pump_running = 1`) for ≥ 90% of the calendar day preceding the
  anchor → "max bearing temperature yesterday" returns an operational value, not standby.
- **DG-3** Over the last 7 days both `bfpa` and `bfpb` run ≥ 60% of the time, and
  `AVG(bearing_temp_1)` differs by ≥ 3 °C with **A higher** — traceable to E1. → the
  comparison query has a non-trivial answer with a discoverable cause.
- **DG-4** `cepa` has ≥ 2 maintenance logs in the window; the latest consumes ≥ 3 distinct
  Items with **distinct** quantities → "most consumed" has an unambiguous winner.
- **DG-5** `turbine` has ≥ 8 MaintenanceLogs with non-zero item cost across the 24-month
  history → the count-and-cost query returns interesting numbers.

---

## 10. Maintenance, Items, and consumption

### 10.1 MaintenanceLog
~120 records over 24 months (≈24 per system). Only those tied to E1–E7 fall inside the
telemetry window; the rest populate history so cost rollups are meaningful.

- `maintenance_class` ∈ {`preventive`, `corrective`, `predictive`, `modification`} and
  `failure_mode` ∈ the ISO 14224 vocabulary (`vibration`, `overheating`, `external_leakage`,
  `plugged_choked`, `abnormal_instrument_reading`, `structural_deficiency`, …).
- `detection_method` ∈ {`condition_monitoring`, `periodic_inspection`, `alarm`,
  `operator_report`}. Logs derived from E1–E7 carry `related_alert_id` and
  `detection_method = alarm`.
- `start_ts` > the triggering alert's `start_ts` — work orders never precede their trigger.

### 10.2 Item catalog
~90 items across 14 categories (bearing, seal, filter, gasket, o_ring, lubricant, coupling,
impeller, wear_ring, sleeve, valve, instrument, fastener, electrical), with a realistic
cost spread from ~$8 (O-ring) to ~$8,500 (turbine journal bearing). Currency: **USD**,
recorded explicitly on both Item and CONSUMED so no query has to assume it.

### 10.3 Consumption (MOD-03)
- Every corrective/preventive log consumes 1–7 Items; ≥ 40% consume ≥ 3, satisfying the
  spec's "one maintenance activity can consume multiple item nodes".
- `CONSUMED {quantity, unit_cost_at_time, line_cost, currency}`.
- Enforced identities, so both natural Cypher formulations agree:
  ```
  line_cost              == quantity × unit_cost_at_time
  unit_cost_at_time      == Item.unit_cost
  total_item_cost        == Σ line_cost over the log's CONSUMED edges
  total_cost             == total_item_cost + labor_cost
  ```

---

## 11. Quality gates (`make validate`)

Build-failing. The report prints in the notebook as the proof for evaluation criterion 1.

| ID | Gate |
|---|---|
| G-01 | Exactly the 5 required tables exist |
| G-02 | Each table's sensor-column count ∈ [100, 200]; `_long` view yields the same count per timestamp; `System.tag_count` matches |
| G-03 | `MIN(ts) == anchor − 30d`, `MAX(ts) == anchor`; 43,200 rows; no gaps; no duplicate `ts` |
| G-04 | Every table has ≥ 1 tag in each of pressure, temperature, flow, vibration (+ the other 6 families) |
| G-05 | `CALL db.labels()` == {System, Tag, MaintenanceLog, Item, Alert} — no extras |
| G-06 | `CALL db.relationshipTypes()` == {GENERATED_ON, PERFORMED_ON, MEASURED_AT, CONSUMED}; every instance has the spec's direction |
| **G-07** | **Separation rule:** no Neo4j property is an array of numerics; no Tag property matches `/value\|reading\|measurement\|sample\|series\|history/i` |
| G-08 | `Tag.tag_name` set per system **==** Postgres column set (both directions); `unit`, `description`, ranges match `sensor_catalog` and the YAML catalog |
| G-09 | Every MaintenanceLog has exactly one `PERFORMED_ON`, and its `system` property matches that target |
| G-10 | Every Item is reachable via ≥ 1 CONSUMED; no orphans |
| G-11 | Every Alert has exactly one `GENERATED_ON`; `system` matches; `tag_name` exists in that system's catalog |
| G-12 | ≥ 40% of MaintenanceLogs consume ≥ 3 distinct Items |
| G-13 | DG-2 holds |
| G-14 | DG-3 holds |
| G-15 | Graph tag count per system **==** Postgres column count (the cross-DB invariant) |
| G-16 | Cost identities of §10.3 hold for every log; DG-5 holds |
| G-17 | DG-4 holds |
| G-18 | KMeans (k=4) on (load, efficiency, vibration_overall) reaches silhouette ≥ 0.45 → operating regions are genuinely separable |
| **G-19** | **DG-1 holds** — the latest `bfpa` alert is a bearing-temperature alert whose window contains a telemetry excursion ≥ 2 °C above threshold |
| G-20 | For every corrective log: the tag's 6 h post-`end_ts` mean is materially below its 6 h pre-`start_ts` mean (repairs are visible) |
| G-21 | NULL fraction ≤ 0.15% per table; no column entirely NULL or entirely constant (except intentional status tags) |
| G-22 | Re-seeding with a pinned `NOW_ANCHOR` + `MASTER_SEED` reproduces identical per-table content hashes |

---

## 12. Reproducibility & configuration (MOD-05)

```
MASTER_SEED=20260907          # every RNG derives from this
NOW_ANCHOR=                   # blank → date_trunc('minute', now()) at seed time
SAMPLE_SECONDS=60
WINDOW_DAYS=30
MAINTENANCE_HISTORY_MONTHS=24
CURRENCY=USD
```

- The anchor is resolved once, written to `run_metadata`, and read by the seeder, the
  validators, the agents, and the notebook. Nothing calls `now()` twice.
- Every RNG is a `numpy.random.Generator` derived as
  `SeedSequence(MASTER_SEED).spawn()` keyed by `(system, tag_name)`, so adding a tag cannot
  change any existing tag's values.
- G-22 pins the anchor to prove bit-reproducibility; the default unpinned path gives a fresh
  "last 30 days" for a live demo. Both behaviours are intentional and documented.

---

## 13. Build manifest — plan of action for the data layer

Order matters: each step's output is the next step's input.

| # | Deliverable | Depends on |
|---|---|---|
| 1 | `docker-compose.yml` (postgres:16, neo4j:5 + APOC), `.env.example`, `Makefile` targets `up`/`down` | — |
| 2 | `src/mas/config.py` — pydantic-settings; seed, anchor, window resolution | 1 |
| 3 | `catalog/{bfpa,bfpb,cepa,cepb,turbine}.yaml` — **636 tag records** (§5) | — |
| 4 | `src/mas/datagen/catalog.py` — load + schema-validate YAML; emit column lists | 2, 3 |
| 5 | `src/mas/db/schema.sql` generated from the catalogs (5 tables + `sensor_catalog` + `run_metadata` + 5 `_long` views) and `constraints.cypher` | 4 |
| 6 | `src/mas/datagen/modes.py` — plant state machine + duty/standby schedule (§7 s2–s3) | 2 |
| 7 | `src/mas/datagen/physics.py` — per-family driver models (§7 s4–s5) | 4, 6 |
| 8 | `src/mas/datagen/events.py` — E1–E8 schedule + DG-1..DG-5 constraint solver | 6 |
| 9 | `src/mas/datagen/instrument.py` — noise, quantization, pathologies (§7 s7) | 4 |
| 10 | `src/mas/datagen/build_telemetry.py` — orchestrates s1–s7, `COPY` load | 5,6,7,8,9 |
| 11 | `src/mas/datagen/alerts.py` — threshold engine over final telemetry (§8) | 10 |
| 12 | `src/mas/datagen/maintenance.py` — Item catalog, work orders, consumption (§10) | 8, 11 |
| 13 | `src/mas/datagen/graph_seed.py` — project catalogs + alerts + maintenance into Neo4j | 5, 11, 12 |
| 14 | `src/mas/eval/consistency.py` — gates G-01..G-22 (§11) | 10, 13 |
| 15 | `docs/03-data-dictionary.md` generated from `sensor_catalog` | 13 |
| 16 | `make seed` = 5→13, `make validate` = 14 | all |

**Exit criterion for the data layer:** `make up && make seed && make validate` returns
22/22 gates green on a clean clone, in under five minutes.

---

## 14. Open decisions for you

1. **`Alert.peak_value`** — a single scalar extremum characterising the event. I read it as
   event metadata, not telemetry, but it is the one property a strict reader could argue
   about. Keep it (better demos) or drop it (zero ambiguity)? Default: keep, documented.
2. **Currency** — assumed USD. Switch to INR if the audience expects it.
3. **`NOW_ANCHOR` default** — live wall-clock (fresh "last 30 days" on every seed) vs. pinned
   (byte-identical every time). Default: live, with pinning available and exercised by G-22.
4. **Tag counts** — currently 130/130/108/108/160, comfortably inside [100, 200]. Say the word
   to push all five toward ~180 for a denser dataset.
