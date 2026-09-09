# Problem Analysis & System Design Brief
**Case Study: Multi-Agent Systems for Industrial Asset Analytics**
Status: pre-implementation research + design. Source spec: [Problem.md](../Problem.md)

---

## 0. TL;DR — what is actually being graded

The spec reads like "build 3 agents + 2 databases." It is not. Read the four evaluation
criteria backwards and the real test is:

| Criterion | What they are really probing | Where projects fail |
|---|---|---|
| 1. System Completeness & **Data Quality** | Can you fabricate ~30M telemetry points a domain engineer would believe, and keep Neo4j and Postgres *mutually consistent*? | `random.uniform(60, 90)` for bearing temp. Alert windows that show nothing when plotted. Tag names in Neo4j that don't match Postgres columns. |
| 2. Orchestrator **Sequencing** | Does the planner produce a real **dependency graph** where step N consumes step N−1's output — with no `if "plot" in query` anywhere? | Keyword routers dressed up as agents. Single-agent-per-query systems that can't do the alert→plot handoff. |
| 3. Agent **Determinism & Accuracy** | Are generated SQL/Cypher/Python *validated before execution*, read-only, repaired on failure, and reproducible run-to-run? | Raw LLM output piped into `cursor.execute()`. `exec()` with no AST guard. Nondeterministic sampling. |
| 4. **Demonstration Notebook** | Can a reviewer clone, `make up && make seed`, open one notebook, and see every spec example work? | 45-minute setup. Notebook with stale outputs. Examples quietly reworded to ones that happen to pass. |

**The single highest-leverage design decision in the whole assignment:** the telemetry
generator and the graph seeder must be *one program driven by one event timeline*. Alerts,
maintenance logs, and spare-part consumption are **derived from injected physical events in
the telemetry**, not sampled independently. That is what makes criterion 1 pass, and what
makes the flagship multi-agent query (criterion 2) produce a plot that visibly contains the
anomaly instead of a flat line.

---

## 1. Requirement decomposition → acceptance tests

Every line of the spec turned into something binary and checkable.

### 1.1 Databases

| # | Spec requirement | Acceptance test |
|---|---|---|
| D1 | 5 Postgres tables: `bfpa`, `bfpb`, `cepa`, `cepb`, `turbine` | `SELECT tablename FROM pg_tables` returns exactly these 5 (+ metadata tables) |
| D2 | 100–200 sensor columns/records per table | `information_schema.columns` count per table ∈ [100, 200] |
| D3 | Time-series over the last 30 days | `MIN(ts) >= NOW() - 31d AND MAX(ts) <= NOW()`; no gaps > 1 sampling interval |
| D4 | Pressure / temperature / flow / vibration families present | tag catalog asserts ≥1 tag per family per system |
| D5 | Neo4j has 5 node labels: System, Tag, MaintenanceLog, Item, Alert | `CALL db.labels()` == that set |
| D6 | 4 relationship types, correct direction | `CALL db.relationshipTypes()` + directional Cypher assertions |
| D7 | **No telemetry values in Neo4j** | property-type scan: assert no node property is an array of numerics; assert no Tag property matches `/value|reading|measurement|sample/i` |
| D8 | One MaintenanceLog can CONSUME many Items | `MATCH (m)-[:CONSUMED]->(i) WITH m, count(i) AS c WHERE c > 1 RETURN count(m) > 0` |

### 1.2 Agents

| # | Spec requirement | Acceptance test |
|---|---|---|
| A1 | SQL Agent: single-system stats | "max bearing temperature on bfpa yesterday" → matches a hand-written golden query's *result*, not its text |
| A2 | SQL Agent: cross-system comparison | "bfpa vs bfpb bearing temp, 7d avg" → one query touching both tables (or two queries + a comparison step) |
| A3 | Graph Agent: structural count | "how many tags on bfpa" → equals `information_schema` column count for `bfpa` (cross-DB invariant) |
| A4 | Graph Agent: aggregation over a path | "turbine maintenance count + total item cost" → equals sum of `CONSUMED.line_cost` |
| A5 | Graph Agent: ranking on a relationship property | "most consumed spare parts in latest CEP-A maintenance" → ordered by `CONSUMED.quantity` |
| A6 | Coder Agent: line / bar / correlation charts | figure artifact returned; non-empty axes; deterministic given seed |
| A7 | Coder Agent: regression / clustering | fit head-vs-flow curve; KMeans on (load, efficiency, vibration) → labelled operating regions |
| A8 | Multi-agent: latest alert → plot alert window | graph step returns `start_ts`/`end_ts`; the plot's x-limits equal them; the series visibly crosses `Alert.threshold_value` |

### 1.3 Cross-cutting (the criteria themselves)

| # | Requirement | Acceptance test |
|---|---|---|
| X1 | Dynamic routing, no hardcoded paths | Routing eval set (~40 queries incl. unseen phrasings) → ≥95% correct agent sequence. Grep for `if "plot" in`-style branches: zero. |
| X2 | Determinism | Run each example query 5×: identical plan JSON, identical generated SQL/Cypher, identical result hash |
| X3 | Read-only safety | Fuzz with "delete all maintenance logs" / "DROP TABLE bfpa" → blocked at the validator, never reaches the driver |
| X4 | Reproducible data | `make seed` twice → identical row hashes (fixed seed + fixed `NOW` anchor) |

---

## 2. Ambiguities in the spec, and the rulings I recommend

These need an explicit decision recorded in the README, because a reviewer will look for
whether you noticed them.

**AMB-1 — "100 to 200 sensor columns *or records*"**
Two readings: (a) 100–200 *columns* per table (wide layout); (b) 100–200 *tag records*
(narrow/EAV layout). The example query — *"maximum bearing temperature recorded on bfpa"* —
and the phrase "sensor columns" appearing first both point to (a).

> **Ruling: wide tables.** `ts TIMESTAMPTZ PRIMARY KEY` + 110–170 typed `DOUBLE PRECISION`
> sensor columns per system. Postgres caps at 1600 columns, so this is comfortable.
> Wide also makes the SQL agent's job near-trivially deterministic
> (`SELECT MAX(pump_de_bearing_temp_c) FROM bfpa WHERE ts >= …`) and matches how real
> historian exports (PI, Aspen IP.21) land in an analytics warehouse.
> Industry guidance says narrow scales better past ~200 signals and avoids migrations —
> true, but irrelevant at this fixed schema and 30-day horizon. **Mitigation:** also ship a
> `*_long` view (`ts, tag_name, value`) via `LATERAL` unnest so the Coder Agent can pivot
> freely, and record the wide-vs-narrow tradeoff in the README as a deliberate call.

