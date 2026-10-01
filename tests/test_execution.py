"""Tests for the tools layer — validators (safety boundary), resolvers, schema-linking.

DB-free: these exercise the code-owned guarantees without Postgres/Neo4j.
"""
from __future__ import annotations

import pytest

from mas.execution import (
    CypherValidationError,
    PyValidationError,
    SqlValidationError,
    validate_cypher,
    validate_python,
    validate_sql,
)
from mas.execution.timewin import resolve_window


# ── SQL guard (the read-only boundary) ───────────────────────────────────────
def test_sql_accepts_select_and_injects_limit():
    out = validate_sql("SELECT ts, bearing_temp_1 FROM bfpa")
    assert "LIMIT" in out.upper()


def test_sql_keeps_existing_limit():
    out = validate_sql("SELECT ts FROM bfpa LIMIT 5")
    assert out.upper().count("LIMIT") == 1 and "5" in out


def test_sql_accepts_cte_alias():
    # A real trace lost a call to "table not in allowlist: unpivoted" on a valid CTE.
    out = validate_sql(
        "WITH unpivoted AS (SELECT ts, bearing_temp_1 AS val FROM bfpa) "
        "SELECT max(val) FROM unpivoted")
    assert "unpivoted" in out


def test_sql_cte_body_is_still_allowlisted():
    with pytest.raises(SqlValidationError):
        validate_sql("WITH x AS (SELECT * FROM secret_table) SELECT * FROM x")


@pytest.mark.parametrize("bad", [
    "DROP TABLE bfpa",
    "DELETE FROM bfpa",
    "INSERT INTO bfpa (ts) VALUES (now())",
    "UPDATE bfpa SET ts = now()",
    "SELECT ts FROM bfpa; SELECT ts FROM bfpb",   # two statements
    "SELECT * FROM secret_table",                  # not in allowlist
    "SELECT pg_read_file('/etc/passwd')",          # dangerous function
])
def test_sql_rejects_unsafe(bad):
    with pytest.raises(SqlValidationError):
        validate_sql(bad)


# ── Cypher guard ──────────────────────────────────────────────────────────────
def test_cypher_accepts_read():
    q = "MATCH (t:Tag)-[:MEASURED_AT]->(s:System {name:'bfpa'}) RETURN count(t)"
    assert validate_cypher(q) == q


@pytest.mark.parametrize("bad", [
    "CREATE (n:System {name:'x'})",
    "MATCH (n) DELETE n",
    "MATCH (s:System) SET s.x = 1",
    "MATCH (n) DETACH DELETE n",
    "LOAD CSV FROM 'file:///x.csv' AS row RETURN row",
    "MERGE (n:System {name:'x'})",
])
def test_cypher_rejects_writes(bad):
    with pytest.raises(CypherValidationError):
        validate_cypher(bad)


# ── Python guard (accident/correctness guard; container is the real boundary) ──
def test_python_accepts_analysis():
    validate_python("import pandas as pd\nimport numpy as np\nout = df['x'].mean()")


@pytest.mark.parametrize("bad", [
    "import os",
    "from os import system",
    "open('/etc/passwd')",
    "eval('2+2')",
    "os.system('ls')",
    "__import__('os').system('ls')",
    "x = ().__class__.__bases__",
])
def test_python_rejects_unsafe(bad):
    with pytest.raises(PyValidationError):
        validate_python(bad)


# ── what the model reads back from tools ─────────────────────────────────────
class _Runtime:
    tool_call_id = "call-1"


def test_explore_schema_matches_multi_word_terms():
    """'bearing temperature' is how models ask; as one substring it matched nothing."""
    from mas.agents.tools import explore_schema

    cmd = explore_schema.func(_Runtime(), system="bfpa", searches=["bearing temperature"])
    text = cmd.update["messages"][0].content
    assert "no matching tags" not in text
    assert "bfpa.bearing_temp_1" in text and "bfpa.thrust_bearing_temp_active" in text
    assert "vibration" not in text.split("\n", 1)[1]   # every word must match


def test_small_query_result_is_shown_whole():
    """An agent that sees only head(5) of a 14-row answer re-queries to see the rest."""
    import pandas as pd

    from mas.agents.tools import _model_view
    from mas.memory.artifacts import TableArtifact

    df = pd.DataFrame({"tag_name": [f"bearing_temp_{i}" for i in range(14)],
                       "description": ["BFP-A bearing metal temperature"] * 14,
                       "max_v": [65.8] * 13 + [float("nan")]})
    view = _model_view(df, TableArtifact(df=df).digest())
    assert view["complete"] is True
    assert len(view["rows"]) == 15                      # header + every row
    assert view["rows"][-1].endswith("| null")
    assert "head" not in view

    big = pd.DataFrame({"x": range(500)})
    assert "rows" not in _model_view(big, TableArtifact(df=big).digest())



