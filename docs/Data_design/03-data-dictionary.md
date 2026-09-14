# Data Dictionary

_Auto-generated from the catalog on 2026-09-08 05:03 UTC. Do not edit by hand — run `make data-dict`._

Total: **636 tags** across **5 systems**, **94 spare-part items**.

## `bfpa` — Boiler Feed Pump A

- KKS: `LAC10 AP001` · class: centrifugal_pump / boiler_feed_pump · criticality: high
- 130 tags · rated 9000 kW, 5200 rpm

| tag_name | family | unit | normal | alarms (lo/lolo·hi/hihi) | description |
|---|---|---|---|---|---|
| `bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing #1 metal temperature |
| `bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing #2 metal temperature |
| `bearing_temp_3` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing #3 metal temperature |
| `bearing_temp_4` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing #4 metal temperature |
| `vibration_x_1` | vibration | um | 5–60 | / · 90/150 | BFP-A bearing #1 shaft vibration X |
| `vibration_y_1` | vibration | um | 5–60 | / · 90/150 | BFP-A bearing #1 shaft vibration Y |
| `vibration_x_2` | vibration | um | 5–60 | / · 90/150 | BFP-A bearing #2 shaft vibration X |
| `vibration_y_2` | vibration | um | 5–60 | / · 90/150 | BFP-A bearing #2 shaft vibration Y |
| `vibration_overall` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A overall casing vibration velocity |
| `vibration_axial` | vibration | mm | -1–1 | / · / | BFP-A overall axial vibration velocity |
| `shaft_speed` | speed | rpm | 0–6000 | / · / | BFP-A shaft rotational speed |
| `lube_oil_pressure` | pressure | bar | 1.5–3 | 1.2/0.9 · / | BFP-A lube oil header pressure |
| `lube_oil_temp` | temperature | degC | 35–55 | / · 60/65 | BFP-A lube oil supply temperature |
| `lube_oil_level` | level | % | 40–90 | / · / | BFP-A lube oil tank level |
| `ambient_temp` | temperature | degC | 15–35 | / · / | BFP-A ambient air temperature |
| `suction_pressure` | pressure | bar | 3–12 | / · / | BFP-A suction pressure |
| `discharge_pressure` | pressure | bar | 60–185 | / · / | BFP-A discharge pressure |
| `differential_pressure` | pressure | bar | 0.1–1.5 | / · 1.6/2 | BFP-A differential pressure |
| `flow_rate` | flow | t/h | 0–320 | / · / | BFP-A feedwater flow rate |
| `motor_current` | electrical | A | 0–600 | / · / | BFP-A motor current |
| `motor_power` | electrical | kW | 0–9000 | / · / | BFP-A motor active power |
| `motor_voltage` | electrical | V | 6200–6800 | / · / | BFP-A motor terminal voltage |
| `winding_temp_1` | temperature | degC | 55–110 | / · 120/130 | BFP-A motor winding U temperature |
| `winding_temp_2` | temperature | degC | 55–110 | / · 120/130 | BFP-A motor winding V temperature |
| `winding_temp_3` | temperature | degC | 55–110 | / · 120/130 | BFP-A motor winding W temperature |
| `bearing_temp_5` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing temp 5 |
| `bearing_temp_6` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing temp 6 |
| `bearing_temp_7` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing temp 7 |
| `bearing_temp_8` | temperature | degC | 45–85 | / · 90/100 | BFP-A bearing temp 8 |
| `thrust_bearing_temp_active` | temperature | degC | 45–85 | / · 90/100 | BFP-A thrust bearing temp active |
| `thrust_bearing_temp_inactive` | temperature | degC | 45–85 | / · 90/100 | BFP-A thrust bearing temp inactive |
| `bearing_vibration_1` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A bearing vibration 1 |
| `bearing_vibration_2` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A bearing vibration 2 |
| `bearing_vibration_3` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A bearing vibration 3 |
| `bearing_vibration_4` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A bearing vibration 4 |
| `stage_pressure_1` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 1 |
| `stage_pressure_2` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 2 |
| `stage_pressure_3` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 3 |
| `stage_pressure_4` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 4 |
| `stage_pressure_5` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 5 |
| `stage_pressure_6` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 6 |
| `stage_pressure_7` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 7 |
| `stage_pressure_8` | pressure | bar | 10–180 | / · / | BFP-A stage pressure 8 |
| `recirc_flow` | flow | t/h | 0–300 | / · / | BFP-A recirc flow |
| `min_flow_valve_position` | level | % | 0–100 | / · / | BFP-A min flow valve position |
| `discharge_valve_position` | level | % | 0–100 | / · / | BFP-A discharge valve position |
| `suction_strainer_dp` | pressure | bar | 0.1–1.5 | / · 1.6/2 | BFP-A suction strainer dp |
| `npsh_available` | pressure | m | 6–18 | 4/2.5 · / | BFP-A npsh available |
| `npsh_margin` | pressure | m | 3–12 | 1.5/0.5 · / | BFP-A npsh margin |
| `balance_leakoff_flow` | flow | lpm | 0–8 | / · / | BFP-A balance leakoff flow |
| `balance_leakoff_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A balance leakoff temp |
| `suction_temp` | temperature | degC | 140–180 | / · 190/200 | BFP-A suction temp |
| `discharge_temp` | temperature | degC | 150–195 | / · 205/215 | BFP-A discharge temp |
| `temp_rise` | temperature | degC | 2–18 | / · 21/24 | BFP-A temp rise |
| `deaerator_level` | level | % | 20–80 | / · / | BFP-A deaerator level |
| `deaerator_pressure` | pressure | bar | 5–12 | / · / | BFP-A deaerator pressure |
| `gland_seal_pressure` | pressure | bar | 1–4 | 1.2/0.8 · / | BFP-A gland seal pressure |
| `gland_seal_flow` | flow | lpm | 0–8 | / · / | BFP-A gland seal flow |
| `mech_seal_temp_1` | temperature | degC | 30–80 | / · 85/90 | BFP-A mech seal temp 1 |
| `mech_seal_temp_2` | temperature | degC | 30–80 | / · 85/90 | BFP-A mech seal temp 2 |
| `seal_leakage_rate` | flow | lpm | 0–8 | / · 4/6 | BFP-A seal leakage rate |
| `lube_oil_filter_dp` | pressure | bar | 0.1–1.5 | / · 1.6/2 | BFP-A lube oil filter dp |
| `lube_oil_supply_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A lube oil supply temp |
| `lube_oil_return_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A lube oil return temp |
| `lube_oil_cooler_inlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A lube oil cooler inlet temp |
| `lube_oil_cooler_outlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A lube oil cooler outlet temp |
| `lube_oil_flow` | flow | lpm | 20–120 | / · / | BFP-A lube oil flow |
| `lube_oil_water_content` | chemistry | ppm | 50–400 | / · / | BFP-A lube oil water content |
| `lube_oil_particle_count` | chemistry | count/ml | 100–2000 | / · / | BFP-A lube oil particle count |
| `aux_oil_pump_pressure` | pressure | bar | 1.5–3.5 | / · / | BFP-A aux oil pump pressure |
| `motor_current_phase_1` | electrical | A | 0–600 | / · / | BFP-A motor current phase 1 |
| `motor_current_phase_2` | electrical | A | 0–600 | / · / | BFP-A motor current phase 2 |
| `motor_current_phase_3` | electrical | A | 0–600 | / · / | BFP-A motor current phase 3 |
| `motor_voltage_phase_1` | electrical | V | 6200–6800 | / · / | BFP-A motor voltage phase 1 |
| `motor_voltage_phase_2` | electrical | V | 6200–6800 | / · / | BFP-A motor voltage phase 2 |
| `motor_voltage_phase_3` | electrical | V | 6200–6800 | / · / | BFP-A motor voltage phase 3 |
| `motor_power_factor` | electrical |  | 0.8–0.95 | / · / | BFP-A motor power factor |
| `motor_frequency` | electrical | Hz | 49.8–50.2 | / · / | BFP-A motor frequency |
| `motor_bearing_temp_de` | temperature | degC | 45–85 | / · 90/100 | BFP-A motor bearing temp de |
| `motor_bearing_temp_nde` | temperature | degC | 45–85 | / · 90/100 | BFP-A motor bearing temp nde |
| `motor_vibration_de` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A motor vibration de |
| `motor_vibration_nde` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A motor vibration nde |
| `motor_cooling_air_inlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A motor cooling air inlet temp |
| `motor_cooling_air_outlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A motor cooling air outlet temp |
| `motor_insulation_resistance` | electrical | Mohm | 50–500 | / · / | BFP-A motor insulation resistance |
| `winding_temp_4` | temperature | degC | 55–110 | / · 120/130 | BFP-A winding temp 4 |
| `winding_temp_5` | temperature | degC | 55–110 | / · 120/130 | BFP-A winding temp 5 |
| `winding_temp_6` | temperature | degC | 55–110 | / · 120/130 | BFP-A winding temp 6 |
| `coupling_scoop_position` | level | % | 0–100 | / · / | BFP-A coupling scoop position |
| `coupling_oil_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-A coupling oil temp |
| `coupling_slip` | derived | % | 1–6 | / · / | BFP-A coupling slip |
| `coupling_input_speed` | speed | rpm | 0–6000 | / · / | BFP-A coupling input speed |
| `coupling_output_speed` | speed | rpm | 0–6000 | / · / | BFP-A coupling output speed |
| `booster_suction_pressure` | pressure | bar | 3–10 | / · / | BFP-A booster suction pressure |
| `booster_discharge_pressure` | pressure | bar | 15–45 | / · / | BFP-A booster discharge pressure |
| `booster_flow` | flow | t/h | 0–300 | / · / | BFP-A booster flow |
| `booster_motor_current` | electrical | A | 0–600 | / · / | BFP-A booster motor current |
| `booster_bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | BFP-A booster bearing temp 1 |
| `booster_bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | BFP-A booster bearing temp 2 |
| `booster_vibration` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A booster vibration |
| `feedwater_conductivity` | chemistry | uS/cm | 0.05–0.35 | / · / | BFP-A feedwater conductivity |
| `feedwater_ph` | chemistry | pH | 8.8–9.4 | / · / | BFP-A feedwater ph |
| `feedwater_dissolved_oxygen` | chemistry | ppb | 2–20 | / · / | BFP-A feedwater dissolved oxygen |
| `feedwater_silica` | chemistry | ppb | 2–20 | / · / | BFP-A feedwater silica |
| `feedwater_iron` | chemistry | ppb | 1–15 | / · / | BFP-A feedwater iron |
| `axial_displacement` | vibration | mm | -1–1 | / · / | BFP-A axial displacement |
| `shaft_eccentricity` | vibration | um | 10–50 | / · 80/120 | BFP-A shaft eccentricity |
| `thrust_position` | vibration | mm | -1–1 | / · / | BFP-A thrust position |
| `casing_vibration_h` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A casing vibration h |
| `casing_vibration_v` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A casing vibration v |
| `casing_vibration_a` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-A casing vibration a |
| `pump_head` | derived |  | 0–100 | / · / | BFP-A pump head |
| `hydraulic_power` | derived |  | 0–100 | / · / | BFP-A hydraulic power |
| `pump_efficiency` | derived |  | 0–100 | / · / | BFP-A pump efficiency |
| `specific_energy` | derived |  | 0–100 | / · / | BFP-A specific energy |
| `flow_deviation_from_bep` | derived |  | 0–100 | / · / | BFP-A flow deviation from bep |
| `vibration_severity_zone` | derived |  | 0–100 | / · / | BFP-A vibration severity zone |
| `bearing_temp_margin` | derived |  | 0–100 | / · / | BFP-A bearing temp margin |
| `health_index` | derived |  | 0–100 | / · / | BFP-A health index |
| `power_consumed` | derived |  | 0–100 | / · / | BFP-A power consumed |
| `cavitation_index` | derived |  | 0–100 | / · / | BFP-A cavitation index |
| `running_hours` | derived | h | 0–1e+06 | / · / | BFP-A running hours |
| `start_count` | derived | count | 0–100000 | / · / | BFP-A start count |
| `pump_running` | status | bool | 0–1 | / · / | BFP-A pump running |
| `standby_mode` | status | bool | 0–1 | / · / | BFP-A standby mode |
| `auto_mode` | status | bool | 0–1 | / · / | BFP-A auto mode |
| `trip_status` | status | bool | 0–1 | / · / | BFP-A trip status |
| `alarm_active` | status | bool | 0–1 | / · / | BFP-A alarm active |
| `recirc_valve_open` | status | bool | 0–1 | / · / | BFP-A recirc valve open |
| `aux_oil_pump_running` | status | bool | 0–1 | / · / | BFP-A aux oil pump running |

