"""Cross-database consistency suite — gates G-01 .. G-22 (doc 02 §11).

Build-failing proof for evaluation criterion 1. Each gate returns a
``GateResult``; ``run_all`` opens both databases, runs every gate (isolating
exceptions so one failure doesn't hide the rest), and prints a report.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta, timezone

import numpy as np

from .. import catalog
from ..config import Settings, get_settings
from ..db import constraints
from ..db import neo4j as neo
from ..db import postgres as pg

REQUIRED_LABELS = set(constraints.NODE_LABELS)
REQUIRED_RELS = set(constraints.REL_TYPES)


@dataclass(slots=True)
class GateResult:
    gate: str
    title: str
    passed: bool
    detail: str = ""


@dataclass(slots=True)
class Ctx:
    settings: Settings
    conn: object       # psycopg connection
    driver: object     # neo4j driver


# ── helpers ──────────────────────────────────────────────────────────────────
def _scalar(cx: Ctx, sql: str, params=None):
    row = pg.fetchone(cx.conn, sql, params)
    return row[0] if row else None


def _cypher1(cx: Ctx, cypher: str, params=None):
    rows = neo.run_read(cx.driver, cypher, params, settings=cx.settings)
    return rows[0] if rows else None


def _pg_columns(cx: Ctx, table: str) -> list[str]:
    rows = pg.fetchall(cx.conn,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name <> 'ts' ORDER BY ordinal_position",
        (table,))
    return [r[0] for r in rows]


# ── gates ────────────────────────────────────────────────────────────────────
def g01(cx: Ctx) -> GateResult:
    rows = pg.fetchall(cx.conn,
        "SELECT tablename FROM pg_tables WHERE schemaname='public'")
    names = {r[0] for r in rows}
    need = set(catalog.systems())
    ok = need.issubset(names)
    return GateResult("G-01", "5 required tables exist", ok,
                      f"missing: {sorted(need - names)}" if not ok else f"{sorted(need)}")


def g02(cx: Ctx) -> GateResult:
    problems = []
    for s in catalog.systems():
        ncol = len(_pg_columns(cx, s))
        want = catalog.tag_count(s)
        if not (100 <= ncol <= 200):
            problems.append(f"{s}: {ncol} cols outside [100,200]")
        if ncol != want:
            problems.append(f"{s}: {ncol} cols != catalog {want}")
        long_n = _scalar(cx, f'SELECT count(*) FROM "{s}_long" '
                             f'WHERE ts = (SELECT max(ts) FROM "{s}")')
        if long_n != want:
            problems.append(f"{s}: _long yields {long_n} != {want}")
        sysnode = _cypher1(cx, "MATCH (s:System {name:$n}) RETURN s.tag_count AS c", {"n": s})
        if not sysnode or sysnode["c"] != want:
            problems.append(f"{s}: System.tag_count mismatch")
    return GateResult("G-02", "column counts in [100,200] & consistent",
                      not problems, "; ".join(problems))


def g03(cx: Ctx) -> GateResult:
    st = cx.settings
    problems = []
    for s in catalog.systems():
        n, mn, mx = pg.fetchone(cx.conn,
            f'SELECT count(*), min(ts), max(ts) FROM "{s}"')
        ndist = _scalar(cx, f'SELECT count(DISTINCT ts) FROM "{s}"')
        if n != st.n_steps:
            problems.append(f"{s}: {n} rows != {st.n_steps}")
        if ndist != n:
            problems.append(f"{s}: duplicate ts")
        def _utc(dt):
            if dt is None:
                return None
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo \
                else dt.replace(tzinfo=None)
        ws = st.window_start.astimezone(timezone.utc).replace(tzinfo=None)
        if _utc(mn) != ws:
            problems.append(f"{s}: min(ts) {mn} != {st.window_start}")
        expected_max = (st.window_start + timedelta(
            seconds=(st.n_steps - 1) * st.sample_seconds)).astimezone(timezone.utc).replace(tzinfo=None)
        if _utc(mx) != expected_max:
            problems.append(f"{s}: max(ts) {mx} != {expected_max}")
    return GateResult("G-03", "30-day axis: rows, bounds, no gaps/dupes",
                      not problems, "; ".join(problems))


def g04(cx: Ctx) -> GateResult:
    required = ("pressure", "temperature", "flow", "vibration")
    problems = []
    for s in catalog.systems():
        rows = pg.fetchall(cx.conn,
            "SELECT DISTINCT family FROM sensor_catalog WHERE system=%s", (s,))
        fams = {r[0] for r in rows}
        for req in required:
            if req not in fams:
                problems.append(f"{s}: missing {req}")
    return GateResult("G-04", "pressure/temperature/flow/vibration per table",
                      not problems, "; ".join(problems))


def g05(cx: Ctx) -> GateResult:
    rows = neo.run_read(cx.driver, "CALL db.labels() YIELD label RETURN label",
                        settings=cx.settings)
    labels = {r["label"] for r in rows}
    ok = labels == REQUIRED_LABELS
    return GateResult("G-05", "exactly 5 node labels", ok, f"{sorted(labels)}")


def g06(cx: Ctx) -> GateResult:
    rows = neo.run_read(cx.driver,
        "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType",
        settings=cx.settings)
    rels = {r["relationshipType"] for r in rows}
    problems = []
    if rels != REQUIRED_RELS:
        problems.append(f"types={sorted(rels)}")
    checks = [
        ("GENERATED_ON", "Alert", "System"),
        ("PERFORMED_ON", "MaintenanceLog", "System"),
        ("MEASURED_AT", "Tag", "System"),
        ("CONSUMED", "MaintenanceLog", "Item"),
    ]
    for rel, a, b in checks:
        bad = _cypher1(cx, f"MATCH (x)-[r:{rel}]->(y) "
                           f"WHERE NOT (x:{a} AND y:{b}) RETURN count(r) AS c")
        if bad and bad["c"]:
            problems.append(f"{rel}: {bad['c']} wrong-direction")
    return GateResult("G-06", "4 rel types, correct direction", not problems,
                      "; ".join(problems))


def g07(cx: Ctx) -> GateResult:
    import re
    forbidden = re.compile(r"value|reading|measurement|sample|series|history", re.I)
    problems = []
    for label in REQUIRED_LABELS:
        rows = neo.run_read(cx.driver, f"MATCH (n:{label}) RETURN n LIMIT 5000",
                            settings=cx.settings)
        for r in rows:
            props = r["n"]
            for k, v in props.items():
                if isinstance(v, (list, tuple)) and v and all(
                        isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                    problems.append(f"{label}.{k} numeric array")
                    break
            if label == "Tag":
                for k in props:
                    if forbidden.search(k):
                        problems.append(f"Tag.{k} matches forbidden pattern")
        if problems:
            break
    return GateResult("G-07", "Data Separation Rule (no telemetry in Neo4j)",
                      not problems, "; ".join(sorted(set(problems))[:5]))


def g08(cx: Ctx) -> GateResult:
    problems = []
    for s in catalog.systems():
        pg_cols = set(_pg_columns(cx, s))
        rows = neo.run_read(cx.driver,
            "MATCH (t:Tag {system:$s}) RETURN t.tag_name AS n, t.unit AS u", {"s": s})
        neo_tags = {r["n"] for r in rows}
        if pg_cols != neo_tags:
            problems.append(f"{s}: pg\\neo={sorted(pg_cols-neo_tags)[:3]} "
                            f"neo\\pg={sorted(neo_tags-pg_cols)[:3]}")
        # unit consistency: catalog == sensor_catalog == Tag
        cat = catalog.tag_map(s)
        neo_units = {r["n"]: r["u"] for r in rows}
        srows = pg.fetchall(cx.conn,
            "SELECT tag_name, unit FROM sensor_catalog WHERE system=%s", (s,))
        sc_units = {r[0]: r[1] for r in srows}
        for name, spec in cat.items():
            if neo_units.get(name) != spec.unit or sc_units.get(name) != spec.unit:
                problems.append(f"{s}.{name}: unit mismatch")
                break
    return GateResult("G-08", "Tag names/units match Postgres both ways",
                      not problems, "; ".join(problems[:4]))


def g09(cx: Ctx) -> GateResult:
    bad = _cypher1(cx,
        "MATCH (m:MaintenanceLog) "
        "OPTIONAL MATCH (m)-[:PERFORMED_ON]->(s:System) "
        "WITH m, collect(s) AS ss "
        "WHERE size(ss) <> 1 OR ss[0].name <> m.system "
        "RETURN count(m) AS c")
    c = bad["c"] if bad else -1
    return GateResult("G-09", "MaintenanceLog PERFORMED_ON exactly one matching System",
                      c == 0, f"{c} bad")


def g10(cx: Ctx) -> GateResult:
    orphan = _cypher1(cx,
        "MATCH (i:Item) WHERE NOT (i)<-[:CONSUMED]-() RETURN count(i) AS c")
    c = orphan["c"] if orphan else -1
    return GateResult("G-10", "no orphan Items (all CONSUMED)", c == 0, f"{c} orphans")


def g11(cx: Ctx) -> GateResult:
    bad = _cypher1(cx,
        "MATCH (a:Alert) OPTIONAL MATCH (a)-[:GENERATED_ON]->(s:System) "
        "WITH a, collect(s) AS ss WHERE size(ss) <> 1 OR ss[0].name <> a.system "
        "RETURN count(a) AS c")
    c = bad["c"] if bad else -1
    # tag_name exists in that system's catalog
    rows = neo.run_read(cx.driver, "MATCH (a:Alert) RETURN a.system AS s, a.tag_name AS t",
                        settings=cx.settings)
    missing = [f"{r['s']}.{r['t']}" for r in rows
               if r["t"] not in catalog.tag_map(r["s"])]
    ok = c == 0 and not missing
    return GateResult("G-11", "Alert GENERATED_ON one System; tag in catalog", ok,
                      f"{c} bad edges; missing tags {missing[:3]}")


def g12(cx: Ctx) -> GateResult:
    row = _cypher1(cx,
        "MATCH (m:MaintenanceLog) "
        "OPTIONAL MATCH (m)-[:CONSUMED]->(i:Item) "
        "WITH m, count(DISTINCT i) AS c "
        "RETURN avg(CASE WHEN c>=3 THEN 1.0 ELSE 0.0 END) AS frac, count(m) AS n")
    frac = row["frac"] if row else 0
    return GateResult("G-12", ">=40% logs consume >=3 items", (frac or 0) >= 0.40,
                      f"frac={frac:.2f}")


def g13(cx: Ctx) -> GateResult:  # DG-2
    st = cx.settings
    day_start = st.anchor - timedelta(days=1)
    frac = _scalar(cx, 'SELECT avg(pump_running) FROM bfpa WHERE ts >= %s', (day_start,))
    ok = frac is not None and frac >= 0.90
    return GateResult("G-13", "DG-2: bfpa running >=90% day before anchor", ok,
                      f"frac={frac:.2f}" if frac is not None else "none")


def g14(cx: Ctx) -> GateResult:  # DG-3
    st = cx.settings
    w = st.anchor - timedelta(days=7)
    ra = _scalar(cx, 'SELECT avg(pump_running) FROM bfpa WHERE ts >= %s', (w,))
    rb = _scalar(cx, 'SELECT avg(pump_running) FROM bfpb WHERE ts >= %s', (w,))
    da = _scalar(cx, 'SELECT avg(bearing_temp_1) FROM bfpa WHERE ts >= %s', (w,))
    db = _scalar(cx, 'SELECT avg(bearing_temp_1) FROM bfpb WHERE ts >= %s', (w,))
    ok = (ra >= 0.60 and rb >= 0.60 and (da - db) >= 3.0)
    return GateResult("G-14", "DG-3: last 7d both run; A bearing >=3C higher", ok,
                      f"runA={ra:.2f} runB={rb:.2f} dA-dB={da-db:.1f}")


def g15(cx: Ctx) -> GateResult:
    problems = []
    for s in catalog.systems():
        ncol = len(_pg_columns(cx, s))
        node = _cypher1(cx, "MATCH (t:Tag {system:$s}) RETURN count(t) AS c", {"s": s})
        if not node or node["c"] != ncol:
            problems.append(f"{s}: graph {node['c'] if node else '?'} != pg {ncol}")
    return GateResult("G-15", "graph tag count == Postgres column count",
                      not problems, "; ".join(problems))


def g16(cx: Ctx) -> GateResult:
    bad = _cypher1(cx,
        "MATCH (m:MaintenanceLog)-[c:CONSUMED]->(i:Item) "
        "WITH m, sum(c.line_cost) AS s, "
        "     sum(CASE WHEN abs(c.line_cost - c.quantity*c.unit_cost_at_time)>0.01 "
        "              OR abs(c.unit_cost_at_time - i.unit_cost)>0.01 THEN 1 ELSE 0 END) AS lb "
        "WITH m, s, lb WHERE abs(m.total_item_cost - s) > 0.01 OR lb > 0 "
        "RETURN count(m) AS c")
    tc = _cypher1(cx,
        "MATCH (m:MaintenanceLog) WHERE abs(m.total_cost - (m.total_item_cost + m.labor_cost)) > 0.01 "
        "RETURN count(m) AS c")
    dg5 = _cypher1(cx,
        "MATCH (m:MaintenanceLog {system:'turbine'}) WHERE m.total_item_cost > 0 "
        "RETURN count(m) AS c")
    c1 = bad["c"] if bad else -1
    c2 = tc["c"] if tc else -1
    n5 = dg5["c"] if dg5 else 0
    ok = c1 == 0 and c2 == 0 and n5 >= 8
    return GateResult("G-16", "cost identities hold; DG-5 turbine>=8 logs", ok,
                      f"itembad={c1} totalbad={c2} turbine_cost_logs={n5}")


def g17(cx: Ctx) -> GateResult:  # DG-4
    st = cx.settings
    ws = st.window_start.isoformat()
    rows = neo.run_read(cx.driver,
        "MATCH (m:MaintenanceLog {system:'cepa'}) "
        "WHERE m.start_ts >= datetime($ws) "
        "RETURN m.work_order_id AS w, toString(m.start_ts) AS t ORDER BY m.start_ts",
        {"ws": ws}, settings=st)
    if len(rows) < 2:
        return GateResult("G-17", "DG-4: cepa >=2 in-window; latest >=3 distinct-qty items",
                          False, f"only {len(rows)} in-window logs")
    latest = rows[-1]["w"]
    items = neo.run_read(cx.driver,
        "MATCH (m:MaintenanceLog {work_order_id:$w})-[c:CONSUMED]->(i:Item) "
        "RETURN c.quantity AS q", {"w": latest}, settings=st)
    qtys = [r["q"] for r in items]
    ok = len(qtys) >= 3 and len(set(qtys)) == len(qtys)
    return GateResult("G-17", "DG-4: cepa >=2 in-window; latest >=3 distinct-qty items",
                      ok, f"latest={latest} items={len(qtys)} qtys={qtys}")


def g18(cx: Ctx) -> GateResult:
    rows = pg.fetchall(cx.conn,
        "SELECT flow_rate, pump_efficiency, vibration_overall FROM bfpa")
    X = np.array([[r[0], r[1], r[2]] for r in rows if None not in r], dtype=float)
    X = X[~np.isnan(X).any(axis=1)]
    if len(X) < 100:
        return GateResult("G-18", "operating regions separable (silhouette>=0.45)",
                          False, "insufficient rows")
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    rng = np.random.default_rng(0)
    idx = rng.choice(len(Z), min(4000, len(Z)), replace=False)
    km = KMeans(n_clusters=4, n_init=10, random_state=0).fit(Z[idx])
    sub = rng.choice(len(idx), min(1500, len(idx)), replace=False)
    sil = silhouette_score(Z[idx][sub], km.labels_[sub])
    return GateResult("G-18", "operating regions separable (silhouette>=0.45)",
                      sil >= 0.45, f"silhouette={sil:.3f}")


def g19(cx: Ctx) -> GateResult:  # DG-1
    latest = _cypher1(cx,
        "MATCH (a:Alert {system:'bfpa'}) WHERE a.has_telemetry = true "
        "RETURN a.tag_name AS tag, a.threshold_value AS thr, "
        "toString(a.start_ts) AS s, toString(a.end_ts) AS e "
        "ORDER BY a.start_ts DESC LIMIT 1")
    if not latest:
        return GateResult("G-19", "DG-1: latest bfpa alert is bearing-temp excursion",
                          False, "no bfpa telemetry alert")
    if latest["tag"] != "bearing_temp_1":
        return GateResult("G-19", "DG-1: latest bfpa alert is bearing-temp excursion",
                          False, f"latest tag={latest['tag']}")
    mx = _scalar(cx, 'SELECT max(bearing_temp_1) FROM bfpa WHERE ts >= %s AND ts <= %s',
                 (latest["s"], latest["e"]))
    ok = mx is not None and mx >= latest["thr"] + 2.0
    return GateResult("G-19", "DG-1: latest bfpa alert is bearing-temp excursion", ok,
                      f"max={mx:.1f} thr={latest['thr']:.1f}")


def g20(cx: Ctx) -> GateResult:
    st = cx.settings
    logs = neo.run_read(cx.driver,
        "MATCH (m:MaintenanceLog)-[:PERFORMED_ON]->(s:System) "
        "WHERE m.related_alert_id IS NOT NULL "
        "  AND m.maintenance_class IN ['corrective','predictive'] "
        "MATCH (a:Alert {alert_id: m.related_alert_id}) "
        "WHERE a.alert_type <> 'data_quality' "
        "RETURN m.system AS sys, a.tag_name AS tag, toString(m.end_ts) AS end",
        settings=st)
    problems = []
    for L in logs:
        sys, tag, end = L["sys"], L["tag"], L["end"]
        spec = catalog.tag_map(sys)[tag]
        center = 0.5 * (spec.normal_min + spec.normal_max)
        pre = _scalar(cx, f'SELECT avg("{tag}") FROM "{sys}" '
                          f"WHERE ts >= (%s::timestamptz - interval '6 hour') AND ts < %s",
                      (end, end))
        post = _scalar(cx, f'SELECT avg("{tag}") FROM "{sys}" '
                           f"WHERE ts >= %s AND ts < (%s::timestamptz + interval '6 hour')",
                       (end, end))
        if pre is None or post is None:
            problems.append(f"{sys}.{tag}: no data")
        elif abs(post - center) >= abs(pre - center) - 1e-6:
            problems.append(f"{sys}.{tag}: pre_dev={abs(pre-center):.1f} post_dev={abs(post-center):.1f}")
    return GateResult("G-20", "corrective repairs visible in telemetry",
                      not problems, "; ".join(problems[:4]) or f"{len(logs)} logs OK")


def g21(cx: Ctx) -> GateResult:
    problems = []
    total_cells = 0
    total_nulls = 0
    for s in catalog.systems():
        cols = _pg_columns(cx, s)
        status_cols = {t.tag_name for t in catalog.tags_for(s) if t.family == "status"}
        # one wide query: nulls + distinct per column
        exprs = []
        for c in cols:
            exprs.append(f'sum(CASE WHEN "{c}" IS NULL THEN 1 ELSE 0 END)')
            exprs.append(f'count(DISTINCT "{c}")')
        row = pg.fetchone(cx.conn, f'SELECT count(*), {", ".join(exprs)} FROM "{s}"')
        n = row[0]
        vals = row[1:]
        for i, c in enumerate(cols):
            nulls = vals[2 * i] or 0
            distinct = vals[2 * i + 1] or 0
            total_cells += n
            total_nulls += nulls
            if nulls == n:
                problems.append(f"{s}.{c} all NULL")
            if distinct <= 1 and c not in status_cols:
                problems.append(f"{s}.{c} constant")
    frac = total_nulls / total_cells if total_cells else 0
    if frac > 0.0015:
        problems.append(f"null fraction {frac:.4%} > 0.15%")
    return GateResult("G-21", "NULL budget & no constant non-status columns",
                      not problems, f"nulls={frac:.4%}; " + "; ".join(problems[:3]))


def g22(cx: Ctx) -> GateResult:
    from ..datagen.build_telemetry import generate_all
    if cx.settings.now_anchor.strip().lower() == "live":
        return GateResult("G-22", "reproducible content hashes (pinned anchor)",
                          True, "skipped (NOW_ANCHOR=live)")

    def digest() -> str:
        data = generate_all(cx.settings)
        h = hashlib.sha256()
        for s in catalog.systems():
            for name in [t.tag_name for t in catalog.tags_for(s)]:
                arr = np.nan_to_num(data.arrays[s][name], nan=-9.99e9)
                h.update(np.round(arr, 4).tobytes())
        return h.hexdigest()

    d1, d2 = digest(), digest()
    return GateResult("G-22", "reproducible content hashes (pinned anchor)",
                      d1 == d2, f"{d1[:12]} == {d2[:12]}: {d1 == d2}")


GATES = [g01, g02, g03, g04, g05, g06, g07, g08, g09, g10, g11, g12, g13, g14,
         g15, g16, g17, g18, g19, g20, g21, g22]


def run_all(settings: Settings | None = None) -> list[GateResult]:
    settings = settings or get_settings()
    results: list[GateResult] = []
    conn = pg.connect(settings)
    driver = neo.get_driver(settings)
    cx = Ctx(settings=settings, conn=conn, driver=driver)
    try:
        for gate in GATES:
            try:
                results.append(gate(cx))
            except Exception as e:  # isolate a gate's failure
                results.append(GateResult(gate.__name__.upper().replace("G", "G-"),
                                          gate.__doc__ or "", False, f"ERROR: {e}"))
    finally:
        conn.close()
        driver.close()
    return results


def format_report(results: list[GateResult]) -> str:
    lines = ["", "=" * 72, "  CROSS-DATABASE CONSISTENCY REPORT", "=" * 72]
    passed = sum(1 for r in results if r.passed)
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"  [{mark}] {r.gate:6s} {r.title}")
        if r.detail and (not r.passed or True):
            lines.append(f"         └ {r.detail}")
    lines.append("-" * 72)
    lines.append(f"  {passed}/{len(results)} gates green")
    lines.append("=" * 72)
    return "\n".join(lines)


def all_passed(results: list[GateResult]) -> bool:
    return all(r.passed for r in results)
