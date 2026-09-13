"""Build the golden evaluation dataset from the LIVE databases.

Ground truth is computed by **direct** SQL/Cypher against Postgres + Neo4j — independent of
the agent pipeline — so a later eval can score the agents' answers against an authoritative
reference. Windows resolve against the frozen anchor with the same code the agents use.

    python scripts/build_golden.py        # writes eval/golden_dataset.json

This does NOT run the agents or any eval. It only records expected routes + values.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mas.config import get_settings           # noqa: E402
from mas.db import neo4j as neo               # noqa: E402
from mas.db import postgres                    # noqa: E402
from mas.harness import clock                  # noqa: E402


def _win(expr: str) -> tuple[str, str]:
    t0, t1 = clock.resolve_window(expr)
    return t0.isoformat(), t1.isoformat()


def _scalar(conn, sql: str):
    v = postgres.fetchone(conn, sql)
    return None if v is None or v[0] is None else float(v[0])


def build() -> dict:
    s = get_settings()
    conn = postgres.connect(reader=True)
    driver = neo.get_driver()
    cases: list[dict] = []

    try:
        y0, y1 = _win("yesterday")
        w0, w1 = _win("last 7 days")

        # A1 — single-system stat (yesterday)
        sql = f"SELECT max(bearing_temp_1) FROM bfpa WHERE ts >= '{y0}' AND ts < '{y1}'"
        cases.append({
            "id": "A1", "kind": "sql_stat",
            "query": "What was the maximum bearing_temp_1 recorded on Boiler Feed Pump A yesterday?",
            "expected_route": ["sql.aggregate_stat"],
            "ground_truth": {"max_bearing_temp_1": _scalar(conn, sql), "window": [y0, y1]},
            "source": {"sql": sql},
        })

        # A2 — cross-system comparison (7-day avg)
        a = _scalar(conn, f"SELECT avg(bearing_temp_1) FROM bfpa WHERE ts >= '{w0}' AND ts < '{w1}'")
        b = _scalar(conn, f"SELECT avg(bearing_temp_1) FROM bfpb WHERE ts >= '{w0}' AND ts < '{w1}'")
        cases.append({
            "id": "A2", "kind": "sql_compare",
            "query": "Which BFP had the higher average bearing_temp_1 over the last 7 days, Pump A or Pump B?",
            "expected_route": ["sql.compare_systems"],
            "ground_truth": {"bfpa_avg": a, "bfpb_avg": b,
                             "winner": "bfpa" if (a or 0) >= (b or 0) else "bfpb", "window": [w0, w1]},
            "source": {"sql_bfpa": f"SELECT avg(bearing_temp_1) FROM bfpa WHERE ts >= '{w0}' AND ts < '{w1}'",
                       "sql_bfpb": f"SELECT avg(bearing_temp_1) FROM bfpb WHERE ts >= '{w0}' AND ts < '{w1}'"},
        })

        # A3 — structural tag count per system (graph)  == Postgres non-ts column count
        counts = {}
        for name in ("bfpa", "bfpb", "cepa", "cepb", "turbine"):
            g = neo.run_read(driver, "MATCH (t:Tag)-[:MEASURED_AT]->(:System {name:$n}) RETURN count(t) AS c",
                             {"n": name})[0]["c"]
            counts[name] = g
        cases.append({
            "id": "A3", "kind": "graph_count",
            "query": "How many sensors (tags) are present on BFP-A?",
            "expected_route": ["graph.tag_count_for_system"],
            "ground_truth": {"tag_count_bfpa": counts["bfpa"], "tag_counts_all": counts},
            "source": {"cypher": "MATCH (t:Tag)-[:MEASURED_AT]->(:System {name:$n}) RETURN count(t)"},
        })

        # A4 — aggregation over a path (turbine maintenance)
        mr = neo.run_read(driver,
            "MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(:System {name:'turbine'}) "
            "RETURN count(m) AS count, coalesce(sum(m.total_item_cost),0) AS total_item_cost, "
            "coalesce(sum(m.total_cost),0) AS total_cost")[0]
        cases.append({
            "id": "A4", "kind": "graph_rollup",
            "query": "How many maintenance activities were performed on the Turbine, and the total item cost?",
            "expected_route": ["graph.maintenance_rollup"],
            "ground_truth": {"count": mr["count"], "total_item_cost": mr["total_item_cost"],
                             "total_cost": mr["total_cost"], "currency": s.currency},
            "source": {"cypher": "MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(:System {name:'turbine'}) RETURN count(m), sum(m.total_item_cost)"},
        })

        # A5 — ranking on a relationship property (latest CEP-A work order)
        items = neo.run_read(driver,
            "MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(:System {name:'cepa'}) "
            "WITH m ORDER BY m.start_ts DESC LIMIT 1 "
            "MATCH (m)-[c:CONSUMED]->(i:Item) "
            "RETURN m.work_order_id AS wo, i.name AS item, c.quantity AS quantity, c.line_cost AS line_cost "
            "ORDER BY c.quantity DESC")
        cases.append({
            "id": "A5", "kind": "graph_rank",
            "query": "Which spare parts were consumed the most during the latest maintenance activity on CEP-A?",
            "expected_route": ["graph.top_consumed_items"],
            "ground_truth": {"work_order": items[0]["wo"] if items else None,
                             "items": [{"item": r["item"], "quantity": r["quantity"], "line_cost": r["line_cost"]} for r in items],
                             "top_item": items[0]["item"] if items else None},
            "source": {"cypher": "latest CEP-A WO -> CONSUMED items ORDER BY quantity DESC"},
        })

        # A6 — chart (correlation): the expected DATA, not pixels
        cases.append({
            "id": "A6", "kind": "chart",
            "query": "Plot the correlation between flow and head on BFP-A over the last 7 days.",
            "expected_route": ["sql.tag_table", "python.plot_correlation"],
            "ground_truth": {"criterion": "figure produced with both axes non-empty; series from bfpa over the 7-day window",
                             "window": [w0, w1]},
            "source": {"note": "chart case — scored on artifact kind + underlying data, not pixels"},
        })

        # A7 — regression / clustering (metric threshold from gate G-18)
        cases.append({
            "id": "A7", "kind": "analysis",
            "query": "Cluster BFP-A operating data into operating regions using load, efficiency and vibration.",
            "expected_route": ["sql.tag_table", "python.cluster_operating_regions"],
            "ground_truth": {"features": ["load", "efficiency", "vibration_overall"],
                             "silhouette_min": 0.45, "gate": "G-18"},
            "source": {"note": "metric-threshold case — silhouette >= 0.45 per gate G-18"},
        })

        # A8 — flagship: latest alert on BFP-A + plot the window
        alert = neo.run_read(driver,
            "MATCH (a:Alert)-[:GENERATED_ON]->(:System {name:'bfpa'}) WHERE a.has_telemetry = true "
            "RETURN a.alert_id AS alert_id, a.tag_name AS tag_name, a.start_ts AS start_ts, "
            "a.end_ts AS end_ts, a.threshold_value AS threshold_value, a.peak_value AS peak_value "
            "ORDER BY a.start_ts DESC LIMIT 1")[0]
        st = alert["start_ts"].to_native().isoformat()
        en = alert["end_ts"].to_native().isoformat()
        tag = alert["tag_name"]
        wsql = f"SELECT count(*), max(\"{tag}\") FROM bfpa WHERE ts >= '{st}' AND ts < '{en}'"
        row = postgres.fetchone(conn, wsql)
        cases.append({
            "id": "A8", "kind": "multi_agent",
            "query": "What is the latest alert on BFP-A, and can you plot the bearing temperature during that alert window?",
            "expected_route": ["graph.latest_alert_for_system", "sql.timeseries_window", "python.plot_timeseries"],
            "ground_truth": {"alert_id": alert["alert_id"], "tag_name": tag,
                             "window": [st, en], "threshold_value": alert["threshold_value"],
                             "alert_peak_value": alert["peak_value"],
                             "window_row_count": int(row[0]), "window_max": float(row[1])},
            "source": {"cypher": "latest bfpa Alert with telemetry", "sql": wsql},
        })

        return {
            "meta": {
                "created_from": "live Postgres + Neo4j (direct queries, independent of the agent pipeline)",
                "now_anchor": s.anchor.isoformat(),
                "generator_version": dict(postgres.fetchall(conn, "SELECT key,value FROM run_metadata")).get("generator_version"),
                "currency": s.currency,
                "note": "Golden ground truth for evaluation. Not tested here — see scripts/build_golden.py.",
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