## `bfpb` — Boiler Feed Pump B

- KKS: `LAC20 AP001` · class: centrifugal_pump / boiler_feed_pump · criticality: high
- 130 tags · rated 9000 kW, 5200 rpm

| tag_name | family | unit | normal | alarms (lo/lolo·hi/hihi) | description |
|---|---|---|---|---|---|
| `bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing #1 metal temperature |
| `bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing #2 metal temperature |
| `bearing_temp_3` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing #3 metal temperature |
| `bearing_temp_4` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing #4 metal temperature |
| `vibration_x_1` | vibration | um | 5–60 | / · 90/150 | BFP-B bearing #1 shaft vibration X |
| `vibration_y_1` | vibration | um | 5–60 | / · 90/150 | BFP-B bearing #1 shaft vibration Y |
| `vibration_x_2` | vibration | um | 5–60 | / · 90/150 | BFP-B bearing #2 shaft vibration X |
| `vibration_y_2` | vibration | um | 5–60 | / · 90/150 | BFP-B bearing #2 shaft vibration Y |
| `vibration_overall` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B overall casing vibration velocity |
| `vibration_axial` | vibration | mm | -1–1 | / · / | BFP-B overall axial vibration velocity |
| `shaft_speed` | speed | rpm | 0–6000 | / · / | BFP-B shaft rotational speed |
| `lube_oil_pressure` | pressure | bar | 1.5–3 | 1.2/0.9 · / | BFP-B lube oil header pressure |
| `lube_oil_temp` | temperature | degC | 35–55 | / · 60/65 | BFP-B lube oil supply temperature |
| `lube_oil_level` | level | % | 40–90 | / · / | BFP-B lube oil tank level |
| `ambient_temp` | temperature | degC | 15–35 | / · / | BFP-B ambient air temperature |
| `suction_pressure` | pressure | bar | 3–12 | / · / | BFP-B suction pressure |
| `discharge_pressure` | pressure | bar | 60–185 | / · / | BFP-B discharge pressure |
| `differential_pressure` | pressure | bar | 0.1–1.5 | / · 1.6/2 | BFP-B differential pressure |
| `flow_rate` | flow | t/h | 0–320 | / · / | BFP-B feedwater flow rate |
| `motor_current` | electrical | A | 0–600 | / · / | BFP-B motor current |
| `motor_power` | electrical | kW | 0–9000 | / · / | BFP-B motor active power |
| `motor_voltage` | electrical | V | 6200–6800 | / · / | BFP-B motor terminal voltage |
| `winding_temp_1` | temperature | degC | 55–110 | / · 120/130 | BFP-B motor winding U temperature |
| `winding_temp_2` | temperature | degC | 55–110 | / · 120/130 | BFP-B motor winding V temperature |
| `winding_temp_3` | temperature | degC | 55–110 | / · 120/130 | BFP-B motor winding W temperature |
| `bearing_temp_5` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing temp 5 |
| `bearing_temp_6` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing temp 6 |
| `bearing_temp_7` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing temp 7 |
| `bearing_temp_8` | temperature | degC | 45–85 | / · 90/100 | BFP-B bearing temp 8 |
| `thrust_bearing_temp_active` | temperature | degC | 45–85 | / · 90/100 | BFP-B thrust bearing temp active |
| `thrust_bearing_temp_inactive` | temperature | degC | 45–85 | / · 90/100 | BFP-B thrust bearing temp inactive |
| `bearing_vibration_1` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B bearing vibration 1 |
| `bearing_vibration_2` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B bearing vibration 2 |
| `bearing_vibration_3` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B bearing vibration 3 |
| `bearing_vibration_4` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B bearing vibration 4 |
| `stage_pressure_1` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 1 |
| `stage_pressure_2` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 2 |
| `stage_pressure_3` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 3 |
| `stage_pressure_4` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 4 |
| `stage_pressure_5` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 5 |
| `stage_pressure_6` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 6 |
| `stage_pressure_7` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 7 |
| `stage_pressure_8` | pressure | bar | 10–180 | / · / | BFP-B stage pressure 8 |
| `recirc_flow` | flow | t/h | 0–300 | / · / | BFP-B recirc flow |
| `min_flow_valve_position` | level | % | 0–100 | / · / | BFP-B min flow valve position |
| `discharge_valve_position` | level | % | 0–100 | / · / | BFP-B discharge valve position |
| `suction_strainer_dp` | pressure | bar | 0.1–1.5 | / · 1.6/2 | BFP-B suction strainer dp |
| `npsh_available` | pressure | m | 6–18 | 4/2.5 · / | BFP-B npsh available |
| `npsh_margin` | pressure | m | 3–12 | 1.5/0.5 · / | BFP-B npsh margin |
| `balance_leakoff_flow` | flow | lpm | 0–8 | / · / | BFP-B balance leakoff flow |
| `balance_leakoff_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B balance leakoff temp |
| `suction_temp` | temperature | degC | 140–180 | / · 190/200 | BFP-B suction temp |
| `discharge_temp` | temperature | degC | 150–195 | / · 205/215 | BFP-B discharge temp |
| `temp_rise` | temperature | degC | 2–18 | / · 21/24 | BFP-B temp rise |
| `deaerator_level` | level | % | 20–80 | / · / | BFP-B deaerator level |
| `deaerator_pressure` | pressure | bar | 5–12 | / · / | BFP-B deaerator pressure |
| `gland_seal_pressure` | pressure | bar | 1–4 | 1.2/0.8 · / | BFP-B gland seal pressure |
| `gland_seal_flow` | flow | lpm | 0–8 | / · / | BFP-B gland seal flow |
| `mech_seal_temp_1` | temperature | degC | 30–80 | / · 85/90 | BFP-B mech seal temp 1 |
| `mech_seal_temp_2` | temperature | degC | 30–80 | / · 85/90 | BFP-B mech seal temp 2 |
| `seal_leakage_rate` | flow | lpm | 0–8 | / · 4/6 | BFP-B seal leakage rate |
| `lube_oil_filter_dp` | pressure | bar | 0.1–1.5 | / · 1.6/2 | BFP-B lube oil filter dp |
| `lube_oil_supply_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B lube oil supply temp |
| `lube_oil_return_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B lube oil return temp |
| `lube_oil_cooler_inlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B lube oil cooler inlet temp |
| `lube_oil_cooler_outlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B lube oil cooler outlet temp |
| `lube_oil_flow` | flow | lpm | 20–120 | / · / | BFP-B lube oil flow |
| `lube_oil_water_content` | chemistry | ppm | 50–400 | / · / | BFP-B lube oil water content |
| `lube_oil_particle_count` | chemistry | count/ml | 100–2000 | / · / | BFP-B lube oil particle count |
| `aux_oil_pump_pressure` | pressure | bar | 1.5–3.5 | / · / | BFP-B aux oil pump pressure |
| `motor_current_phase_1` | electrical | A | 0–600 | / · / | BFP-B motor current phase 1 |
| `motor_current_phase_2` | electrical | A | 0–600 | / · / | BFP-B motor current phase 2 |
| `motor_current_phase_3` | electrical | A | 0–600 | / · / | BFP-B motor current phase 3 |
| `motor_voltage_phase_1` | electrical | V | 6200–6800 | / · / | BFP-B motor voltage phase 1 |
| `motor_voltage_phase_2` | electrical | V | 6200–6800 | / · / | BFP-B motor voltage phase 2 |
| `motor_voltage_phase_3` | electrical | V | 6200–6800 | / · / | BFP-B motor voltage phase 3 |
| `motor_power_factor` | electrical |  | 0.8–0.95 | / · / | BFP-B motor power factor |
| `motor_frequency` | electrical | Hz | 49.8–50.2 | / · / | BFP-B motor frequency |
| `motor_bearing_temp_de` | temperature | degC | 45–85 | / · 90/100 | BFP-B motor bearing temp de |
| `motor_bearing_temp_nde` | temperature | degC | 45–85 | / · 90/100 | BFP-B motor bearing temp nde |
| `motor_vibration_de` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B motor vibration de |
| `motor_vibration_nde` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B motor vibration nde |
| `motor_cooling_air_inlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B motor cooling air inlet temp |
| `motor_cooling_air_outlet_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B motor cooling air outlet temp |
| `motor_insulation_resistance` | electrical | Mohm | 50–500 | / · / | BFP-B motor insulation resistance |
| `winding_temp_4` | temperature | degC | 55–110 | / · 120/130 | BFP-B winding temp 4 |
| `winding_temp_5` | temperature | degC | 55–110 | / · 120/130 | BFP-B winding temp 5 |
| `winding_temp_6` | temperature | degC | 55–110 | / · 120/130 | BFP-B winding temp 6 |
| `coupling_scoop_position` | level | % | 0–100 | / · / | BFP-B coupling scoop position |
| `coupling_oil_temp` | temperature | degC | 30–80 | / · 85/90 | BFP-B coupling oil temp |
| `coupling_slip` | derived | % | 1–6 | / · / | BFP-B coupling slip |
| `coupling_input_speed` | speed | rpm | 0–6000 | / · / | BFP-B coupling input speed |
| `coupling_output_speed` | speed | rpm | 0–6000 | / · / | BFP-B coupling output speed |
| `booster_suction_pressure` | pressure | bar | 3–10 | / · / | BFP-B booster suction pressure |
| `booster_discharge_pressure` | pressure | bar | 15–45 | / · / | BFP-B booster discharge pressure |
| `booster_flow` | flow | t/h | 0–300 | / · / | BFP-B booster flow |
| `booster_motor_current` | electrical | A | 0–600 | / · / | BFP-B booster motor current |
| `booster_bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | BFP-B booster bearing temp 1 |
| `booster_bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | BFP-B booster bearing temp 2 |
| `booster_vibration` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B booster vibration |
| `feedwater_conductivity` | chemistry | uS/cm | 0.05–0.35 | / · / | BFP-B feedwater conductivity |
| `feedwater_ph` | chemistry | pH | 8.8–9.4 | / · / | BFP-B feedwater ph |
| `feedwater_dissolved_oxygen` | chemistry | ppb | 2–20 | / · / | BFP-B feedwater dissolved oxygen |
| `feedwater_silica` | chemistry | ppb | 2–20 | / · / | BFP-B feedwater silica |
| `feedwater_iron` | chemistry | ppb | 1–15 | / · / | BFP-B feedwater iron |
| `axial_displacement` | vibration | mm | -1–1 | / · / | BFP-B axial displacement |
| `shaft_eccentricity` | vibration | um | 10–50 | / · 80/120 | BFP-B shaft eccentricity |
| `thrust_position` | vibration | mm | -1–1 | / · / | BFP-B thrust position |
| `casing_vibration_h` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B casing vibration h |
| `casing_vibration_v` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B casing vibration v |
| `casing_vibration_a` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | BFP-B casing vibration a |
| `pump_head` | derived |  | 0–100 | / · / | BFP-B pump head |
| `hydraulic_power` | derived |  | 0–100 | / · / | BFP-B hydraulic power |
| `pump_efficiency` | derived |  | 0–100 | / · / | BFP-B pump efficiency |
| `specific_energy` | derived |  | 0–100 | / · / | BFP-B specific energy |
| `flow_deviation_from_bep` | derived |  | 0–100 | / · / | BFP-B flow deviation from bep |
| `vibration_severity_zone` | derived |  | 0–100 | / · / | BFP-B vibration severity zone |
| `bearing_temp_margin` | derived |  | 0–100 | / · / | BFP-B bearing temp margin |
| `health_index` | derived |  | 0–100 | / · / | BFP-B health index |
| `power_consumed` | derived |  | 0–100 | / · / | BFP-B power consumed |
| `cavitation_index` | derived |  | 0–100 | / · / | BFP-B cavitation index |
| `running_hours` | derived | h | 0–1e+06 | / · / | BFP-B running hours |
| `start_count` | derived | count | 0–100000 | / · / | BFP-B start count |
| `pump_running` | status | bool | 0–1 | / · / | BFP-B pump running |
| `standby_mode` | status | bool | 0–1 | / · / | BFP-B standby mode |
| `auto_mode` | status | bool | 0–1 | / · / | BFP-B auto mode |
| `trip_status` | status | bool | 0–1 | / · / | BFP-B trip status |
| `alarm_active` | status | bool | 0–1 | / · / | BFP-B alarm active |
| `recirc_valve_open` | status | bool | 0–1 | / · / | BFP-B recirc valve open |
| `aux_oil_pump_running` | status | bool | 0–1 | / · / | BFP-B aux oil pump running |

## `cepa` — Condensate Extraction Pump A

- KKS: `LCB10 AP001` · class: centrifugal_pump / condensate_extraction_pump · criticality: medium
- 108 tags · rated 900 kW, 1480 rpm

| tag_name | family | unit | normal | alarms (lo/lolo·hi/hihi) | description |
|---|---|---|---|---|---|
| `bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | CEP-A bearing #1 metal temperature |
| `bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | CEP-A bearing #2 metal temperature |
| `bearing_temp_3` | temperature | degC | 45–85 | / · 90/100 | CEP-A bearing #3 metal temperature |
| `bearing_temp_4` | temperature | degC | 45–85 | / · 90/100 | CEP-A bearing #4 metal temperature |
| `vibration_x_1` | vibration | um | 5–60 | / · 90/150 | CEP-A bearing #1 shaft vibration X |
| `vibration_y_1` | vibration | um | 5–60 | / · 90/150 | CEP-A bearing #1 shaft vibration Y |
| `vibration_x_2` | vibration | um | 5–60 | / · 90/150 | CEP-A bearing #2 shaft vibration X |
| `vibration_y_2` | vibration | um | 5–60 | / · 90/150 | CEP-A bearing #2 shaft vibration Y |
| `vibration_overall` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A overall casing vibration velocity |
| `vibration_axial` | vibration | mm | -1–1 | / · / | CEP-A overall axial vibration velocity |
| `shaft_speed` | speed | rpm | 0–6000 | / · / | CEP-A shaft rotational speed |
| `lube_oil_pressure` | pressure | bar | 1.5–3 | 1.2/0.9 · / | CEP-A lube oil header pressure |
| `lube_oil_temp` | temperature | degC | 35–55 | / · 60/65 | CEP-A lube oil supply temperature |
| `lube_oil_level` | level | % | 40–90 | / · / | CEP-A lube oil tank level |
| `ambient_temp` | temperature | degC | 15–35 | / · / | CEP-A ambient air temperature |
| `suction_pressure` | pressure | bar | 3–12 | / · / | CEP-A suction pressure |
| `discharge_pressure` | pressure | bar | 60–185 | / · / | CEP-A discharge pressure |
| `differential_pressure` | pressure | bar | 0.1–1.5 | / · 1.6/2 | CEP-A differential pressure |
| `flow_rate` | flow | t/h | 0–320 | / · / | CEP-A feedwater flow rate |
| `motor_current` | electrical | A | 0–600 | / · / | CEP-A motor current |
| `motor_power` | electrical | kW | 0–9000 | / · / | CEP-A motor active power |
| `motor_voltage` | electrical | V | 6200–6800 | / · / | CEP-A motor terminal voltage |
| `winding_temp_1` | temperature | degC | 55–110 | / · 120/130 | CEP-A motor winding U temperature |
| `winding_temp_2` | temperature | degC | 55–110 | / · 120/130 | CEP-A motor winding V temperature |
| `winding_temp_3` | temperature | degC | 55–110 | / · 120/130 | CEP-A motor winding W temperature |
| `upper_guide_bearing_temp` | temperature | degC | 45–85 | / · 90/100 | CEP-A upper guide bearing temp |
| `lower_guide_bearing_temp` | temperature | degC | 45–85 | / · 90/100 | CEP-A lower guide bearing temp |
| `thrust_bearing_temp` | temperature | degC | 45–85 | / · 90/100 | CEP-A thrust bearing temp |
| `column_vibration_1` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A column vibration 1 |
| `column_vibration_2` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A column vibration 2 |
| `column_vibration_3` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A column vibration 3 |
| `motor_stool_vibration` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A motor stool vibration |
| `shaft_deflection` | vibration | um | 5–60 | / · 90/150 | CEP-A shaft deflection |
| `bowl_assembly_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-A bowl assembly temp |
| `line_shaft_vibration` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A line shaft vibration |
| `stage_pressure_1` | pressure | bar | 1–45 | / · / | CEP-A stage pressure 1 |
| `stage_pressure_2` | pressure | bar | 1–45 | / · / | CEP-A stage pressure 2 |
| `stage_pressure_3` | pressure | bar | 1–45 | / · / | CEP-A stage pressure 3 |
| `stage_pressure_4` | pressure | bar | 1–45 | / · / | CEP-A stage pressure 4 |
| `hotwell_level` | level | mm | 300–900 | / · / | CEP-A hotwell level |
| `condenser_vacuum` | pressure | mbara | 40–120 | / · / | CEP-A condenser vacuum |
| `condenser_pressure` | pressure | bar | 0.04–0.12 | / · / | CEP-A condenser pressure |
| `condensate_temp` | temperature | degC | 30–55 | / · 58/61 | CEP-A condensate temp |
| `air_ingress_rate` | chemistry | index | 0–1 | / · / | CEP-A air ingress rate |
| `cw_inlet_temp` | temperature | degC | 20–35 | / · 38/41 | CEP-A cw inlet temp |
| `cw_outlet_temp` | temperature | degC | 28–45 | / · 48/51 | CEP-A cw outlet temp |
| `condenser_ttd` | temperature | degC | 2–8 | / · 11/14 | CEP-A condenser ttd |
| `recirc_flow` | flow | t/h | 0–300 | / · / | CEP-A recirc flow |
| `min_flow_valve_position` | level | % | 0–100 | / · / | CEP-A min flow valve position |
| `discharge_valve_position` | level | % | 0–100 | / · / | CEP-A discharge valve position |
| `npsh_available` | pressure | m | 3–12 | 2/1 · / | CEP-A npsh available |
| `npsh_margin` | pressure | m | 1.5–8 | 0.8/0.3 · / | CEP-A npsh margin |
| `cavitation_index` | derived |  | 0–100 | / · / | CEP-A cavitation index |
| `suction_pressure_abs` | pressure | mbara | 40–120 | / · / | CEP-A suction pressure abs |
| `discharge_temp` | temperature | degC | 30–55 | / · 58/61 | CEP-A discharge temp |
| `deaerator_level` | level | % | 20–80 | / · / | CEP-A deaerator level |
| `condensate_conductivity` | chemistry | uS/cm | 0.05–0.35 | / · / | CEP-A condensate conductivity |
| `condensate_ph` | chemistry | pH | 8.8–9.4 | / · / | CEP-A condensate ph |
| `dissolved_oxygen` | chemistry | ppb | 2–20 | / · / | CEP-A dissolved oxygen |
| `sodium_content` | chemistry | ppb | 1–10 | / · / | CEP-A sodium content |
| `condensate_iron` | chemistry | ppb | 1–15 | / · / | CEP-A condensate iron |
| `gland_seal_water_flow` | flow | lpm | 0–8 | / · / | CEP-A gland seal water flow |
| `gland_seal_water_pressure` | pressure | bar | 1–4 | / · / | CEP-A gland seal water pressure |
| `mech_seal_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-A mech seal temp |
| `seal_leakage_rate` | flow | lpm | 0–8 | / · 4/6 | CEP-A seal leakage rate |
| `lube_oil_filter_dp` | pressure | bar | 0.1–1.5 | / · 1.6/2 | CEP-A lube oil filter dp |
| `lube_oil_supply_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-A lube oil supply temp |
| `lube_oil_return_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-A lube oil return temp |
| `lube_oil_flow` | flow | lpm | 20–120 | / · / | CEP-A lube oil flow |
| `lube_oil_water_content` | chemistry | ppm | 50–400 | / · / | CEP-A lube oil water content |
| `lube_oil_particle_count` | chemistry | count/ml | 100–2000 | / · / | CEP-A lube oil particle count |
| `aux_oil_pump_pressure` | pressure | bar | 1.5–3.5 | / · / | CEP-A aux oil pump pressure |
| `motor_current_phase_1` | electrical | A | 0–600 | / · / | CEP-A motor current phase 1 |
| `motor_current_phase_2` | electrical | A | 0–600 | / · / | CEP-A motor current phase 2 |
| `motor_current_phase_3` | electrical | A | 0–600 | / · / | CEP-A motor current phase 3 |
| `motor_voltage_phase_1` | electrical | V | 6200–6800 | / · / | CEP-A motor voltage phase 1 |
| `motor_voltage_phase_2` | electrical | V | 6200–6800 | / · / | CEP-A motor voltage phase 2 |
| `motor_voltage_phase_3` | electrical | V | 6200–6800 | / · / | CEP-A motor voltage phase 3 |
| `motor_power_factor` | electrical |  | 0.8–0.95 | / · / | CEP-A motor power factor |
| `motor_frequency` | electrical | Hz | 49.8–50.2 | / · / | CEP-A motor frequency |
| `motor_bearing_temp_de` | temperature | degC | 45–85 | / · 90/100 | CEP-A motor bearing temp de |
| `motor_bearing_temp_nde` | temperature | degC | 45–85 | / · 90/100 | CEP-A motor bearing temp nde |
| `motor_vibration_de` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A motor vibration de |
| `motor_vibration_nde` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-A motor vibration nde |
| `motor_cooling_air_inlet_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-A motor cooling air inlet temp |
| `motor_cooling_air_outlet_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-A motor cooling air outlet temp |
| `motor_insulation_resistance` | electrical | Mohm | 50–500 | / · / | CEP-A motor insulation resistance |
| `motor_reactive_power` | electrical | kVAr | 0–400 | / · / | CEP-A motor reactive power |
| `pump_head` | derived |  | 0–100 | / · / | CEP-A pump head |
| `hydraulic_power` | derived |  | 0–100 | / · / | CEP-A hydraulic power |
| `pump_efficiency` | derived |  | 0–100 | / · / | CEP-A pump efficiency |
| `specific_energy` | derived |  | 0–100 | / · / | CEP-A specific energy |
| `flow_deviation_from_bep` | derived |  | 0–100 | / · / | CEP-A flow deviation from bep |
| `vibration_severity_zone` | derived |  | 0–100 | / · / | CEP-A vibration severity zone |
| `bearing_temp_margin` | derived |  | 0–100 | / · / | CEP-A bearing temp margin |
| `health_index` | derived |  | 0–100 | / · / | CEP-A health index |
| `power_consumed` | derived |  | 0–100 | / · / | CEP-A power consumed |
| `running_hours` | derived | h | 0–1e+06 | / · / | CEP-A running hours |
| `start_count` | derived | count | 0–100000 | / · / | CEP-A start count |
| `vacuum_margin` | derived |  | 0–100 | / · / | CEP-A vacuum margin |
| `subcooling` | derived |  | 0–100 | / · / | CEP-A subcooling |
| `pump_running` | status | bool | 0–1 | / · / | CEP-A pump running |
| `standby_mode` | status | bool | 0–1 | / · / | CEP-A standby mode |
| `auto_mode` | status | bool | 0–1 | / · / | CEP-A auto mode |
| `trip_status` | status | bool | 0–1 | / · / | CEP-A trip status |
| `alarm_active` | status | bool | 0–1 | / · / | CEP-A alarm active |
| `recirc_valve_open` | status | bool | 0–1 | / · / | CEP-A recirc valve open |
| `aux_oil_pump_running` | status | bool | 0–1 | / · / | CEP-A aux oil pump running |

## `cepb` — Condensate Extraction Pump B

- KKS: `LCB20 AP001` · class: centrifugal_pump / condensate_extraction_pump · criticality: medium
- 108 tags · rated 900 kW, 1480 rpm

| tag_name | family | unit | normal | alarms (lo/lolo·hi/hihi) | description |
|---|---|---|---|---|---|
| `bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | CEP-B bearing #1 metal temperature |
| `bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | CEP-B bearing #2 metal temperature |
| `bearing_temp_3` | temperature | degC | 45–85 | / · 90/100 | CEP-B bearing #3 metal temperature |
| `bearing_temp_4` | temperature | degC | 45–85 | / · 90/100 | CEP-B bearing #4 metal temperature |
| `vibration_x_1` | vibration | um | 5–60 | / · 90/150 | CEP-B bearing #1 shaft vibration X |
| `vibration_y_1` | vibration | um | 5–60 | / · 90/150 | CEP-B bearing #1 shaft vibration Y |
| `vibration_x_2` | vibration | um | 5–60 | / · 90/150 | CEP-B bearing #2 shaft vibration X |
| `vibration_y_2` | vibration | um | 5–60 | / · 90/150 | CEP-B bearing #2 shaft vibration Y |
| `vibration_overall` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B overall casing vibration velocity |
| `vibration_axial` | vibration | mm | -1–1 | / · / | CEP-B overall axial vibration velocity |
| `shaft_speed` | speed | rpm | 0–6000 | / · / | CEP-B shaft rotational speed |
| `lube_oil_pressure` | pressure | bar | 1.5–3 | 1.2/0.9 · / | CEP-B lube oil header pressure |
| `lube_oil_temp` | temperature | degC | 35–55 | / · 60/65 | CEP-B lube oil supply temperature |
| `lube_oil_level` | level | % | 40–90 | / · / | CEP-B lube oil tank level |
| `ambient_temp` | temperature | degC | 15–35 | / · / | CEP-B ambient air temperature |
| `suction_pressure` | pressure | bar | 3–12 | / · / | CEP-B suction pressure |
| `discharge_pressure` | pressure | bar | 60–185 | / · / | CEP-B discharge pressure |
| `differential_pressure` | pressure | bar | 0.1–1.5 | / · 1.6/2 | CEP-B differential pressure |
| `flow_rate` | flow | t/h | 0–320 | / · / | CEP-B feedwater flow rate |
| `motor_current` | electrical | A | 0–600 | / · / | CEP-B motor current |
| `motor_power` | electrical | kW | 0–9000 | / · / | CEP-B motor active power |
| `motor_voltage` | electrical | V | 6200–6800 | / · / | CEP-B motor terminal voltage |
| `winding_temp_1` | temperature | degC | 55–110 | / · 120/130 | CEP-B motor winding U temperature |
| `winding_temp_2` | temperature | degC | 55–110 | / · 120/130 | CEP-B motor winding V temperature |
| `winding_temp_3` | temperature | degC | 55–110 | / · 120/130 | CEP-B motor winding W temperature |
| `upper_guide_bearing_temp` | temperature | degC | 45–85 | / · 90/100 | CEP-B upper guide bearing temp |
| `lower_guide_bearing_temp` | temperature | degC | 45–85 | / · 90/100 | CEP-B lower guide bearing temp |
| `thrust_bearing_temp` | temperature | degC | 45–85 | / · 90/100 | CEP-B thrust bearing temp |
| `column_vibration_1` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B column vibration 1 |
| `column_vibration_2` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B column vibration 2 |
| `column_vibration_3` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B column vibration 3 |
| `motor_stool_vibration` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B motor stool vibration |
| `shaft_deflection` | vibration | um | 5–60 | / · 90/150 | CEP-B shaft deflection |
| `bowl_assembly_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-B bowl assembly temp |
| `line_shaft_vibration` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B line shaft vibration |
| `stage_pressure_1` | pressure | bar | 1–45 | / · / | CEP-B stage pressure 1 |
| `stage_pressure_2` | pressure | bar | 1–45 | / · / | CEP-B stage pressure 2 |
| `stage_pressure_3` | pressure | bar | 1–45 | / · / | CEP-B stage pressure 3 |
| `stage_pressure_4` | pressure | bar | 1–45 | / · / | CEP-B stage pressure 4 |
| `hotwell_level` | level | mm | 300–900 | / · / | CEP-B hotwell level |
| `condenser_vacuum` | pressure | mbara | 40–120 | / · / | CEP-B condenser vacuum |
| `condenser_pressure` | pressure | bar | 0.04–0.12 | / · / | CEP-B condenser pressure |
| `condensate_temp` | temperature | degC | 30–55 | / · 58/61 | CEP-B condensate temp |
| `air_ingress_rate` | chemistry | index | 0–1 | / · / | CEP-B air ingress rate |
| `cw_inlet_temp` | temperature | degC | 20–35 | / · 38/41 | CEP-B cw inlet temp |
| `cw_outlet_temp` | temperature | degC | 28–45 | / · 48/51 | CEP-B cw outlet temp |
| `condenser_ttd` | temperature | degC | 2–8 | / · 11/14 | CEP-B condenser ttd |
| `recirc_flow` | flow | t/h | 0–300 | / · / | CEP-B recirc flow |
| `min_flow_valve_position` | level | % | 0–100 | / · / | CEP-B min flow valve position |
| `discharge_valve_position` | level | % | 0–100 | / · / | CEP-B discharge valve position |
| `npsh_available` | pressure | m | 3–12 | 2/1 · / | CEP-B npsh available |
| `npsh_margin` | pressure | m | 1.5–8 | 0.8/0.3 · / | CEP-B npsh margin |
| `cavitation_index` | derived |  | 0–100 | / · / | CEP-B cavitation index |
| `suction_pressure_abs` | pressure | mbara | 40–120 | / · / | CEP-B suction pressure abs |
| `discharge_temp` | temperature | degC | 30–55 | / · 58/61 | CEP-B discharge temp |
| `deaerator_level` | level | % | 20–80 | / · / | CEP-B deaerator level |
| `condensate_conductivity` | chemistry | uS/cm | 0.05–0.35 | / · / | CEP-B condensate conductivity |
| `condensate_ph` | chemistry | pH | 8.8–9.4 | / · / | CEP-B condensate ph |
| `dissolved_oxygen` | chemistry | ppb | 2–20 | / · / | CEP-B dissolved oxygen |
| `sodium_content` | chemistry | ppb | 1–10 | / · / | CEP-B sodium content |
| `condensate_iron` | chemistry | ppb | 1–15 | / · / | CEP-B condensate iron |
| `gland_seal_water_flow` | flow | lpm | 0–8 | / · / | CEP-B gland seal water flow |
| `gland_seal_water_pressure` | pressure | bar | 1–4 | / · / | CEP-B gland seal water pressure |
| `mech_seal_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-B mech seal temp |
| `seal_leakage_rate` | flow | lpm | 0–8 | / · 4/6 | CEP-B seal leakage rate |
| `lube_oil_filter_dp` | pressure | bar | 0.1–1.5 | / · 1.6/2 | CEP-B lube oil filter dp |
| `lube_oil_supply_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-B lube oil supply temp |
| `lube_oil_return_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-B lube oil return temp |
| `lube_oil_flow` | flow | lpm | 20–120 | / · / | CEP-B lube oil flow |
| `lube_oil_water_content` | chemistry | ppm | 50–400 | / · / | CEP-B lube oil water content |
| `lube_oil_particle_count` | chemistry | count/ml | 100–2000 | / · / | CEP-B lube oil particle count |
| `aux_oil_pump_pressure` | pressure | bar | 1.5–3.5 | / · / | CEP-B aux oil pump pressure |
| `motor_current_phase_1` | electrical | A | 0–600 | / · / | CEP-B motor current phase 1 |
| `motor_current_phase_2` | electrical | A | 0–600 | / · / | CEP-B motor current phase 2 |
| `motor_current_phase_3` | electrical | A | 0–600 | / · / | CEP-B motor current phase 3 |
| `motor_voltage_phase_1` | electrical | V | 6200–6800 | / · / | CEP-B motor voltage phase 1 |
| `motor_voltage_phase_2` | electrical | V | 6200–6800 | / · / | CEP-B motor voltage phase 2 |
| `motor_voltage_phase_3` | electrical | V | 6200–6800 | / · / | CEP-B motor voltage phase 3 |
| `motor_power_factor` | electrical |  | 0.8–0.95 | / · / | CEP-B motor power factor |
| `motor_frequency` | electrical | Hz | 49.8–50.2 | / · / | CEP-B motor frequency |
| `motor_bearing_temp_de` | temperature | degC | 45–85 | / · 90/100 | CEP-B motor bearing temp de |
| `motor_bearing_temp_nde` | temperature | degC | 45–85 | / · 90/100 | CEP-B motor bearing temp nde |
| `motor_vibration_de` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B motor vibration de |
| `motor_vibration_nde` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | CEP-B motor vibration nde |
| `motor_cooling_air_inlet_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-B motor cooling air inlet temp |
| `motor_cooling_air_outlet_temp` | temperature | degC | 30–80 | / · 85/90 | CEP-B motor cooling air outlet temp |
| `motor_insulation_resistance` | electrical | Mohm | 50–500 | / · / | CEP-B motor insulation resistance |
| `motor_reactive_power` | electrical | kVAr | 0–400 | / · / | CEP-B motor reactive power |
| `pump_head` | derived |  | 0–100 | / · / | CEP-B pump head |
| `hydraulic_power` | derived |  | 0–100 | / · / | CEP-B hydraulic power |
| `pump_efficiency` | derived |  | 0–100 | / · / | CEP-B pump efficiency |
| `specific_energy` | derived |  | 0–100 | / · / | CEP-B specific energy |
| `flow_deviation_from_bep` | derived |  | 0–100 | / · / | CEP-B flow deviation from bep |
| `vibration_severity_zone` | derived |  | 0–100 | / · / | CEP-B vibration severity zone |
| `bearing_temp_margin` | derived |  | 0–100 | / · / | CEP-B bearing temp margin |
| `health_index` | derived |  | 0–100 | / · / | CEP-B health index |
| `power_consumed` | derived |  | 0–100 | / · / | CEP-B power consumed |
| `running_hours` | derived | h | 0–1e+06 | / · / | CEP-B running hours |
| `start_count` | derived | count | 0–100000 | / · / | CEP-B start count |
| `vacuum_margin` | derived |  | 0–100 | / · / | CEP-B vacuum margin |
| `subcooling` | derived |  | 0–100 | / · / | CEP-B subcooling |
| `pump_running` | status | bool | 0–1 | / · / | CEP-B pump running |
| `standby_mode` | status | bool | 0–1 | / · / | CEP-B standby mode |
| `auto_mode` | status | bool | 0–1 | / · / | CEP-B auto mode |
| `trip_status` | status | bool | 0–1 | / · / | CEP-B trip status |
| `alarm_active` | status | bool | 0–1 | / · / | CEP-B alarm active |
| `recirc_valve_open` | status | bool | 0–1 | / · / | CEP-B recirc valve open |
| `aux_oil_pump_running` | status | bool | 0–1 | / · / | CEP-B aux oil pump running |