**AMB-2 — sampling interval.** Not specified. 1 minute is the de-facto standard for plant
historian aggregates and matches the reference Kaggle pump dataset's cadence.
> **Ruling: 60 s for all five systems** → 43,200 rows/table, ~30M scalar values total.
> Config-driven (`SAMPLE_SECONDS`) so it can be dropped to 10 s for the turbine if asked.

**AMB-3 — "deterministic multi-agent system" + an LLM planner.** These are in tension.
> **Ruling — determinism is a property of the execution layer, not the model.** State this
> explicitly: (i) every generated artifact (SQL, Cypher, Python) is parsed and validated
> against an allowlist before it can execute; (ii) all DB access goes through read-only roles
> with statement timeouts; (iii) all temporal reasoning ("yesterday", "last 7 days") is
> resolved in *code* against a frozen `NOW` anchor, never by the LLM; (iv) plans are
> validated against a Pydantic schema, and a plan cache keyed on the normalized question
> makes repeat runs byte-identical; (v) every run emits a replayable trace. This framing
> turns criterion 3 from a liability into a talking point.

**AMB-4 — how much history for MaintenanceLog / Alert.** Telemetry is 30 days; maintenance
history is naturally longer.
> **Ruling:** MaintenanceLog spans 24 months (so cost rollups are interesting); Alerts span
> the 30-day telemetry window and are **derived from the generated telemetry**, so every
> alert is plottable. Add a handful of older alerts for realism, flagged
> `has_telemetry: false`.

**AMB-5 — is a `sensor_catalog` table in Postgres a violation of the separation rule?**
No. The rule forbids *time-series values in Neo4j*. Metadata in Postgres is unconstrained and
is what makes SQL schema-linking cheap and deterministic. It mirrors the Tag nodes, and a
consistency test asserts the two are identical.

---

## 3. Layer 1 — The data layer (the differentiator)

### 3.1 Postgres physical design

```
telemetry (per system, wide)
  bfpa     (ts PK, ~148 sensor columns)
  bfpb     (ts PK, ~148)
  cepa     (ts PK, ~118)
  cepb     (ts PK, ~118)
  turbine  (ts PK, ~168)

metadata (supports schema linking; mirrors Neo4j Tag nodes)
  sensor_catalog(system, tag_name, column_name, unit, description, sensor_type,
                 family, normal_min, normal_max, alarm_hi, alarm_hihi, alarm_lo,
                 alarm_lolo, precision, is_derived)
```

- Index: `ts` is the PK (btree). Add BRIN on `ts` as a documented alternative — at 43k rows
  it changes nothing, but showing you know why is free credit.
- Roles: `mas_writer` (seeder only) and `mas_reader` (`GRANT SELECT` only,
  `ALTER ROLE mas_reader SET default_transaction_read_only = on`,
  `SET statement_timeout = '15s'`). The SQL Agent connects **only** as `mas_reader`.
- Load path: build each column as a 43,200-element NumPy array, assemble a CSV/Arrow buffer,
  `COPY … FROM STDIN`. The whole seed should finish well under a minute.
- Partitioning is unnecessary at this volume; note in the README that at 10 s sampling ×
  1 year you would move to monthly `RANGE` partitions or a TimescaleDB hypertable.

### 3.2 Sensor tag design — grounded in real plant practice

Don't invent 700 tag names ad hoc. Derive them from three real conventions so the catalog is
defensible under questioning:

- **KKS** (Kraftwerk-Kennzeichensystem) for the plant-side identifier — BFP-A ≈ `LAC10 AP001`
  (`LA` feedwater system → `LAC` feedwater pump system), CEP-A ≈ `LCB10 AP001`,
  turbine ≈ `MAA10`. Store as `Tag.kks_tag` / `System.kks_code`.
- **ISA-5.1** instrument letters for measurement type — `PT`/`TT`/`FT`/`VT`/`LT`/`ST`
  (pressure / temperature / flow / vibration / level / speed transmitter).
- **Snake-case analytics name** as both the Postgres column and `Tag.tag_name` — e.g.
  `pump_de_bearing_temp_c`. This is the join key between the two databases.

Tag families per asset (counts are the design target):

**BFP-A / BFP-B — multistage centrifugal, motor + hydraulic coupling, ~4500–6000 rpm** (~148)

| Family | n | Representative tags |
|---|---|---|
| Process hydraulics | 18 | `suction_press_bar`, `discharge_press_bar`, `diff_press_bar`, `feed_flow_tph`, `recirc_flow_tph`, `min_flow_valve_pos_pct`, `npsha_m`, `cavitation_margin_m`, `balance_leakoff_flow_lpm`, `suction_strainer_dp_bar`, `deaerator_level_pct` |
| Stage pressures | 8 | `stage_1_press_bar` … `stage_8_press_bar` |
| Pump mechanical | 24 | `shaft_speed_rpm`, `pump_de_bearing_temp_c`, `pump_nde_bearing_temp_c`, `thrust_brg_active_temp_c`, `journal_brg_1..4_temp_c`, `shaft_vib_de_x_um`, `shaft_vib_de_y_um`, `casing_vib_de_mms`, `axial_displacement_mm`, `shaft_eccentricity_um` |
| Lube oil | 12 | `lube_oil_press_bar`, `lube_oil_supply_temp_c`, `lo_filter_dp_bar`, `lo_cooler_out_temp_c`, `lo_tank_level_pct`, `lo_water_content_ppm` |
| Motor | 20 | `motor_current_r/y/b_a`, `motor_power_kw`, `motor_power_factor`, `motor_winding_temp_u/v/w_c`, `motor_de/nde_brg_temp_c`, `motor_vib_de_mms`, `motor_insulation_mohm` |
| Coupling / drive | 10 | `hyd_coupling_scoop_pos_pct`, `coupling_oil_temp_c`, `coupling_slip_pct` |
| Seals & gland | 8 | `gland_seal_press_bar`, `mech_seal_temp_c`, `seal_leakage_lpm` |
| Booster pump | 10 | `booster_disch_press_bar`, `booster_motor_current_a` |
| Water chemistry | 8 | `fw_conductivity_us_cm`, `fw_do_ppb`, `fw_ph` |
| Derived / performance | 12 | `pump_head_m`, `hydraulic_power_kw`, `pump_efficiency_pct`, `specific_energy_kwh_per_t`, `flow_dev_from_bep_pct`, `vib_severity_zone`, `health_index` |