# ── semantic validation (doc 10, S2) ─────────────────────────────────────────
@pytest.mark.parametrize("sql", [
    "SELECT tag_name, MAX(value) AS max_v, (ARRAY_AGG(ts ORDER BY value DESC, ts))[1] AS t "
    "FROM bfpa_long WHERE tag_name IN ('bearing_temp_1') GROUP BY tag_name ORDER BY max_v DESC",
    "SELECT a.ts, a.bearing_temp_1 AS a1, b.bearing_temp_1 AS b1 FROM bfpa a JOIN bfpb b USING (ts)",
    "SELECT date_bin('10 minutes', ts, TIMESTAMPTZ '2026-08-08') AS bucket, AVG(flow_rate) AS f "
    "FROM bfpa GROUP BY bucket ORDER BY bucket",
    "SELECT t.tag, t.v FROM bfpa CROSS JOIN LATERAL (VALUES ('bearing_temp_1', bearing_temp_1)) AS t(tag, v)",
    "SELECT l.tag_name, COUNT(*) FILTER (WHERE l.value > c.alarm_hi) AS n FROM bfpa_long l "
    "JOIN sensor_catalog c ON c.system = 'bfpa' AND c.tag_name = l.tag_name GROUP BY l.tag_name",
])
def test_valid_sql_is_never_blocked_by_column_checks(sql):
    validate_sql(sql)


@pytest.mark.parametrize("sql, hint", [
    ("SELECT max(bearing_temp_9) FROM bfpa", "bearing_temp_8"),
    ("SELECT max(eccentricity) FROM bfpa", "shaft_eccentricity"),     # exists only on turbine
    ("SELECT tag_name, tag_type FROM sensor_catalog", "tag_name"),
])
def test_hallucinated_columns_are_rejected_with_suggestions(sql, hint):
    with pytest.raises(SqlValidationError, match=hint):
        validate_sql(sql)


def test_cypher_string_datetime_compare_is_rejected():
    with pytest.raises(CypherValidationError, match="datetime"):
        validate_cypher("MATCH (a:Alert) WHERE a.start_ts >= '2026-09-01' RETURN a")
    validate_cypher("MATCH (a:Alert) WHERE a.start_ts >= datetime('2026-09-01T00:00:00Z') RETURN a")


def test_explain_notifications_become_problems_with_suggestions():
    from mas.execution.cypher_guard import unknown_names

    notes = [{"code": "Neo.ClientNotification.Statement.UnknownPropertyKeyWarning",
              "description": "... (the missing property name is: peak_valu)"},
             {"code": "Neo.ClientNotification.Statement.UnknownLabelWarning",
              "description": "... (the missing label name is: Alrt)"}]
    problems = unknown_names(notes)
    assert "peak_value" in problems[0] and "Alert" in problems[1]


def test_randomised_estimators_need_a_random_state():
    with pytest.raises(PyValidationError, match="random_state"):
        validate_python("from sklearn.cluster import KMeans\nKMeans(n_clusters=3).fit(df)")
    validate_python("from sklearn.cluster import KMeans\nKMeans(n_clusters=3, random_state=0).fit(df)")


def test_sandbox_persists_state_reports_errors_and_enforces_timeout():
    import pandas as pd

    from mas.execution.py_sandbox import SandboxError, SandboxSession

    s = SandboxSession(backend="subprocess", timeout_s=15)
    try:
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        first = s.run("total = float(df['a'].sum())\nprint(total)", {"t1": df}, "f1.png")
        assert first["ok"] and first["stdout"].strip() == "6.0"
        again = s.run("print(total * 2)", {"t1": df}, "f2.png")          # state persisted
        assert again["ok"] and again["stdout"].strip() == "12.0"
        assert first["figures"] == []
        err = s.run("raise ValueError('boom')", {}, "f3.png")
        assert not err["ok"] and "boom" in err["error"]
        s.timeout_s = 2
        with pytest.raises(SandboxError, match="timed out"):
            s.run("while True:\n    pass", {}, "f4.png")
    finally:
        s.close(force=True)


def test_sandbox_keeps_every_figure_drawn_whatever_the_code_saves():
    import pandas as pd

    from mas.execution.py_sandbox import SandboxSession

    s = SandboxSession(backend="subprocess", timeout_s=30)
    try:
        df = pd.DataFrame({"a": [1.0, 3.0, 2.0], "b": [2.0, 1.0, 4.0]})
        code = "\n".join([
            "fig, ax = plt.subplots()",
            "ax.plot(df['a']); ax.set_title('Series A')",
            "fig.savefig('../../elsewhere/custom.png')",             # redirected into the session
            "fig2, ax2 = plt.subplots(2, 1, sharex=True)",
            "ax2[0].plot(df['b']); fig2.suptitle('Series B panels')",  # never saved
            "plt.figure(); plt.plot(df['a'], df['b']); plt.savefig(OUT)",
        ])
        r = s.run(code, {"t1": df}, "figure_9.png")
        assert r["ok"], r["error"]
        titles = [f["title"] for f in r["figures"]]
        assert len(r["figures"]) == 3 and titles[0] == "Series A" and "Series B panels" in titles
        from pathlib import Path
        assert all(Path(f["path"]).parent == s.workdir and Path(f["path"]).exists()
                   for f in r["figures"])
    finally:
        s.close(force=True)