## `turbine` — Steam Turbine

- KKS: `MAA10` · class: steam_turbine / reheat_condensing_turbine · criticality: critical
- 160 tags · rated 250000 kW, 3000 rpm

| tag_name | family | unit | normal | alarms (lo/lolo·hi/hihi) | description |
|---|---|---|---|---|---|
| `bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing #1 metal temperature |
| `bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing #2 metal temperature |
| `bearing_temp_3` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing #3 metal temperature |
| `bearing_temp_4` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing #4 metal temperature |
| `vibration_x_1` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing #1 shaft vibration X |
| `vibration_y_1` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing #1 shaft vibration Y |
| `vibration_x_2` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing #2 shaft vibration X |
| `vibration_y_2` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing #2 shaft vibration Y |
| `vibration_overall` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | Steam Turbine overall casing vibration velocity |
| `vibration_axial` | vibration | mm | -1–1 | / · / | Steam Turbine overall axial vibration velocity |
| `shaft_speed` | speed | rpm | 0–6000 | / · / | Steam Turbine shaft rotational speed |
| `lube_oil_pressure` | pressure | bar | 1.5–3 | 1.2/0.9 · / | Steam Turbine lube oil header pressure |
| `lube_oil_temp` | temperature | degC | 35–55 | / · 60/65 | Steam Turbine lube oil supply temperature |
| `lube_oil_level` | level | % | 40–90 | / · / | Steam Turbine lube oil tank level |
| `ambient_temp` | temperature | degC | 15–35 | / · / | Steam Turbine ambient air temperature |
| `bearing_temp_5` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing temp 5 |
| `bearing_temp_6` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing temp 6 |
| `bearing_temp_7` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing temp 7 |
| `bearing_temp_8` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing temp 8 |
| `bearing_temp_9` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing temp 9 |
| `bearing_temp_10` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine bearing temp 10 |
| `thrust_bearing_temp_active` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine thrust bearing temp active |
| `thrust_bearing_temp_inactive` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine thrust bearing temp inactive |
| `bearing_vibration_x_3` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration x 3 |
| `bearing_vibration_x_4` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration x 4 |
| `bearing_vibration_x_5` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration x 5 |
| `bearing_vibration_x_6` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration x 6 |
| `bearing_vibration_x_7` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration x 7 |
| `bearing_vibration_x_8` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration x 8 |
| `bearing_vibration_y_3` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration y 3 |
| `bearing_vibration_y_4` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration y 4 |
| `bearing_vibration_y_5` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration y 5 |
| `bearing_vibration_y_6` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration y 6 |
| `bearing_vibration_y_7` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration y 7 |
| `bearing_vibration_y_8` | vibration | um | 5–60 | / · 90/150 | Steam Turbine bearing vibration y 8 |
| `main_steam_pressure` | pressure | bar | 20–170 | / · / | Steam Turbine main steam pressure |
| `main_steam_temp` | temperature | degC | 180–540 | / · 545/560 | Steam Turbine main steam temp |
| `main_steam_flow` | flow | t/h | 0–900 | / · / | Steam Turbine main steam flow |
| `hp_inlet_pressure` | pressure | bar | 20–170 | / · / | Steam Turbine hp inlet pressure |
| `hp_inlet_temp` | temperature | degC | 180–540 | / · 545/560 | Steam Turbine hp inlet temp |
| `hp_exhaust_pressure` | pressure | bar | 20–45 | / · / | Steam Turbine hp exhaust pressure |
| `hp_exhaust_temp` | temperature | degC | 280–360 | / · 368/376 | Steam Turbine hp exhaust temp |
| `reheat_inlet_pressure` | pressure | bar | 20–45 | / · / | Steam Turbine reheat inlet pressure |
| `reheat_inlet_temp` | temperature | degC | 180–540 | / · 545/560 | Steam Turbine reheat inlet temp |
| `ip_inlet_pressure` | pressure | bar | 18–42 | / · / | Steam Turbine ip inlet pressure |
| `ip_inlet_temp` | temperature | degC | 30–80 | / · 85/90 | Steam Turbine ip inlet temp |
| `ip_exhaust_pressure` | pressure | bar | 3–12 | / · / | Steam Turbine ip exhaust pressure |
| `ip_exhaust_temp` | temperature | degC | 180–320 | / · 334/348 | Steam Turbine ip exhaust temp |
| `lp_inlet_pressure` | pressure | bar | 3–12 | / · / | Steam Turbine lp inlet pressure |
| `lp_inlet_temp` | temperature | degC | 180–320 | / · 334/348 | Steam Turbine lp inlet temp |
| `lp_exhaust_pressure` | pressure | mbara | 40–120 | / · / | Steam Turbine lp exhaust pressure |
| `lp_exhaust_temp` | temperature | degC | 30–60 | / · 63/66 | Steam Turbine lp exhaust temp |
| `throttle_flow` | flow | t/h | 0–900 | / · / | Steam Turbine throttle flow |
| `extraction_pressure_1` | pressure | bar | 1–40 | / · / | Steam Turbine extraction pressure 1 |
| `extraction_pressure_2` | pressure | bar | 1–40 | / · / | Steam Turbine extraction pressure 2 |
| `extraction_pressure_3` | pressure | bar | 1–40 | / · / | Steam Turbine extraction pressure 3 |
| `extraction_pressure_4` | pressure | bar | 1–40 | / · / | Steam Turbine extraction pressure 4 |
| `extraction_pressure_5` | pressure | bar | 1–40 | / · / | Steam Turbine extraction pressure 5 |
| `extraction_temp_1` | temperature | degC | 120–400 | / · 428/456 | Steam Turbine extraction temp 1 |
| `extraction_temp_2` | temperature | degC | 120–400 | / · 428/456 | Steam Turbine extraction temp 2 |
| `extraction_temp_3` | temperature | degC | 120–400 | / · 428/456 | Steam Turbine extraction temp 3 |
| `extraction_temp_4` | temperature | degC | 120–400 | / · 428/456 | Steam Turbine extraction temp 4 |
| `extraction_temp_5` | temperature | degC | 120–400 | / · 428/456 | Steam Turbine extraction temp 5 |
| `gov_valve_position_1` | level | % | 0–100 | / · / | Steam Turbine gov valve position 1 |
| `gov_valve_position_2` | level | % | 0–100 | / · / | Steam Turbine gov valve position 2 |
| `gov_valve_position_3` | level | % | 0–100 | / · / | Steam Turbine gov valve position 3 |
| `gov_valve_position_4` | level | % | 0–100 | / · / | Steam Turbine gov valve position 4 |
| `stop_valve_position_1` | level | % | 0–100 | / · / | Steam Turbine stop valve position 1 |
| `stop_valve_position_2` | level | % | 0–100 | / · / | Steam Turbine stop valve position 2 |
| `reheat_stop_valve_position` | level | % | 0–100 | / · / | Steam Turbine reheat stop valve position |
| `intercept_valve_position_1` | level | % | 0–100 | / · / | Steam Turbine intercept valve position 1 |
| `intercept_valve_position_2` | level | % | 0–100 | / · / | Steam Turbine intercept valve position 2 |
| `speed_setpoint` | speed | rpm | 0–3300 | / · / | Steam Turbine speed setpoint |
| `load_setpoint` | electrical | MW | 0–250 | / · / | Steam Turbine load setpoint |
| `governor_oil_pressure` | pressure | bar | 8–16 | / · / | Steam Turbine governor oil pressure |
| `eccentricity` | vibration | um | 10–50 | / · 80/120 | Steam Turbine eccentricity |
| `axial_shift` | vibration | mm | -1–1 | / · / | Steam Turbine axial shift |
| `differential_expansion_hp` | vibration | mm | -1–1 | / · / | Steam Turbine differential expansion hp |
| `differential_expansion_ip` | vibration | mm | -1–1 | / · / | Steam Turbine differential expansion ip |
| `differential_expansion_lp` | vibration | mm | -1–1 | / · / | Steam Turbine differential expansion lp |
| `casing_expansion_1` | vibration | mm | -1–1 | / · / | Steam Turbine casing expansion 1 |
| `casing_expansion_2` | vibration | mm | -1–1 | / · / | Steam Turbine casing expansion 2 |
| `rotor_position` | vibration | mm | -1–1 | / · / | Steam Turbine rotor position |
| `phase_reference` | speed | deg | 0–360 | / · / | Steam Turbine phase reference |
| `control_oil_pressure` | pressure | bar | 8–16 | / · / | Steam Turbine control oil pressure |
| `jacking_oil_pressure_1` | pressure | bar | 100–160 | / · / | Steam Turbine jacking oil pressure 1 |
| `jacking_oil_pressure_2` | pressure | bar | 100–160 | / · / | Steam Turbine jacking oil pressure 2 |
| `jacking_oil_pressure_3` | pressure | bar | 100–160 | / · / | Steam Turbine jacking oil pressure 3 |
| `jacking_oil_pressure_4` | pressure | bar | 100–160 | / · / | Steam Turbine jacking oil pressure 4 |
| `lube_oil_tank_level` | level | % | 40–90 | / · / | Steam Turbine lube oil tank level |
| `lube_oil_tank_temp` | temperature | degC | 35–55 | / · 58/61 | Steam Turbine lube oil tank temp |
| `lube_oil_filter_dp` | pressure | bar | 0.1–1.5 | / · 1.6/2 | Steam Turbine lube oil filter dp |
| `lube_oil_cooler_outlet_temp` | temperature | degC | 35–50 | / · 53/56 | Steam Turbine lube oil cooler outlet temp |
| `aux_oil_pump_pressure` | pressure | bar | 1.5–3.5 | / · / | Steam Turbine aux oil pump pressure |
| `emergency_oil_pump_running` | status | bool | 0–1 | / · / | Steam Turbine emergency oil pump running |
| `condenser_vacuum` | pressure | mbara | 45–90 | / · 100/115 | Steam Turbine condenser vacuum |
| `condenser_pressure` | pressure | bar | 0.04–0.12 | / · / | Steam Turbine condenser pressure |
| `hotwell_level` | level | mm | 300–900 | / · / | Steam Turbine hotwell level |
| `cw_inlet_temp` | temperature | degC | 20–35 | / · 38/41 | Steam Turbine cw inlet temp |
| `cw_outlet_temp` | temperature | degC | 28–45 | / · 48/51 | Steam Turbine cw outlet temp |
| `condenser_ttd` | temperature | degC | 2–8 | / · 11/14 | Steam Turbine condenser ttd |
| `air_ejector_flow` | flow | kg/h | 5–60 | / · / | Steam Turbine air ejector flow |
| `cooling_water_flow` | flow | t/h | 0–40000 | / · / | Steam Turbine cooling water flow |
| `gross_power` | electrical | MW | 0–250 | / · / | Steam Turbine gross power |
| `reactive_power` | electrical | MVAr | -20–90 | / · / | Steam Turbine reactive power |
| `stator_current_1` | electrical | A | 0–9000 | / · / | Steam Turbine stator current 1 |
| `stator_current_2` | electrical | A | 0–9000 | / · / | Steam Turbine stator current 2 |
| `stator_current_3` | electrical | A | 0–9000 | / · / | Steam Turbine stator current 3 |
| `stator_voltage_1` | electrical | V | 6200–6800 | / · / | Steam Turbine stator voltage 1 |
| `stator_voltage_2` | electrical | V | 6200–6800 | / · / | Steam Turbine stator voltage 2 |
| `stator_voltage_3` | electrical | V | 6200–6800 | / · / | Steam Turbine stator voltage 3 |
| `stator_winding_temp_1` | temperature | degC | 55–110 | / · 120/130 | Steam Turbine stator winding temp 1 |
| `stator_winding_temp_2` | temperature | degC | 55–110 | / · 120/130 | Steam Turbine stator winding temp 2 |
| `stator_winding_temp_3` | temperature | degC | 55–110 | / · 120/130 | Steam Turbine stator winding temp 3 |
| `stator_winding_temp_4` | temperature | degC | 55–110 | / · 120/130 | Steam Turbine stator winding temp 4 |
| `stator_winding_temp_5` | temperature | degC | 55–110 | / · 120/130 | Steam Turbine stator winding temp 5 |
| `stator_winding_temp_6` | temperature | degC | 55–110 | / · 120/130 | Steam Turbine stator winding temp 6 |
| `stator_core_temp_1` | temperature | degC | 55–105 | / · 110/115 | Steam Turbine stator core temp 1 |
| `stator_core_temp_2` | temperature | degC | 55–105 | / · 110/115 | Steam Turbine stator core temp 2 |
| `rotor_current` | electrical | A | 0–2500 | / · / | Steam Turbine rotor current |
| `rotor_voltage` | electrical | V | 6200–6800 | / · / | Steam Turbine rotor voltage |
| `h2_pressure` | pressure | bar | 2–4 | / · / | Steam Turbine h2 pressure |
| `h2_purity` | chemistry | % | 95–99.5 | / · / | Steam Turbine h2 purity |
| `h2_temp` | temperature | degC | 30–50 | / · 53/56 | Steam Turbine h2 temp |
| `seal_oil_pressure` | pressure | bar | 3–6 | / · / | Steam Turbine seal oil pressure |
| `seal_oil_temp` | temperature | degC | 30–50 | / · 53/56 | Steam Turbine seal oil temp |
| `exciter_temp` | temperature | degC | 40–90 | / · 95/100 | Steam Turbine exciter temp |
| `generator_bearing_temp_1` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine generator bearing temp 1 |
| `generator_bearing_temp_2` | temperature | degC | 45–85 | / · 90/100 | Steam Turbine generator bearing temp 2 |
| `frequency` | electrical | Hz | 49.8–50.2 | / · / | Steam Turbine frequency |
| `power_factor` | electrical |  | 0.8–0.95 | / · / | Steam Turbine power factor |
| `heat_rate` | derived | kJ/kWh | 7500–11000 | / · / | Steam Turbine heat rate |
| `hp_efficiency` | derived | % | 70–92 | / · / | Steam Turbine hp efficiency |
| `ip_efficiency` | derived | % | 70–92 | / · / | Steam Turbine ip efficiency |
| `lp_efficiency` | derived | % | 70–92 | / · / | Steam Turbine lp efficiency |
| `steam_rate` | derived | kg/kWh | 3–6 | / · / | Steam Turbine steam rate |
| `backpressure` | pressure | kPa | 4–12 | / · / | Steam Turbine backpressure |
| `vacuum_loss` | derived | mbar | 0–30 | / · / | Steam Turbine vacuum loss |
| `cycle_efficiency` | derived | % | 30–45 | / · / | Steam Turbine cycle efficiency |
| `gland_steam_pressure` | pressure | bar | 0.1–1.5 | / · / | Steam Turbine gland steam pressure |
| `gland_steam_temp` | temperature | degC | 120–280 | / · 545/560 | Steam Turbine gland steam temp |
| `lp_hood_temp_1` | temperature | degC | 30–80 | / · 90/110 | Steam Turbine lp hood temp 1 |
| `lp_hood_temp_2` | temperature | degC | 30–80 | / · 90/110 | Steam Turbine lp hood temp 2 |
| `lp_spray_flow` | flow | t/h | 0–20 | / · / | Steam Turbine lp spray flow |
| `crossover_pressure` | pressure | bar | 3–14 | / · / | Steam Turbine crossover pressure |
| `crossover_temp` | temperature | degC | 180–340 | / · 356/372 | Steam Turbine crossover temp |
| `stator_coolant_flow` | flow | l/min | 200–600 | / · / | Steam Turbine stator coolant flow |
| `stator_coolant_temp` | temperature | degC | 30–60 | / · 63/66 | Steam Turbine stator coolant temp |
| `h2_cooler_outlet_temp` | temperature | degC | 25–45 | / · 48/51 | Steam Turbine h2 cooler outlet temp |
| `generator_vibration_de` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | Steam Turbine generator vibration de |
| `generator_vibration_nde` | vibration | mm/s | 0.5–4.5 | / · 4.5/7.1 | Steam Turbine generator vibration nde |
| `exhaust_hood_temp` | temperature | degC | 30–80 | / · 85/90 | Steam Turbine exhaust hood temp |
| `condensate_makeup_flow` | flow | t/h | 0–30 | / · / | Steam Turbine condensate makeup flow |
| `turbine_running` | status | bool | 0–1 | / · / | Steam Turbine turbine running |
| `on_load` | status | bool | 0–1 | / · / | Steam Turbine on load |
| `auto_mode` | status | bool | 0–1 | / · / | Steam Turbine auto mode |
| `trip_status` | status | bool | 0–1 | / · / | Steam Turbine trip status |
| `alarm_active` | status | bool | 0–1 | / · / | Steam Turbine alarm active |
| `barring_gear_engaged` | status | bool | 0–1 | / · / | Steam Turbine barring gear engaged |
| `turning_gear_running` | status | bool | 0–1 | / · / | Steam Turbine turning gear running |