**CEP-A / CEP-B — vertical can pump, ~1480 rpm, suction under condenser vacuum** (~118)
Distinctive tags: `hotwell_level_mm`, `suction_press_mbara` (vacuum), `condenser_vacuum_mbara`,
`condensate_flow_tph`, `condensate_temp_c`, `cond_conductivity_us_cm`, `dissolved_o2_ppb`,
`air_ingress_index`, `upper_guide_brg_temp_c` / `lower_guide_brg_temp_c` (vertical machines
have guide bearings, not DE/NDE), `gland_seal_water_flow_lpm`, `npsha_margin_m`.
The CEP draws condensate from the condenser hotwell under vacuum and discharges at modest
positive pressure into the LP heater / deaerator train, which then feeds the BFP suction —
so CEP and BFP tags should be *causally linked* in the generator, not independent.

**Turbine — steam turbine, 3000 rpm** (~168)

| Family | n | Representative tags |
|---|---|---|
| Steam path | 30 | `main_steam_press_bar`, `main_steam_temp_c`, `hrh_temp_c`, `hp_exhaust_press_bar`, `ip_inlet_temp_c`, `lp_exhaust_temp_c`, `throttle_flow_tph` |
| Governor / valves | 12 | `gov_valve_1..4_pos_pct`, `stop_valve_pos_pct`, `speed_setpoint_rpm` |
| Rotor & expansion | 20 | `shaft_speed_rpm`, `eccentricity_um`, `axial_shift_mm`, `hp/ip/lp_diff_expansion_mm`, `casing_expansion_mm` |
| Bearings (8 pedestals) | 32 | `brg_1..8_metal_temp_c`, `brg_1..8_vib_x_um` / `_y_um`, `thrust_brg_active/inactive_temp_c` |
| Lube / control / jacking oil | 16 | `lube_oil_press_bar`, `control_oil_press_bar`, `jacking_oil_press_bar`, `lo_tank_temp_c` |
| Condenser & CW | 16 | `condenser_vacuum_mbara`, `cw_inlet_temp_c`, `cw_outlet_temp_c`, `ttd_c`, `hotwell_level_mm` |
| Generator | 22 | `gross_mw`, `mvar`, `stator_winding_temp_1..6_c`, `h2_press_bar`, `h2_purity_pct`, `seal_oil_press_bar` |
| Performance | 12 | `heat_rate_kj_per_kwh`, `hp_efficiency_pct`, `steam_flow_tph`, `backpressure_kpa` |

This matches the ~8 core parameters real steam-turbine supervisory systems monitor — shaft
vibration, axial position, eccentricity, differential expansion, casing expansion, speed,
phase reference, valve position — expanded to a full tag list. The 8 journal bearings with
X/Y proximity probes are exactly why the spec's "bearing temperature" example is natural, and
they give the Coder Agent genuinely interesting correlation material.

### 3.3 The generation engine — how to make ~30M points *meaningful*

Five stacked layers. Each is vectorized NumPy over the 43,200-step time axis, seeded from a
single master seed so `make seed` is bit-reproducible.

**Layer 1 — one latent driver: plant load.**
Generate `unit_load_mw(t)` once: diurnal ramp (trough ~03:00, peak 10:00–20:00),
weekday/weekend modulation, a few planned ramps, and one two-day outage. **Every other tag is
a function of load.** This is the reason the data will look real: real plant tags are
massively cross-correlated, and independently-sampled noise is the tell-tale sign of fake data.

**Layer 2 — physics coupling.** Concrete relationships to implement:

- Flow: `feed_flow ≈ k · load`, plus recirculation valve opening below minimum flow.
- Pump curve: `H = H₀ − a·Q²`; `discharge_press = suction_press + ρgH/1e5`.
- Affinity laws for speed scaling: `Q ∝ N`, `H ∝ N²`, `P ∝ N³`, and `NPSHr ∝ N²`
  (the last one is what makes a cavitation event physically coherent).
- Power: `P_hyd = ρ g Q H / 3.6e6` kW; `P_shaft = P_hyd / η(Q/Q_bep)` with η peaking around
  80–87% at BEP and falling off either side; `motor_current ≈ P / (√3 · V · pf)`.
- Thermal: `bearing_temp = T_ambient + α·load + β·speed²` passed through a **first-order lag**
  (`τ ≈ 20–40 min`) so temperatures don't teleport. This single detail separates plausible
  telemetry from obviously-synthetic telemetry.
- Turbine: `condenser_vacuum = f(cw_inlet_temp, load, air_ingress)`;
  `heat_rate = f(load, vacuum, main_steam_temp)`; differential expansion tracks the integral
  of metal-temperature change during ramps.

**Layer 3 — stochastic realism.**
Per-tag Gaussian noise with σ from the tag catalog (a 0–200 bar transmitter is ±0.1 bar, not
±5), 1/f drift for slow instrument bias, ADC quantization to the tag's `precision`, and a
small budget of instrument pathologies: frozen values (stuck transmitter), single-sample
spikes, brief NULL dropouts. These give the Coder Agent real data-cleaning work to show off.

**Layer 4 — the event timeline (the keystone).**
Define an explicit list of events per system, each `{system, kind, tag(s), t_start, t_end,
shape, magnitude}`:

| Event | Telemetry signature | Downstream artifacts |
|---|---|---|
| Bearing degradation (BFP-A) | `pump_de_bearing_temp_c` ramps +18 °C over 12 h; `casing_vib_de_mms` crosses ISO 20816 Zone B→C | Alert (hi then hi-hi) → corrective MaintenanceLog consuming bearing + seal kit + oil |
| Cavitation (CEP-A) | `suction_press` oscillation, `npsha_margin_m` → 0, broadband vibration rise, flow instability | Alert (medium) → predictive MaintenanceLog consuming suction strainer + gasket |
| Seal leakage (BFP-B) | `seal_leakage_lpm` monotonic rise, `gland_seal_press_bar` decay | Alert → corrective MaintenanceLog consuming mechanical seal set |
| Lube-oil filter clogging | `lo_filter_dp_bar` ramps to setpoint | Alert (low) → preventive MaintenanceLog consuming filter element ×2 |
| Condenser vacuum deterioration | `condenser_vacuum_mbara` degrades, `heat_rate_kj_per_kwh` rises | Alert → MaintenanceLog (air-ingress survey) |
| Turbine eccentricity on restart | `eccentricity_um` spike at low speed after the outage | Alert (critical, short) |
| Sensor fault | one tag frozen / railed while its physical siblings move | Alert (`data_quality`), no maintenance |

Each event **generates its Alert node**, with `start_ts` / `end_ts` / `peak_value` /
`threshold_value` read back off the generated series, and where applicable its MaintenanceLog
plus CONSUMED edges. After a corrective maintenance `end_ts`, the degradation term is
**reset to zero** — so the telemetry shows the step recovery a reviewer plotting around the
work order will actually see.

