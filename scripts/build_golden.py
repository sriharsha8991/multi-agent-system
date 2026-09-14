"""Build the golden evaluation dataset from the LIVE databases.

Ground truth is computed by **direct** SQL/Cypher against Postgres + Neo4j — independent of
the agent pipeline — so the eval scores answers against an authoritative reference. Windows
resolve against the frozen anchor with the same clock the agents use.

    python scripts/build_golden.py        # writes eval/golden_dataset.json

20 cases (doc 10 §6): the original eight, paraphrases of four of them (reproducibility),
glossary-concept questions, a no-time history question (the 'last 24 months' trap), an
explicit-date duration question, a root-cause question and an out-of-scope question.
Each case carries ``checks``: numbers that must appear, groups of strings of which one must
appear, whether a figure is required, and whether the question must be answered with no
delegation. This does NOT run the agents.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mas.catalog import glossary                # noqa: E402
from mas.config import get_settings             # noqa: E402
from mas.db import neo4j as neo                 # noqa: E402
from mas.db import postgres                     # noqa: E402
from mas.harness import clock                   # noqa: E402

WINNER_NAMES = {
    "bfpa": ["bfpa", "BFP-A", "Pump A", "Boiler Feed Pump A"],
    "bfpb": ["bfpb", "BFP-B", "Pump B", "Boiler Feed Pump B"],
    "cepa": ["cepa", "CEP-A", "Condensate Extraction Pump A"],
    "cepb": ["cepb", "CEP-B", "Condensate Extraction Pump B"],
}


def _win(expr: str) -> tuple[str, str]:
    t0, t1 = clock.resolve_window(expr)
    return t0.isoformat(), t1.isoformat()


def _scalar(conn, sql: str):
    v = postgres.fetchone(conn, sql)
    return None if v is None or v[0] is None else float(v[0])


def case(cid, kind, query, route, checks, truth, source=None):
    return {"id": cid, "kind": kind, "query": query, "expected_route": route, "checks": checks,
            "ground_truth": truth, "source": source or {}}


def build() -> dict:
    s = get_settings()
    conn = postgres.connect(reader=True)
    driver = neo.get_driver()
    cases: list[dict] = []
    try:
        y0, y1 = _win("yesterday")
        w0, w1 = _win("last 7 days")
        read = lambda q, p=None: neo.run_read(driver, q, p or {})  # noqa: E731

        # ── original eight ────────────────────────────────────────────────────
        a1 = _scalar(conn, f"SELECT max(bearing_temp_1) FROM bfpa WHERE ts >= '{y0}' AND ts < '{y1}'")
        cases.append(case("A1", "sql_stat",
                          "What was the maximum bearing_temp_1 recorded on Boiler Feed Pump A yesterday?",
                          ["sql"], {"numbers": [a1]}, {"max": a1, "window": [y0, y1]}))

        avg_a = _scalar(conn, f"SELECT avg(bearing_temp_1) FROM bfpa WHERE ts >= '{w0}' AND ts < '{w1}'")
        avg_b = _scalar(conn, f"SELECT avg(bearing_temp_1) FROM bfpb WHERE ts >= '{w0}' AND ts < '{w1}'")
        win2 = "bfpa" if avg_a >= avg_b else "bfpb"
        cases.append(case("A2", "sql_compare",
                          "Which BFP had the higher average bearing_temp_1 over the last 7 days, Pump A or Pump B?",
                          ["sql"], {"any_of": [WINNER_NAMES[win2]]},
                          {"bfpa_avg": avg_a, "bfpb_avg": avg_b, "winner": win2, "window": [w0, w1]}))

        n_tags = read("MATCH (t:Tag)-[:MEASURED_AT]->(:System {name:'bfpa'}) RETURN count(t) AS c")[0]["c"]
        cases.append(case("A3", "graph_count", "How many sensors (tags) are present on BFP-A?",
                          ["graph"], {"numbers": [n_tags]}, {"tag_count": n_tags}))

        mr = read("MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(:System {name:'turbine'}) "
                  "RETURN count(m) AS count, sum(m.total_item_cost) AS item_cost")[0]
        cases.append(case("A4", "graph_rollup",
                          "How many maintenance activities were performed on the Turbine, and the total item cost?",
                          ["graph"], {"numbers": [mr["count"], mr["item_cost"]]},
                          {"count": mr["count"], "total_item_cost": mr["item_cost"], "currency": s.currency}))

        items = read("MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(:System {name:'cepa'}) "
                     "WITH m ORDER BY m.start_ts DESC LIMIT 1 MATCH (m)-[c:CONSUMED]->(i:Item) "
                     "RETURN m.work_order_id AS wo, i.name AS item, c.quantity AS q, c.line_cost AS cost "
                     "ORDER BY q DESC, cost DESC, item")
        top = items[0]["item"]
        cases.append(case("A5", "graph_rank",
                          "Which spare parts were consumed the most during the latest maintenance activity on CEP-A?",
                          ["graph"], {"any_of": [[top.split(",")[0]]]},
                          {"work_order": items[0]["wo"], "top_item": top,
                           "items": [dict(r) for r in items]}))

        r6 = _scalar(conn, f"SELECT corr(flow_rate, pump_head) FROM bfpa WHERE ts >= '{w0}' AND ts < '{w1}'")
        cases.append(case("A6", "chart", "Plot the correlation between flow and head on BFP-A over the last 7 days.",
                          ["sql", "python"], {"figure": True}, {"pearson_r_raw_minutes": r6, "window": [w0, w1]},
                          {"note": "r is recorded for inspection; a bucketed series can differ slightly"}))

        cases.append(case("A7", "analysis",
                          "Cluster BFP-A operating data into operating regions using load, efficiency and vibration.",
                          ["sql", "python"], {"figure": False},
                          {"features": [glossary.resolve(c, 'bfpa').primary.tag_name
                                        for c in ("load", "efficiency", "vibration")]}))

        alert = read("MATCH (a:Alert)-[:GENERATED_ON]->(:System {name:'bfpa'}) WHERE a.has_telemetry = true "
                     "RETURN a.alert_id AS alert_id, a.tag_name AS tag ORDER BY a.start_ts DESC, a.alert_id DESC LIMIT 1")[0]
        cases.append(case("A8", "multi_agent",
                          "What is the latest alert on BFP-A, and can you plot the bearing temperature during that alert window?",
                          ["graph", "sql", "python"], {"any_of": [[alert["alert_id"]]], "figure": True},
                          {"alert_id": alert["alert_id"], "tag": alert["tag"]}))

        # ── paraphrases (same information, different words) ───────────────────
        cases.append(case("A9", "paraphrase:A1", "What's the highest bearing_temp_1 reading on pump A yesterday?",
                          ["sql"], {"numbers": [a1]}, {"same_as": "A1"}))
        cases.append(case("A10", "paraphrase:A3", "How many tags does Boiler Feed Pump A have?",
                          ["graph"], {"numbers": [n_tags]}, {"same_as": "A3"}))
        cases.append(case("A11", "paraphrase:A4",
                          "Count the turbine's work orders and total the item cost across them.",
                          ["graph"], {"numbers": [mr["count"], mr["item_cost"]]}, {"same_as": "A4"}))
        cases.append(case("A12", "paraphrase:A2",
                          "Between BFP-A and BFP-B, whose bearing_temp_1 averaged higher over the past week?",
                          ["sql"], {"any_of": [WINNER_NAMES[win2]]}, {"same_as": "A2"}))

        # ── glossary concepts ─────────────────────────────────────────────────
        bt = ", ".join(f"'{t.tag_name}'" for t in glossary.resolve("bearing temperature", "bfpa").tags)
        a13 = _scalar(conn, f"SELECT max(value) FROM bfpa_long WHERE tag_name IN ({bt}) AND ts >= '{y0}' AND ts < '{y1}'")
        cases.append(case("A13", "concept",
                          "What was the maximum bearing temperature across all BFP-A bearings yesterday?",
                          ["sql"], {"numbers": [a13]}, {"max": a13, "concept": "bearing temperature"}))

        # A clear margin on purpose: CEP-A/B average motor current differ by 0.004% (478.07 vs
        # 478.05 A), which would test tag-set definitions, not the system's determinism.
        peaks = {}
        for sys_ in ("bfpa", "bfpb"):
            names = ", ".join(f"'{t.tag_name}'" for t in glossary.resolve("bearing temperature", sys_).tags)
            peaks[sys_] = _scalar(conn, f"SELECT max(value) FROM {sys_}_long WHERE tag_name IN ({names}) "
                                        f"AND ts >= '{w0}' AND ts < '{w1}'")
        win14 = max(peaks, key=peaks.get)
        cases.append(case("A14", "concept_compare",
                          "Which boiler feed pump reached the higher bearing temperature over the last 7 days?",
                          ["sql"], {"any_of": [WINNER_NAMES[win14]], "numbers": [peaks[win14]]},
                          {"peaks": peaks, "winner": win14}))

        # ── ledger traps and new shapes ───────────────────────────────────────
        n_alerts = read("MATCH (a:Alert)-[:GENERATED_ON]->(:System {name:'turbine'}) WHERE a.has_telemetry = true "
                        "RETURN count(a) AS c")[0]["c"]
        cases.append(case("A15", "graph_count", "How many alerts did the turbine raise inside the telemetry window?",
                          ["graph"], {"numbers": [n_alerts]}, {"count": n_alerts}))

        down = read("MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(:System {name:'cepa'}) "
                    "RETURN sum(m.downtime_hours) AS h, count(m) AS n")[0]
        cases.append(case("A16", "no_time_history",
                          "What is the total downtime in hours across all maintenance on CEP-A?",
                          ["graph"], {"numbers": [down["h"]]}, {"downtime_hours": down["h"], "work_orders": down["n"]},
                          {"note": "no time in the question — a window added by the orchestrator would drop records"}))

        d0, d1 = "2026-09-03T00:00:00+00:00", "2026-09-04T00:00:00+00:00"
        minutes = _scalar(conn, f"SELECT count(*) FROM bfpa WHERE bearing_temp_1 > 90 AND ts >= '{d0}' AND ts < '{d1}'")
        minutes = minutes * s.sample_seconds / 60
        cases.append(case("A17", "duration",
                          "For how many minutes was BFP-A bearing_temp_1 above its alarm_hi on 2026-09-03?",
                          ["sql"], {"numbers": [minutes]}, {"minutes_above_alarm_hi": minutes, "alarm_hi": 90}))

        crit = read("MATCH (a:Alert)-[:GENERATED_ON]->(s:System {name:'bfpa'}) WHERE a.severity = 'critical' "
                    "WITH a, s ORDER BY a.start_ts DESC, a.alert_id DESC LIMIT 1 "
                    "OPTIONAL MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(s) WHERE m.related_alert_id = a.alert_id "
                    "RETURN a.alert_id AS alert_id, collect(m.work_order_id) AS wos")[0]
        checks18 = {"any_of": [[crit["alert_id"]]] + ([[w] for w in crit["wos"][:1]])}
        cases.append(case("A18", "root_cause",
                          "Why did BFP-A raise its latest critical alert, and did any maintenance follow?",
                          ["graph", "sql"], checks18, {"alert_id": crit["alert_id"], "work_orders": crit["wos"]}))

        cases.append(case("A19", "out_of_scope", "What will the weather be at the plant tomorrow?",
                          [], {"no_delegation": True,
                               "any_of": [["cannot", "can't", "not able", "unable", "don't have", "do not have",
                                           "no data", "outside", "not available"]]},
                          {"note": "no capability answers this"}))

        latest = read("MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(:System {name:'cepa'}) "
                      "RETURN m.work_order_id AS wo, m.total_cost AS cost ORDER BY m.start_ts DESC LIMIT 1")[0]
        cases.append(case("A20", "graph_value", "What did the latest maintenance on CEP-A cost in total?",
                          ["graph"], {"numbers": [latest["cost"]]}, {"work_order": latest["wo"], "total_cost": latest["cost"]}))

        meta = dict(postgres.fetchall(conn, "SELECT key, value FROM run_metadata"))
        return {
            "meta": {
                "created_from": "live Postgres + Neo4j (direct queries, independent of the agent pipeline)",
                "snapshot": {k: meta.get(k) for k in ("generator_version", "master_seed", "now_anchor",
                                                      "window_start", "window_end")},
                "currency": s.currency,
            },
            "cases": cases,
        }
    finally:
        conn.close()
        driver.close()


if __name__ == "__main__":
    data = build()
    out = ROOT / "eval" / "golden_dataset.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out}  ({len(data['cases'])} cases)")