def _docker_sandbox_available() -> bool:
    """True when a docker daemon is reachable and the sandbox image is built."""
    import subprocess

    from mas.config import get_settings

    try:
        return subprocess.run(["docker", "image", "inspect", get_settings().py_sandbox_image],
                              capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.skipif(not _docker_sandbox_available(),
                    reason="docker daemon or mas-py-sandbox image unavailable")
def test_docker_backend_starts_and_isolates():
    """The docker backend must actually start — and be the boundary it claims to be.

    It regressed unnoticed because the image was never built: the container ran the worker
    as ``-m mas.execution.py_worker``, which executes ``mas/execution/__init__.py`` first,
    which imports config -> pydantic_settings. The image carries only the scientific stack,
    so every container died with ModuleNotFoundError before reading a single request.
    """
    import pandas as pd

    from mas.execution.py_sandbox import SandboxSession

    s = SandboxSession(backend="docker", timeout_s=90)
    try:
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        r = s.run("print(float(df['a'].sum()))", {"t1": df}, "f1.png")
        assert r["ok"], r.get("error")          # the worker starts and frames cross the mount
        assert r["stdout"].strip() == "6.0"

        net = s.run("import socket\nsocket.setdefaulttimeout(5)\n"
                    "socket.create_connection(('1.1.1.1', 53))", {}, "f2.png")
        assert not net["ok"] and "unreachable" in net["error"].lower()   # --network none

        root = s.run("open('/etc/mas_probe', 'w').write('x')", {}, "f3.png")
        assert not root["ok"] and "read-only" in root["error"].lower()   # --read-only

        who = s.run("import os\nprint(os.getuid())", {}, "f4.png")
        assert who["stdout"].strip() == "10001"                          # non-root
    finally:
        s.close(force=True)


# ── specialist-level loop guards ─────────────────────────────────────────────
class _GuardRuntime:
    tool_call_id = "call-1"
    config: dict = {}

    def __init__(self, events):
        self.state = {"tool_events": events}


def test_identical_calls_and_failure_streaks_are_refused():
    from mas.agents.tools import call_hash, loop_guard

    key = call_hash("sql_query", "SELECT 1")
    ok = [{"tool": "sql_query", "call_hash": key, "artifact_id": "t1", "rows": 3}]
    assert "already ran" in loop_guard(_GuardRuntime(ok), "sql_query", call_hash("sql_query", "select   1"))
    bad = [{"tool": "sql_query", "call_hash": key, "error": "column does not exist"}]
    assert "already failed" in loop_guard(_GuardRuntime(bad), "sql_query", key)
    streak = [{"tool": "x", "error": "e"}] * 3
    assert "consecutive" in loop_guard(_GuardRuntime(streak), "sql_query", "other")
    assert loop_guard(_GuardRuntime([]), "sql_query", key) is None


def test_schema_discovery_through_sql_is_refused():
    from mas.agents.tools import _discovery_only

    assert _discovery_only("SELECT * FROM sensor_catalog WHERE system = 'bfpa'")
    assert not _discovery_only("SELECT l.value FROM bfpa_long l JOIN sensor_catalog c ON c.tag_name = l.tag_name")


def test_timewin_delegates_to_frozen_clock():
    from datetime import datetime, timezone
    ref = datetime(2026, 9, 7, tzinfo=timezone.utc)
    t0, t1 = resolve_window("yesterday", ref=ref)
    assert t0.startswith("2026-09-06") and t1.startswith("2026-09-07")


def test_figure_files_are_named_by_id_and_title():
    from mas.agents.tools import figure_filename

    assert figure_filename("f7", "BFP-A bearing temperatures around ALM-BFPA-0009 (03 Sep 00:26–04:10 UTC)") \
        == "f7_bfp-a-bearing-temperatures-around-alm-bfpa-0009-03-sep-00-26-04-10-utc.png"
    long = figure_filename("f2", "Turbine vibration overall versus gross power across the whole telemetry window with alarm lines")
    assert long.startswith("f2_turbine-vibration") and len(long) <= len("f2_") + 70 + 4
    assert not long[:-4].endswith("-")
    assert figure_filename("f3", "") == "f3_untitled.png"