**Layer 5 — alert detection pass.**
After telemetry is final, run a deterministic threshold engine (hi / hi-hi / lo / lo-lo /
rate-of-change / deviation-from-sibling) over every tag using the catalog setpoints, with
ISA-18.2-style deadband and a 30 s on-delay to suppress chatter. The alerts it emits *are*
the Alert nodes. This guarantees the invariant "every alert is reproducible from the
telemetry" for free.

Severity mapping uses real standards where they exist: vibration alerts follow
**ISO 20816-3 / ISO 10816-3** zones (≈1.12 mm/s Zone A boundary, 2.8 Zone B, 7.1 mm/s → Zone D,
immediate action), which is a far better story than arbitrary numbers.

### 3.4 Neo4j graph design

```cypher
(:System   {name, display_name, kks_code, equipment_class, sub_class, manufacturer, model,
            rated_power_kw, rated_flow_tph, rated_head_m, rated_speed_rpm,
            commissioned_date, criticality, location, sql_table, aliases})
(:Tag      {tag_name, kks_tag, system, description, unit, sensor_type, family,
            normal_min, normal_max, alarm_hi, alarm_hihi, alarm_lo, alarm_lolo,
            sampling_interval_s, precision, is_derived})
(:MaintenanceLog {work_order_id, system, maintenance_type, maintenance_class, description,
            failure_mode, detection_method, start_ts, end_ts, downtime_hours,
            labor_hours, labor_cost, total_item_cost, total_cost, technician, status})
(:Item     {item_code, name, category, unit_cost, uom, manufacturer, part_number,
            stock_qty, reorder_level, lead_time_days})
(:Alert    {alert_id, system, tag_name, alert_type, severity, priority, message,
            threshold_value, peak_value, start_ts, end_ts, duration_min,
            status, acknowledged_by, acknowledged_ts})

(:Alert)-[:GENERATED_ON]->(:System)
(:MaintenanceLog)-[:PERFORMED_ON]->(:System)
(:Tag)-[:MEASURED_AT]->(:System)
(:MaintenanceLog)-[:CONSUMED {quantity, unit_cost_at_time, line_cost}]->(:Item)
```

Design notes that earn marks:

- **`System.sql_table` is the deliberate cross-database bridge.** It lets the orchestrator
  resolve a graph answer into a Postgres target without a hardcoded dict. Same for
  `Tag.tag_name` == the Postgres column name.
- **`System.aliases`** (`["BFP-A", "BFP A", "Boiler Feed Pump A", "bfp_a"]`) drives the
  deterministic entity resolver, so alias handling is *data*, not code.
- **Properties on `CONSUMED`.** The spec's "which spare parts were consumed the most"
  question is unanswerable without `quantity` on the relationship. Easy to miss.
- **Vocabulary from ISO 14224** for `equipment_class` (centrifugal pump / steam turbine, at
  level 7 of its 9-level taxonomy), `failure_mode` (vibration, overheating, external leakage,
  plugged/choked, …, recorded at component level), and `maintenance_class`
  (preventive / corrective / predictive / modification). This gives the graph a real ontology
  rather than invented enums, and it's the standard that actually governs reliability and
  maintenance data collection for this equipment.
- **`Alert.priority` from ISA-18.2** (critical / high / medium / low, plus rationalization
  and acknowledgment state) rather than free-text severity.
- Constraints: `UNIQUE` on `System.name`, `Tag.tag_name` (composite with system),
  `MaintenanceLog.work_order_id`, `Item.item_code`, `Alert.alert_id`; indexes on
  `Alert.start_ts`, `MaintenanceLog.start_ts`, `Tag.system`.

Scale target: 5 Systems, ~700 Tags, ~120 MaintenanceLogs, ~90 Items, ~350 Alerts,
~450 CONSUMED edges. Small graph, rich structure — which is correct: the graph is the
*ontology*, Postgres carries the mass.

### 3.5 Cross-database consistency suite (`make validate`)

Ship this as a real test module and print its report in the notebook. It is the cheapest
possible proof of criterion 1.

1. `Tag.tag_name` set per system **==** Postgres column set for `System.sql_table`. Both ways.
2. `Tag.unit` / `normal_min` / `normal_max` **==** the `sensor_catalog` row. Both ways.
3. For every Alert: querying Postgres over `[start_ts, end_ts]` for `Alert.tag_name` returns
   rows, and `MAX(value)` (or `MIN` for lo alerts) **crosses `threshold_value`**.
4. For every corrective MaintenanceLog: the referenced tag's mean in the 6 h after `end_ts`
   is materially below its mean in the 6 h before — the repair is visible.
5. No Neo4j property holds an array of numerics; no Tag property matches
   `/value|reading|measurement|sample/i` → the **Data Separation Rule** is enforced, not asserted.
6. `MaintenanceLog.total_item_cost` **==** `sum(CONSUMED.line_cost)`; `total_cost` == items + labor.
7. Telemetry continuity: no gaps, no duplicate `ts`, NULL fraction within the configured budget.
8. Every Alert's `system` property matches its `GENERATED_ON` target; same for MaintenanceLog.

---

## 4. Layer 2 — The agents

### 4.1 Shared contract

Every agent exposes **capabilities**, not a chat interface. A capability is
`(name, description, input_model, output_model, cost_hint)` with Pydantic models on both
sides. The orchestrator sees only this registry — which is precisely what makes routing
dynamic and typed at the same time.

All agent outputs land in a typed **artifact store** (the blackboard):
`TableArtifact` (DataFrame + schema + provenance), `RecordsArtifact` (graph rows),
`ScalarArtifact`, `FigureArtifact` (PNG path + caption), `CodeArtifact`. Steps reference
earlier artifacts by `$step_id.field.path` — resolved by pure code, never by the model.

### 4.2 SQL Agent — pipeline

1. **Entity + time resolution (code, not LLM).** Aliases → `System.name` via the graph's
   `aliases` property. "yesterday" / "last 7 days" / "during that alert" → a concrete
   `[t0, t1)` against a frozen `NOW` anchor in config. *This removes the largest source of
   run-to-run nondeterminism in any text-to-SQL system.*
2. **Schema linking.** 700 columns will not fit usefully in a prompt. Retrieve candidate
   columns from `sensor_catalog` by lexical + embedding match on tag name / description /
   family, keep top-k (~15) plus the resolved tables. Neo4j's schema-filtering study found
   exact-match pruning cut 95th-percentile prompt tokens to about one-sixth with ~2.7× cost
   savings and accuracy *up* for smaller models; RSL-SQL reports 94% strict recall while
   removing 83% of columns. The same principle applies verbatim here.