## Spare-part items

| item_code | name | category | unit_cost (INR) | uom |
|---|---|---|---:|---|
| `BRG-001` | Turbine journal bearing, tilting-pad | bearing | 705,000 | each |
| `BRG-002` | Turbine thrust bearing assembly | bearing | 620,000 | each |
| `BRG-003` | Generator journal bearing | bearing | 410,000 | each |
| `BRG-004` | BFP tilting-pad thrust bearing | bearing | 285,000 | each |
| `BRG-005` | BFP radial journal bearing | bearing | 190,000 | each |
| `BRG-006` | CEP guide bearing, water-lubricated | bearing | 84,000 | each |
| `BRG-007` | CEP thrust bearing | bearing | 118,000 | each |
| `BRG-008` | Motor DE bearing (roller) | bearing | 46,000 | each |
| `BRG-009` | Motor NDE bearing (roller) | bearing | 39,000 | each |
| `BRG-010` | Booster pump bearing set | bearing | 52,000 | set |
| `BRG-011` | Coupling-end journal bearing | bearing | 96,000 | each |
| `BRG-012` | Pedestal bearing white-metal reline | bearing | 135,000 | each |
| `SEL-001` | BFP mechanical seal cartridge set | seal | 118,000 | set |
| `SEL-002` | CEP mechanical seal cartridge | seal | 76,000 | set |
| `SEL-003` | Gland packing set, graphite | seal | 9,500 | set |
| `SEL-004` | Balance drum seal ring | seal | 42,000 | each |
| `SEL-005` | Throttle bush / breakdown seal | seal | 28,000 | each |
| `SEL-006` | Generator H2 seal ring set | seal | 88,000 | set |
| `SEL-007` | Lip seal, oil-side | seal | 3,200 | each |
| `SEL-008` | Labyrinth seal segment | seal | 15,500 | each |
| `SEL-009` | Seal flush ring assembly | seal | 12,500 | each |
| `SEL-010` | Steam gland seal ring | seal | 21,000 | each |
| `FLT-001` | Lube oil filter element, 10 micron | filter | 6,800 | each |
| `FLT-002` | Lube oil filter element, 25 micron | filter | 5,200 | each |
| `FLT-003` | Control oil filter element | filter | 8,900 | each |
| `FLT-004` | Suction strainer basket | filter | 24,000 | each |
| `FLT-005` | Duplex filter changeover kit | filter | 15,500 | kit |
| `FLT-006` | Motor cooling air filter | filter | 3,200 | each |
| `FLT-007` | Seal water fine filter | filter | 4,400 | each |
| `FLT-008` | Air ejector inlet screen | filter | 1,900 | each |
| `GSK-001` | Casing joint gasket, spiral wound | gasket | 14,500 | each |
| `GSK-002` | Cover flange gasket set | gasket | 8,600 | set |
| `GSK-003` | Manway gasket | gasket | 3,400 | each |
| `GSK-004` | Heat-exchanger gasket set | gasket | 6,200 | set |
| `GSK-005` | Valve bonnet gasket | gasket | 1,800 | each |
| `GSK-006` | Condenser waterbox gasket | gasket | 11,200 | each |
| `GSK-007` | Turbine casing spill strip gasket | gasket | 5,400 | each |
| `GSK-008` | Instrument tapping gasket | gasket | 520 | each |
| `ORG-001` | O-ring, Viton, 90 mm | o_ring | 720 | each |
| `ORG-002` | O-ring, Viton, 140 mm | o_ring | 1,150 | each |
| `ORG-003` | O-ring, EPDM, 60 mm | o_ring | 680 | each |
| `ORG-004` | O-ring kit, assorted | o_ring | 2,800 | kit |
| `ORG-005` | O-ring, high-temp silicone | o_ring | 1,450 | each |
| `ORG-006` | Back-up ring set | o_ring | 950 | set |
| `LUB-001` | Turbine oil ISO VG 32 (208 L drum) | lubricant | 58,000 | drum |
| `LUB-002` | Turbine oil ISO VG 46 (208 L drum) | lubricant | 61,000 | drum |
| `LUB-003` | EP gear oil (20 L pail) | lubricant | 9,800 | pail |
| `LUB-004` | High-temp bearing grease (18 kg) | lubricant | 12,500 | keg |
| `LUB-005` | Coupling grease (5 kg) | lubricant | 4,200 | tub |
| `LUB-006` | Oil-conditioning filter cartridge | lubricant | 7,600 | each |
| `CPL-001` | Hydraulic coupling scoop tube | coupling | 165,000 | each |
| `CPL-002` | Gear coupling element set | coupling | 96,000 | set |
| `CPL-003` | Flexible disc coupling pack | coupling | 58,000 | set |
| `CPL-004` | Coupling hub, shrink-fit | coupling | 78,000 | each |
| `CPL-005` | Coupling guard assembly | coupling | 22,000 | each |
| `IMP-001` | BFP first-stage impeller | impeller | 480,000 | each |
| `IMP-002` | BFP intermediate-stage impeller | impeller | 320,000 | each |
| `IMP-003` | CEP bowl impeller | impeller | 175,000 | each |
| `IMP-004` | Booster pump impeller | impeller | 92,000 | each |
| `IMP-005` | Impeller wear-ring machining kit | impeller | 84,000 | kit |
| `WRG-001` | Impeller wear ring, stage | wear_ring | 38,000 | each |
| `WRG-002` | Casing wear ring, stage | wear_ring | 42,000 | each |
| `WRG-003` | Balance drum wear ring | wear_ring | 88,000 | each |
| `WRG-004` | CEP bowl wear ring | wear_ring | 26,000 | each |
| `WRG-005` | Throttle bush wear ring | wear_ring | 14,500 | each |
| `SLV-001` | Shaft sleeve, seal area | sleeve | 34,000 | each |
| `SLV-002` | Inter-stage shaft sleeve | sleeve | 28,000 | each |
| `SLV-003` | Line-shaft sleeve (CEP) | sleeve | 18,500 | each |
| `SLV-004` | Bearing sleeve / journal sleeve | sleeve | 46,000 | each |
| `SLV-005` | Distance sleeve set | sleeve | 9,800 | set |
| `VLV-001` | Minimum-flow recirculation valve | valve | 285,000 | each |
| `VLV-002` | Non-return / check valve | valve | 96,000 | each |
| `VLV-003` | Discharge isolation valve | valve | 128,000 | each |
| `VLV-004` | Governor control valve overhaul kit | valve | 210,000 | kit |
| `VLV-005` | Relief valve, spring-loaded | valve | 42,000 | each |
| `VLV-006` | Solenoid pilot valve | valve | 18,500 | each |
| `INS-001` | Bearing RTD PT100 duplex | instrument | 6,800 | each |
| `INS-002` | Vibration proximity probe + driver | instrument | 118,000 | set |
| `INS-003` | Casing vibration accelerometer | instrument | 42,000 | each |
| `INS-004` | Pressure transmitter | instrument | 38,000 | each |
| `INS-005` | Temperature thermocouple type-K | instrument | 4,200 | each |
| `INS-006` | Flow transmitter (DP type) | instrument | 56,000 | each |
| `INS-007` | Speed / key-phasor probe | instrument | 62,000 | each |
| `INS-008` | Level transmitter | instrument | 34,000 | each |
| `FST-001` | Casing stud & nut kit, high-tensile | fastener | 7,800 | kit |
| `FST-002` | Coupling bolt set, fitted | fastener | 5,400 | set |
| `FST-003` | Foundation / hold-down bolt set | fastener | 3,200 | set |
| `FST-004` | Bearing cap bolt kit | fastener | 1,600 | kit |
| `ELC-001` | Motor winding insulation reconditioning kit | electrical | 148,000 | kit |
| `ELC-002` | Bearing insulation kit (shaft grounding) | electrical | 22,000 | kit |
| `ELC-003` | Stator RTD embedded sensor | electrical | 5,600 | each |
| `ELC-004` | Space heater element | electrical | 3,400 | each |
| `ELC-005` | Contactor / starter module | electrical | 28,000 | each |
| `ELC-006` | Excitation diode wheel set | electrical | 96,000 | set |