3. **Generation.** Claude with structured output returning `{sql, tables_used, columns_used,
   rationale}` — not a bare string.
4. **Validation before execution** (`sqlglot`): parses; exactly one statement; `SELECT`/CTE
   only; no DDL/DML/`COPY`/`pg_read_file`; every table ∈ allowlist; every column ∈ the
   catalog for that table; `LIMIT` injected if absent; then `EXPLAIN` as a dry run.
5. **Execution** as `mas_reader` with `statement_timeout`, a row cap, and a wall-clock guard.
6. **Bounded repair loop.** On validation or execution error, feed back `{sql, error}` and
   regenerate — max 2 attempts, then fail with a structured error the planner can react to.
   This is the execution-guided self-correction every strong text-to-SQL system uses
   (SQLens reports +20.5% on DIN-SQL from grounded error correction alone).
7. **Return** a `TableArtifact` plus the exact SQL, timing, and row count.

### 4.3 Graph Agent — pipeline

Same seven stages, Cypher-flavoured, plus one addition worth calling out:

- **Schema representation matters more than model choice.** Neo4j's own benchmarking found
  schema representation significantly changes Text2Cypher accuracy, and that even strong
  models land around ~30% execution-match on open benchmarks. So:
- **Template-first, generation-second.** Maintain ~10 pre-validated, parameterized "golden"
  Cypher queries covering the intents the spec names (tag count per system; latest alert on
  system; maintenance count + cost rollup; top consumed items for a maintenance event; alerts
  in a window; item cost by category; …). The agent attempts a typed intent match first and
  falls back to free generation otherwise. This is Neo4j's own recommended pattern —
  stability from deterministic function calls, with the LLM orchestrating rather than
  free-forming every query.
  **Important:** this is *not* the "hardcoded pathway" criterion 2 forbids. The forbidden
  thing is a hardcoded *orchestrator route*. Templating a leaf query, selected dynamically,
  is exactly the deterministic execution criterion 3 asks for. Say so in the README so it
  reads as a decision, not a shortcut.
- **Validation:** reject `CREATE|MERGE|DELETE|SET|REMOVE|DROP|DETACH|LOAD CSV` and write-mode
  procedure calls; check every label / relationship type / property against the live schema
  (`db.schema.visualization` + `db.propertyKeys`); verify relationship *direction*; `EXPLAIN`
  on the driver for syntax and planner validation without touching data; execute on a
  read-only user with `default_access_mode=READ`.

### 4.4 Python Coder Agent — pipeline

- **Input:** upstream artifacts pre-loaded into a namespace (`df_bfpa`, `alert_window`, …) so
  the model writes analysis, not I/O boilerplate; plus a task description and a library
  allowlist (`pandas`, `numpy`, `matplotlib`, `scipy`, `sklearn`, `statsmodels`).
- **Validation:** an AST walk rejecting `import` outside the allowlist, `__import__`, `eval`,
  `exec`, `compile`, `open`, dunder `getattr`, attribute access into
  `os`/`sys`/`socket`/`subprocess`/`shutil`, and any network call.
- **Execution:** a separate subprocess with `matplotlib.use("Agg")`, seeded `np.random`,
  CPU/memory rlimits, a hard timeout, cwd pinned to a per-run temp dir, figures saved as PNG.
- **Escalation path documented:** the production posture is a Docker sandbox
  (`--network=none --read-only --memory=512m --pids-limit=64 --cap-drop=ALL`). Be explicit
  that CPython is not a security boundary — PEP 551 says so outright — and that the AST
  allowlist is a *correctness and accident* guard with the container as the real boundary.
  Reviewers notice when a candidate knows the difference.
- **Repair loop** on traceback, max 2.
- **Analyses to have working for A7:** OLS / polynomial fit of head vs flow with the pump
  curve overlaid; correlation heatmap across a tag family; KMeans on
  (load, efficiency, vibration) labelling operating regions; rolling-z-score anomaly overlay
  on the alert window.

---

## 5. Layer 3 — The orchestrator

### 5.1 Pattern choice

**Plan-then-execute over a typed DAG, with bounded replanning.** Rationale for the README:
plan-then-execute fits multi-step tasks with inter-step dependencies and is materially
cheaper in tokens than ReAct (published comparisons put ReAct's input-token consumption
~35% higher), but it is brittle against surprises; ReAct is adaptive but myopic. The hybrid —
plan up front, execute the DAG, allow **one** replan on step failure or empty result — takes
the strengths of both and is easy to demonstrate.

### 5.2 Execution flow

```
User query
  │
  ├─ 1. Intake / guardrail    in-scope? → resolve aliases → freeze NOW → normalize
  │
  ├─ 2. Planner (LLM, structured output)
  │        emits Plan{steps:[{id, capability, inputs, depends_on, rationale}]}
  │        validated against the capability registry (Pydantic) — retry on schema failure
  │
  ├─ 3. DAG executor        topological sort; independent steps run concurrently;
  │                         `$step.field` refs resolved from the artifact store (pure code)
  │
  ├─ 4. Reflection          on error/empty → one bounded replan with the error in context
  │
  └─ 5. Synthesizer         final NL answer composed strictly from artifacts, each number
                            attributed to the agent + query that produced it
```

Worked example — the spec's flagship query, *"latest alert on BFP-A, plot the bearing
temperature during that alert window"*:

```json
{"steps":[
 {"id":"s1","capability":"graph.latest_alert_for_system",
  "inputs":{"system":"bfpa"}},
 {"id":"s2","capability":"sql.timeseries_window",
  "inputs":{"table":"$s1.result.system_sql_table",
            "tags":["pump_de_bearing_temp_c","pump_nde_bearing_temp_c"],
            "start_ts":"$s1.result.start_ts","end_ts":"$s1.result.end_ts"},
  "depends_on":["s1"]},
 {"id":"s3","capability":"python.plot_timeseries",
  "inputs":{"data":"$s2.artifact",
            "annotate_threshold":"$s1.result.threshold_value",
            "title":"BFP-A bearing temperature during alert $s1.result.alert_id"},
  "depends_on":["s2"]}]}
```

Note the spec's own expected flow has the Coder Agent query Postgres directly. Routing it
through the SQL Agent instead is cleaner (one validated DB path, one audit trail) and still
satisfies the described behaviour. Support both, default to the SQL-Agent path, and say why.

### 5.3 Proving "no hardcoded pathways"

- **Routing eval set:** ~40–50 queries with expected capability sequences, including
  paraphrases the planner has never seen and ~5 deliberately out-of-scope queries. Report
  routing accuracy and a confusion matrix in the notebook.
- **Grep evidence:** the README states that the orchestrator module contains zero
  query-string branching, and that the capability registry is the only routing surface. That
  claim is greppable — so make sure it is true.
- **Adding a capability requires zero orchestrator edits** — demonstrate this live in the
  notebook by registering a trivial new capability and watching the planner use it.

### 5.4 Model configuration (Anthropic)

| Role | Model | Why |
|---|---|---|
| Planner, SQL gen, Cypher gen, code gen | `claude-opus-5` ($5 / $25 per MTok, 1M context) | Correctness dominates cost; planning and query generation are the accuracy-critical paths |
| Optional bulk / eval-judge lane | `claude-sonnet-5` ($2 / $10) | Only if the eval harness gets expensive |

Mechanics that matter for this build:

- **Structured outputs** (`output_config: {format: {...}}`, or `client.messages.parse()`) for
  the Plan and for each agent's `{query, rationale}` payload — this is what makes the
  planner's output *structurally guaranteed executable* rather than parsed with regex.
  Use `strict: true` on tool definitions if you take the tool-use path instead.
- **Adaptive thinking** (`thinking: {type: "adaptive"}`) with `output_config.effort` —
  `high` for the planner, `low`/`medium` for the leaf query generators. No `temperature`
  (removed on current models) and no `budget_tokens` (rejected on Opus 5).
- **Prompt caching** is a large win here: the tag catalog + graph schema + few-shot examples
  form a stable multi-thousand-token prefix reused by every request. Render order is
  `tools → system → messages`; put the frozen schema block first behind a `cache_control`
  breakpoint and the per-question text last. Verify with `usage.cache_read_input_tokens` — if
  it is zero, something volatile (a timestamp, unsorted JSON) leaked into the prefix. The
  frozen `NOW` anchor makes this easy to keep clean.

---

## 6. Layer 4 — Demonstration notebook & evaluation

One notebook, top-to-bottom runnable, in this order:

1. **Environment & connectivity check** — versions, DB pings, row/node counts.
2. **Data generation report** — load-profile plot, tag-count table per system, event timeline
   table, and the `make validate` consistency report (all green).
3. **Schema tour** — Postgres column catalog sample; Neo4j schema visualization; the cross-DB
   invariant demonstrated live (graph tag count == Postgres column count).
4. **SQL Agent** — both spec examples, showing generated SQL, validator verdict, and result.
5. **Graph Agent** — all three spec examples, showing the generated/selected Cypher.
6. **Coder Agent** — line chart, bar chart, correlation heatmap, regression fit, and
   clustering into operating regions.
7. **Multi-agent** — the alert→plot query with the full plan JSON printed, then the plot with
   the alert window shaded and the threshold line drawn. Plus 2–3 harder composites (e.g.
   *"compare the 7-day bearing-temperature trend of BFP-A and BFP-B and tell me which had
   higher maintenance cost this year"* → 2 SQL + 1 graph + 1 coder step).
8. **Determinism proof** — same query ×5, hashes of plan / SQL / results identical.
9. **Routing evaluation** — accuracy table + confusion matrix over the eval set.
10. **Safety demo** — destructive and out-of-scope prompts blocked, with the validator's
    rejection message shown.
11. **Trace inspection** — one run's full JSON trace pretty-printed.

Keep heavy computation behind cached artifacts so the notebook re-runs in minutes, and commit
it **with outputs**.

---

## 7. Layer 5 — Repo, infra, ergonomics

```
├── docker-compose.yml          postgres:16, neo4j:5 (+APOC), jupyter
├── Makefile                    up | seed | validate | demo | eval | test | down
├── .env.example
├── docs/
│   ├── 01-problem-analysis.md  (this file)
│   ├── 02-architecture.md      diagrams, sequence flows, ADRs
│   └── 03-data-dictionary.md   generated from sensor_catalog
├── src/mas/
│   ├── config.py               pydantic-settings; MASTER_SEED, NOW_ANCHOR
│   ├── datagen/                load_profile.py, physics.py, events.py,
│   │                           tag_catalog.py, alerts.py, graph_seed.py
│   ├── db/                     postgres.py, neo4j.py, schema.sql, constraints.cypher
│   ├── agents/                 base.py, sql_agent.py, graph_agent.py, coder_agent.py
│   ├── validation/             sql_guard.py, cypher_guard.py, python_guard.py
│   ├── orchestrator/           planner.py, dag.py, blackboard.py, synthesizer.py
│   ├── llm/                    client.py (Anthropic), prompts/, caching.py
│   └── eval/                   routing_cases.py, determinism.py, consistency.py
├── notebooks/demonstration.ipynb
└── tests/
```

`make up && make seed && make validate` must be the entire setup. A reviewer with 20 minutes
and Docker should reach a green validation report without reading anything.

---

## 8. Data references — what exists publicly, and why we still generate

### 8.1 Reference datasets (for calibration, and to cite in the README)

| Dataset | What it gives us | Use here |
|---|---|---|
| **Kaggle `nphantawee/pump-sensor-data`** — 52 sensors, 1-min cadence, 5 months, `machine_status ∈ {NORMAL, BROKEN, RECOVERING}` | The closest public analogue in *shape*: wide table, 1-min sampling, labelled failure/recovery episodes (sensor semantics are unlabelled) | Calibrate sampling interval, noise σ, autocorrelation, and the failure→recovery pattern we inject as events |
| **SKAB (Skoltech Anomaly Benchmark)** — water-pump circuit, 8 sensors, 35 labelled single-anomaly experiments | Realistic anomaly *signatures* under controlled valve perturbations | Shape of injected anomaly transients: onset slope, duration, recovery |
| **NASA C-MAPSS turbofan** — 21 degradation signals + 3 operating variables, FD001–FD004, physics-simulated | Degradation *trajectory* shape toward failure | Slope and curvature of our bearing/seal degradation ramps |
| **NASA IMS bearing run-to-failure / CWRU bearing** | Bearing failure progression and vibration signatures | Vibration-family degradation behaviour |
| **ESPset** (electrical submersible pumps) and the *Data in Brief* E-motor centrifugal pump motor-current + vibration dataset | Coupled motor-current ↔ vibration behaviour under seeded faults | Cross-tag coupling between the motor and mechanical families |

### 8.2 Standards references — this is what makes the data "meaningful"

- **ISO 14224:2016** — equipment taxonomy (9 levels; equipment classes such as centrifugal
  pumps and turbines sit at level 7), failure modes recorded at component level as a
  "reliability thesaurus", and the equipment / failure / maintenance data categories.
  → our `equipment_class`, `failure_mode`, `maintenance_class` vocabularies and the
  MaintenanceLog field set. Written for oil & gas but applies directly to steam-turbine and
  auxiliary power-plant equipment.
- **ISO 20816-3 / ISO 10816-3** — vibration severity zones A/B/C/D on RMS velocity,
  10–1000 Hz, with roughly 1.12 / 2.8 / 7.1 mm/s boundaries for the relevant machine class
  (Zone C = remedial action, Zone D = immediate action). → vibration alarm setpoints and
  `vib_severity_zone`.
- **ISA-18.2 / IEC 62682** — alarm lifecycle, rationalization, prioritization, and alarm
  states (active/normal × acknowledged/unacknowledged; acknowledgment must not clear an alarm
  whose condition persists). → `Alert.priority`, `status`, `acknowledged_by`, and the
  deadband / on-delay in the detection pass.
- **KKS** — power-plant identification coding (`LA` feedwater system, `LAC` feedwater pump
  system, `LAB` feedwater piping, etc.). → `System.kks_code`, `Tag.kks_tag`.
- **ISA-5.1** — instrument identification letters (PT / TT / FT / VT / LT). → tag naming.
- Plant-practice anchors: modern BFPs run ~4500–6000 rpm (older designs higher, to ~8700);
  discharge pressure scales with unit size (tens of bar up to ~100 bar on large units);
  recommended BFP instrumentation includes suction pressure, strainer differential pressure,
  feedwater flow, discharge pressure and temperature, and bearing temperature at all
  bearings. CEPs draw from the condenser hotwell under vacuum and discharge at modest
  positive pressure toward the deaerator, feeding BFP suction.

### 8.3 Why generate rather than download

1. **Licensing & provenance.** Public pump datasets are anonymized single-machine records
   with unlabelled sensors — the Kaggle set explicitly does not say what each sensor
   measures. They cannot be mapped onto a five-asset plant ontology with named tags.
2. **The graph must agree with the telemetry.** No public dataset ships a matching
   maintenance / spares / alert graph. That joint consistency *is* the assignment.
3. **Reproducibility beats realism-by-download.** A seeded generator gives byte-identical
   30M-point datasets on any machine, which directly serves criterion 3.
4. **Volume is trivial to produce and non-trivial to license.** 700 tags × 43,200 steps is
   seconds of vectorized NumPy plus a `COPY`.

> The defensible sentence for the README: *"Telemetry is synthesized by a physics-driven
> generator whose structure, vocabularies, and thresholds derive from ISO 14224,
> ISO 20816-3, ISA-18.2 and KKS, with noise and event characteristics calibrated against
> public pump and turbine datasets (Kaggle pump-sensor, SKAB, C-MAPSS)."*
> That is much stronger than "we downloaded a CSV."

---

## 9. Prior art — is something like this already cleanly built?

**Short answer: no.** There is no public repository implementing this assignment —
BFP/CEP/turbine assets, Neo4j-as-metadata + Postgres-as-telemetry with an enforced separation
rule, and a three-agent orchestrator. Searched GitHub topics, Neo4j Labs, and the
multi-agent orchestration ecosystem; the closest matches are all partial.

| Project / work | Overlap | What to borrow | Gap vs. this assignment |
|---|---|---|---|
| **`neo4j-field/ps-genai-agents`** | Closest architectural relative. LangGraph workflows; a Text2Cypher agent that generates→validates→corrects→executes; a Matplotlib/Seaborn viz agent; a guardrail node for scope; question-parsing for multi-part inputs; a Cypher-query vector store for few-shot retrieval | The **validation taxonomy** (syntax, no-writes, relationship direction, property mapping, label / rel-type / property existence) and the few-shot vector store — both map straight onto our Graph Agent | Graph-only. No SQL agent, no cross-database handoff, no telemetry, no data generation |
| **`taka-hs/neo4j-adk-multiagents`** | Root orchestrator + sub-agents over Neo4j *and* Postgres (Google ADK) | The **pre-validated query** pattern — stability from deterministic calls with the LLM orchestrating | Investment-research domain; not industrial; no code-execution agent |
| **Neo4j Text2Cypher (2024/2025) datasets + schema-filtering paper** | Technique reference | Schema representation and pruning strategy; the "enhanced schema with example values" format; the finding that exact-match pruning cuts prompt tokens ~6× | Benchmark / technique, not a system |
| **MAC-SQL / CHESS / CHASE-SQL / RSL-SQL / LitE-SQL / SQLens** | Multi-agent text-to-SQL technique lineage | Schema linking → generation → execution-guided self-correction → selection. Also the sobering calibration: BIRD execution accuracy tops out around 73%, which is the argument for a template-first hybrid on our known intents | Benchmark systems; no graph, no telemetry |
| **`Alejandro-Candela/agentic-rag-knowledge-graph`** | Postgres + Neo4j in one agentic system | Dual-store wiring patterns | pgvector RAG, not telemetry analytics |
| **LangChain `SQLDatabaseToolkit`, Vanna, `GraphCypherQAChain`** | Off-the-shelf single-DB agents | Reference implementations | Too permissive for the determinism criterion — they hand model output to the driver with minimal guarding |

**Implication:** nothing to fork; the design above is the contribution. The two places to lift
real work from are ps-genai-agents' Cypher validation module structure and the text-to-SQL
literature's schema-linking + self-correction loop. Cite both in the README — showing you
surveyed the field reads as engineering maturity, not derivative work.

**On frameworks:** I recommend **not** using LangGraph here. Its graph topology is declared
statically, so dynamic plan generation would sit *on top* of it anyway; hand-rolling a
~300-line typed DAG executor makes the sequencing logic — literally criterion 2 — visible and
auditable in your own code instead of buried in a framework. Use Pydantic for contracts and
the Anthropic SDK's structured outputs for the plan. Record the choice as an ADR.

---

## 10. Risks & the 7-day plan

| Risk | Impact | Mitigation |
|---|---|---|
| Data generator eats the week | Everything downstream slips | Timebox to 2 days. Build the tag catalog as **data** (YAML/CSV) so adding tags is not coding |
| Text2Cypher accuracy on a novel schema | Graph Agent flakes on demo day | Template-first hybrid with ~10 golden parameterized queries; free generation only as fallback |
| Alert windows plot as flat lines | Kills the flagship demo and criterion 1 | Event timeline drives both telemetry and alerts; consistency test #3 fails the build otherwise |
| Notebook that only runs on your laptop | Criterion 4 | Docker Compose + `make`; re-run the notebook clean before submitting |
| Over-engineering the sandbox | Time sink | Subprocess + AST allowlist ships; document Docker as the production escalation |

**Day plan**

- **D1** — Repo skeleton, Docker Compose, config, tag catalogs for all 5 systems (as data files), Postgres DDL, Neo4j constraints.
- **D2** — Generator: load profile → physics → noise → events → alert detection → `COPY` load → graph seed. `make validate` green.
- **D3** — SQL Agent end-to-end with validator, read-only role, repair loop. A1–A2 passing.
- **D4** — Graph Agent with golden templates + fallback generation + validator. A3–A5 passing.
- **D5** — Coder Agent with AST guard + subprocess sandbox. A6–A7 passing. Artifact store.
- **D6** — Orchestrator: planner (structured output), DAG executor, replan, synthesizer. A8 + composites passing. Routing eval set.
- **D7** — Notebook, determinism + routing eval runs, README with ADRs and the ambiguity rulings, final clean re-run.

---

## 11. Sources

**Prior art & technique**
- [neo4j-field/ps-genai-agents](https://github.com/neo4j-field/ps-genai-agents)
- [Benchmarking using the Neo4j Text2Cypher (2024) dataset](https://neo4j.com/blog/developer/benchmarking-neo4j-text2cypher-dataset/)
- [The Impact of Schema Representation in the Text2Cypher Task](https://medium.com/neo4j/the-impact-of-schema-representation-in-the-text2cypher-task-f96947599b5f)
- [Enhancing Text2Cypher with Schema Filtering (arXiv 2505.05118)](https://arxiv.org/html/2505.05118v1)
- [Text2Cypher: Bridging Natural Language and Graph Databases (ACL 2025)](https://aclanthology.org/2025.genaik-1.11.pdf)
- [Multi-Agent GraphRAG: A Text-to-Cypher Framework for Labeled Property Graphs](https://arxiv.org/pdf/2511.08274)
- [RSL-SQL: Robust Schema Linking in Text-to-SQL Generation](https://arxiv.org/pdf/2411.00073)
- [LitE-SQL: schema linking + execution-guided self-correction](https://arxiv.org/html/2510.09014v1)
- [SQLens: error detection and correction in Text-to-SQL](https://arxiv.org/html/2506.04494v1)
- [G²SQL: guided & guarded Text-to-SQL with two-stage verification](https://www.sciencedirect.com/science/article/abs/pii/S0957417426001892)
- [taka-hs/neo4j-adk-multiagents](https://github.com/taka-hs/neo4j-adk-multiagents)
- [Alejandro-Candela/agentic-rag-knowledge-graph](https://github.com/Alejandro-Candela/agentic-rag-knowledge-graph)
- [ReAct vs. Plan-and-Execute: Agent Architecture Guide](https://atlan.com/know/ai-agent/react-vs-plan-and-execute-agent-architecture/)
- [Architecting Resilient LLM Agents: Secure Plan-then-Execute (arXiv 2509.08646)](https://arxiv.org/pdf/2509.08646)
- [From Static Templates to Dynamic Runtime Graphs: Workflow Optimization for LLM Agents](https://arxiv.org/html/2603.22386v1)

**Sandboxing**
- [Setting Up a Secure Python Sandbox for LLM Agents](https://dida.do/blog/setting-up-a-secure-python-sandbox-for-llm-agents)
- [Code Sandboxes for LLMs and AI Agents](https://amirmalik.net/2025/03/07/code-sandboxes-for-llm-ai-agents)
- [LLM Code Execution Tools & Sandboxing](https://apxml.com/courses/building-advanced-llm-agent-tools/chapter-5-advanced-tool-functionality/code-execution-tools)

**Data references**
- [Kaggle pump_sensor_data (52 sensors, 1-min)](https://www.kaggle.com/datasets/nphantawee/pump-sensor-data)
- [SKAB — Skoltech Anomaly Benchmark](https://github.com/JeongUgSeo/SKAB_original)
- [awesome-bearing-dataset (NASA IMS, CWRU, …)](https://github.com/VictorBauler/awesome-bearing-dataset)
- [ESPset: vibration dataset for electrical submersible pumps](https://www.sciencedirect.com/science/article/abs/pii/S095070512400087X)
- [Motor current and vibration dataset for an E-motor-driven centrifugal pump](https://www.sciencedirect.com/science/article/pii/S235234092301017X)
- [Short-Horizon Predictive Maintenance of Industrial Pumps (arXiv 2508.19974)](https://arxiv.org/html/2508.19974v1)

**Standards & domain**
- [ISO 14224:2016](https://www.iso.org/standard/64076.html) · [Equipment taxonomy explained](https://cpcongroup.com/insights/article/iso-14224-equipment-taxonomy/) · [Power plant asset hierarchy & ISO 14224](https://oxmaint.com/industries/power-plant/power-plant-asset-hierarchy-iso-14224-taxonomy-programs)
- [ISO 20816-3 vibration severity guide](https://vibromera.eu/glossary/iso-20816-3/) · [ISO 10816-3 zones A/B/C/D](https://acoem.us/blog/other-topics/understanding-the-iso-10816-3-vibration-severity-chart/)
- [ISA-18 series of standards](https://www.isa.org/standards-and-publications/isa-standards/isa-18-series-of-standards) · [ISA 18.2 alarm management in process plants](https://instrumentationtools.com/isa-18-2-alarm-management-in-process-plants/)
- [KKS Handbook for Power Plant Identification](https://www.scribd.com/document/273071456/KKS-Handbook-Rev-B)
- [Boiler feed pump (KSB pump lexicon)](https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/boiler-feed-pump-1118674) · [BFP Q&A: design, operation, maintenance](https://www.powerplantandcalculations.com/2021/03/questions-answers-boiler-feedpumps-design-operation-maintenance.html)
- [Steam turbine monitoring — an introduction (Meggitt)](https://meggittsensing.com/energy/expert-articles/steam-turbine-monitoring-an-introduction/) · [Guide to steam turbine vibration monitoring](https://www.forbesmarshall.com/blogs/turbine-vibration-monitoring-guide/)
- [Pump affinity laws (PDHonline M125)](https://www.pdhonline.com/courses/m125/m125content.pdf) · [Centrifugal pumps: curves, NPSH, affinity laws](https://www.cntecho.com/centrifugal-pump-technical-guide)

**Database design**
- [Timescale: narrow, medium or wide table layout](https://www.timescale.com/blog/best-practices-for-time-series-data-modeling-narrow-medium-or-wide-table-layout-2/)
- [Speed up time-series ingestion by partitioning (AWS)](https://aws.amazon.com/blogs/database/speed-up-time-series-data-ingestion-by-partitioning-tables-on-amazon-rds-for-postgresql/)
- [Native partitioning with Postgres and pg_partman](https://www.crunchydata.com/blog/native-partitioning-with-postgres)
