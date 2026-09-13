"""The agents' tools (L4) and the helpers every tool shares.

    explore_schema      sql_agent     plain words → real sensor tags (catalog, no DB call)
    sql_query           sql_agent     any read-only SELECT over the telemetry
    graph_query         graph_agent   any read-only Cypher over the asset graph
    python_analysis     coder_agent   any analysis and any figures, in the sandbox

Four capable tools rather than a registry of narrow, pre-written queries: the specialists
write the SQL, Cypher and Python themselves, because that is their skill. Pre-written
"recipe" tools were tried and removed (2026-09-14): they fixed the output shape of every
answer, so analyses came back thinner and plots barer than what the agents wrote freely.

Each docstring is the tool's description as the model reads it, so each one tells the tool's
story — what it is for, when to reach for it, how to use it well, what comes back. Code
never writes a query for the model; it only *checks* what the model wrote. The safety
boundary is one layer down in ``mas.execution`` (validators + read-only executors + sandbox).

**Strict, code-level loop guards (doc 10, O5 — code only).** Before any tool runs:

* the identical query / code call already succeeded in this run → refused, pointing
  at its artifact;
* the identical call already failed → refused with the earlier error;
* three consecutive tool failures (including refusals) → every further call is refused
  and the specialist is told to report with the gaps.

**Data separation.** A tool returns ``Command(update=...)``. The full payload goes to the
out-of-band ``memory.store``; graph state and the ``ToolMessage`` get only a bounded digest.

**Observability.** Every call appends a structured record to ``tool_events`` — the exact
SQL/Cypher/code, row counts, duration, errors and a hash used by the loop guards.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sqlglot
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from sqlglot import exp

from ..catalog import SYSTEM_META, all_tags, glossary, search_tags, systems
from ..execution import validate_cypher, validate_python, validate_sql
from ..execution.cypher_exec import explain, run_read
from ..execution.cypher_guard import unknown_names
from ..execution.py_sandbox import SandboxError, session
from ..execution.sql_exec import run_select
from ..execution.timewin import data_bounds
from ..llm.schemas import Provenance
from ..memory import store
from ..memory.artifacts import FigureArtifact, RecordsArtifact, TableArtifact

_FIG_DIR = Path("outputs") / "figures"
_MAX_INLINE_ROWS = 50
_MAX_INLINE_CHARS = 4500   # stays under the 6000-char ToolMessage cap once indented
_MAX_STDOUT = 4000
_MAX_QUERY_LOG = 4000
_MAX_SCHEMA_HITS = 25
#: Consecutive failed tool calls (errors or refusals) after which every call is refused.
MAX_CONSECUTIVE_FAILURES = 3


# ── shared helpers ───────────────────────────────────────────────────────────────
def _json_safe(obj):
    """NaN/Inf are not valid JSON and the model API rejects them — coerce to None."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _msg(runtime: ToolRuntime, payload: dict) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(_json_safe(payload), default=str, indent=2, allow_nan=False)[:6000],
        tool_call_id=runtime.tool_call_id,
    )


def _event(tool_name: str, started: float, **fields) -> dict:
    """One observability record. Lands in state, never in a prompt."""
    return _json_safe({
        "tool": tool_name,
        "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "ms": round((time.perf_counter() - started) * 1000),
        **fields,
    })


def call_hash(tool_name: str, payload) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(f"{tool_name}|{norm}".encode()).hexdigest()[:16]


def loop_guard(runtime: ToolRuntime, tool_name: str, key: str) -> str | None:
    """A refusal reason when this call repeats earlier work or the run keeps failing."""
    events = list((runtime.state or {}).get("tool_events") or [])
    trailing = 0
    for e in reversed(events):
        if not e.get("error"):
            break
        trailing += 1
    if trailing >= MAX_CONSECUTIVE_FAILURES:
        return (f"{trailing} consecutive tool calls failed — stop calling tools and write the "
                "report with what you have; list the failures under gaps")
    for e in reversed(events):
        if e.get("tool") == tool_name and e.get("call_hash") == key:
            if e.get("error"):
                return f"this exact call already failed ({str(e['error'])[:160]}) — change it"
            if e.get("artifact_id"):
                return (f"this exact call already ran → artifact {e['artifact_id']} "
                        f"({e.get('rows', '?')} rows); use that result")
            return "this exact call already ran; use its result"
    return None


def refuse(runtime: ToolRuntime, tool_name: str, t0: float, key: str, reason: str) -> Command:
    return Command(update={
        "tool_events": [_event(tool_name, t0, call_hash=key, error=f"refused: {reason}")],
        "messages": [_msg(runtime, {"refused": reason})],
    })


def failed(runtime: ToolRuntime, tool_name: str, t0: float, key: str, error: str,
           **fields) -> Command:
    return Command(update={
        "tool_events": [_event(tool_name, t0, call_hash=key, error=error[:300], **fields)],
        "messages": [_msg(runtime, {"error": error[:600], **fields})],
    })


def table_result(runtime: ToolRuntime, tool_name: str, t0: float, key: str, df: pd.DataFrame,
                 query: str, extra: dict | None = None, **event_fields) -> Command:
    art = TableArtifact(df=df, provenance=Provenance(capability=tool_name, query=query,
                                                     row_count=len(df)))
    art_id = store.put(art, "t")
    digest = art.digest()
    payload = {"artifact_id": art_id, **model_view(df, digest), **(extra or {})}
    return Command(update={
        "blackboard": {art_id: _json_safe(digest)},
        "tool_events": [_event(tool_name, t0, call_hash=key, db="postgres", rows=len(df),
                               artifact_id=art_id, sql=query[:_MAX_QUERY_LOG], **event_fields)],
        "messages": [_msg(runtime, payload)],
    })


def records_result(runtime: ToolRuntime, tool_name: str, t0: float, key: str, rows: list[dict],
                   query: str, summary: dict | None = None, prefix: str = "g",
                   **event_fields) -> Command:
    rows = [{k: iso(v) for k, v in r.items()} for r in rows]
    art = RecordsArtifact(rows=rows, provenance=Provenance(capability=tool_name, query=query,
                                                           row_count=len(rows)))
    art_id = store.put(art, prefix)
    payload = {"artifact_id": art_id, "row_count": len(rows), **(summary or {}),
               "rows": rows[:_MAX_INLINE_ROWS], "complete": len(rows) <= _MAX_INLINE_ROWS}
    return Command(update={
        "blackboard": {art_id: _json_safe(art.digest())},
        "tool_events": [_event(tool_name, t0, call_hash=key, db="neo4j", rows=len(rows),
                               artifact_id=art_id, cypher=query[:_MAX_QUERY_LOG], **event_fields)],
        "messages": [_msg(runtime, payload)],
    })


def iso(v):
    """Neo4j temporals → ISO strings; nested maps and lists too."""
    if hasattr(v, "to_native"):
        return v.to_native().isoformat()
    if isinstance(v, dict):
        return {k: iso(x) for k, x in v.items()}
    if isinstance(v, list):
        return [iso(x) for x in v]
    return v


def model_view(df: pd.DataFrame, digest: dict) -> dict:
    """What the model reads back from a query: every row when the result is small.

    The digest samples only ``head(5)``. A trace showed an agent with a correct 14-row
    answer re-running the same aggregate three times just to see rows 6-14. Small results
    come back whole as pipe-delimited lines; large ones keep the profile.
    """
    if len(df) > _MAX_INLINE_ROWS:
        return digest
    lines = [" | ".join(map(str, df.columns))]
    lines += [" | ".join(_cell(v) for v in row) for row in df.itertuples(index=False)]
    if sum(len(line) + 8 for line in lines) > _MAX_INLINE_CHARS:
        return digest
    view = {k: v for k, v in digest.items() if k not in ("head", "stats", "null_frac")}
    view["rows"] = lines
    view["complete"] = True
    return view


#: Kept for callers of the older private name.
_model_view = model_view


def _cell(value) -> str:
    """Render one value for the model: nulls explicit, floats at display precision."""
    if value is None or value is pd.NaT or value is pd.NA:
        return "null"
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return f"{round(f, 4):f}".rstrip("0").rstrip(".") if math.isfinite(f) else "null"
    return str(value)


# ── discovery ────────────────────────────────────────────────────────────────────
@tool
def explore_schema(runtime: ToolRuntime, system: str = "",
                   searches: list[str] | str | None = None) -> Command:
    """Find the real sensor tags behind plain words — the map from "bearing temperature" to columns.

    Every system has 100+ tags, and a guessed column name is the most common reason a query
    fails. This reads the in-code catalog (no database call, instant), so reach for it
    whenever you need a tag the brief did not list: a related signal worth checking (the
    motor current next to a hot bearing, the flow behind a head drop), a concept the brief
    left unresolved, or the setpoints you want to compare against.

    Look up several terms in one call. A system's table is its name and each tag is a column
    of that table (and a `tag_name` in `<system>_long`).

    Args:
        system: one system ('bfpa', 'bfpb', 'cepa', 'cepb', 'turbine'); empty = all systems.
        searches: terms, e.g. ['bearing temperature', 'motor current']. A multi-word term
                matches tags containing every word. Omit for a family overview.

    Returns, per match: `system.tag_name [family, unit] normal min..max, alarm_hi, alarm_hihi`,
    whether it is a derived KPI rather than a sensor, and its description.
    """
    t0 = time.perf_counter()
    sysname = (system or "").strip().lower() or None
    if sysname and sysname not in set(systems()):
        text = f"Unknown system {system!r}. Valid: {', '.join(systems())}"
        return Command(update={
            "tool_events": [_event("explore_schema", t0, system=system, error="unknown system")],
            "messages": [ToolMessage(text, tool_call_id=runtime.tool_call_id)],
        })

    tags = [t for t in all_tags() if (not sysname or t.system == sysname)]
    if isinstance(searches, str):
        searches = [searches]
    terms = [s.strip().lower() for s in (searches or []) if s and s.strip()]

    if not terms:
        fams: dict[str, int] = {}
        for t in tags:
            fams[t.family] = fams.get(t.family, 0) + 1
        text = (f"{len(tags)} tags" + (f" on {sysname}" if sysname else " across all systems")
                + "\nfamilies: " + ", ".join(f"{k}={v}" for k, v in sorted(fams.items())))
        hits = len(tags)
    else:
        def _describe(t) -> str:
            return (f"  {t.system}.{t.tag_name}  [{t.family}, {glossary.display_unit(t) or 'no unit'}]  "
                    f"normal {t.normal_min}..{t.normal_max}"
                    + (f"  alarm_hi={t.alarm_hi}" if t.alarm_hi is not None else "")
                    + (f"  alarm_hihi={t.alarm_hihi}" if t.alarm_hihi is not None else "")
                    + ("  [DERIVED - computed KPI, not a sensor]" if t.is_derived else "")
                    + f"  — {t.description}")

        seen: set[tuple[str, str]] = set()
        blocks: list[str] = []
        hits = 0
        for term in terms:
            matches = search_tags(term, sysname)
            hits += len(matches)
            shown = [t for t in matches[:_MAX_SCHEMA_HITS] if (t.system, t.tag_name) not in seen]
            seen.update((t.system, t.tag_name) for t in shown)
            if not matches:
                blocks.append(f"{term!r}: no matching tags")
                continue
            head = f"{term!r}: {len(matches)} matching tags"
            if len(matches) > _MAX_SCHEMA_HITS:
                head += f" (showing first {_MAX_SCHEMA_HITS})"
            blocks.append("\n".join([head] + [_describe(t) for t in shown]))
        text = "\n\n".join(blocks)

    return Command(update={
        "tool_events": [_event("explore_schema", t0, system=system or "(all)",
                               searches=terms or "(overview)", matches=hits)],
        "messages": [ToolMessage(text, tool_call_id=runtime.tool_call_id)],
    })


# ── free-form SQL ────────────────────────────────────────────────────────────────
_TELEMETRY = set(systems()) | {f"{s}_long" for s in systems()}
_ISO_LITERAL = re.compile(r"'(\d{4}-\d{2}-\d{2}(?:[T ][0-9:.]+)?(?:Z|[+-]\d{2}:?\d{2})?)'")
_FLOAT_EQ = re.compile(r"(?<![<>!])=\s*-?\d+\.\d+")


def _discovery_only(sql: str) -> bool:
    """True when a query touches no telemetry relation — schema discovery, not measurement."""
    try:
        tables = {t.name.lower() for t in sqlglot.parse_one(sql, read="postgres").find_all(exp.Table)}
    except Exception:  # noqa: BLE001 — the validator reports parse errors
        return False
    return bool(tables) and not (tables & _TELEMETRY)


def empty_result_hints(sql: str) -> list[str]:
    """Likely reasons a telemetry query returned nothing."""
    hints = []
    start, end = data_bounds()
    lo, hi = datetime.fromisoformat(start), datetime.fromisoformat(end)
    for lit in _ISO_LITERAL.findall(sql):
        try:
            ts = datetime.fromisoformat(lit.replace("Z", "+00:00").replace(" ", "T"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < lo or ts > hi:
            hints.append(f"{lit} is outside telemetry coverage [{start}, {end})")
    if _FLOAT_EQ.search(sql):
        hints.append("equality on a float literal rarely matches — rank with ORDER BY instead")
    known = {t.tag_name for t in all_tags()}
    for name in re.findall(r"tag_name\s*(?:=|IN\s*\()\s*'([^']+)'", sql, re.I):
        if name not in known:
            hints.append(f"tag_name {name!r} does not exist")
    return hints


@tool
def sql_query(sql: str, runtime: ToolRuntime) -> Command:
    """Measure the plant: one read-only SELECT you write over the sensor database.

    This is the only place sensor values exist — 30 days at one row per minute. Write the
    query that answers the slot completely in one go: the statistic, when it happened, which
    tag, how it compares to the setpoints. Let the database do the aggregation.

    The data
    - Wide tables `bfpa, bfpb, cepa, cepb, turbine`: `ts timestamptz` + one column per tag.
    - Long views `<system>_long(ts, tag_name, value)` — easiest for many tags at once.
    - `sensor_catalog(system, tag_name, unit, normal_min, normal_max, alarm_hi, alarm_hihi, …)`
      to join setpoints onto results (not for schema lookups — that is explore_schema).

    Doing it well
    - Window: `ts >= '<start>' AND ts < '<end>'`, exactly as the brief gives it.
    - Many tags: `FROM bfpa_long WHERE tag_name IN (...) GROUP BY tag_name`; for *when* the
      extreme happened use `DISTINCT ON (tag_name) … ORDER BY tag_name, value DESC, ts` or a
      window function. Ties are facts: return every tied tag and the earliest time.
    - Time above a limit: `count(*) FILTER (WHERE value > alarm_hi)` — one row is one minute.
    - Series for a chart: raw rows for a day or two; longer spans bucketed with
      `date_bin('10 minutes', ts, TIMESTAMPTZ '2026-01-01')` keeping avg and max, so peaks
      survive. Keep the tag name and unit so the figure can label them.
    - Comparing systems: one SELECT per table joined with `UNION ALL`, a `system` column each.
    - Never filter on float equality; rank with ORDER BY instead.

    Checked before it runs: one SELECT, known tables, real columns (with suggestions), a LIMIT
    added if missing, read-only role, 15 s timeout. An identical query is not run twice.

    Returns the artifact_id; every row when the result is ≤50 rows (`"complete": true`),
    otherwise a profile (row count, columns, first rows, statistics). An empty result comes
    with likely causes.
    """
    t0 = time.perf_counter()
    key = call_hash("sql_query", sql)
    reason = loop_guard(runtime, "sql_query", key)
    if reason:
        return refuse(runtime, "sql_query", t0, key, reason)
    if _discovery_only(sql):
        return refuse(runtime, "sql_query", t0, key,
                      "this query reads only sensor_catalog/run_metadata — use explore_schema "
                      "(or the tags in your brief) for schema questions")
    try:
        safe = validate_sql(sql, row_limit=200_000)
        df = run_select(safe)
    except Exception as e:  # noqa: BLE001
        return failed(runtime, "sql_query", t0, key, str(e), sql=sql[:_MAX_QUERY_LOG])
    extra = {}
    if df.empty or (len(df) == 1 and df.isna().all(axis=None)):
        extra["empty_result_hints"] = empty_result_hints(safe) or ["no obvious cause — check filters"]
    return table_result(runtime, "sql_query", t0, key, df, safe, extra,
                        cols=list(df.columns)[:20])


# ── free-form Cypher ─────────────────────────────────────────────────────────────
def graph_empty_hints(cypher: str) -> list[str]:
    hints = []
    aliases = {a.lower(): name for name, meta in SYSTEM_META.items() for a in meta.get("aliases", [])}
    for literal in re.findall(r"name\s*(?::|=)\s*'([^']+)'", cypher):
        if literal not in systems():
            fix = aliases.get(literal.lower())
            hints.append(f"system name {literal!r} does not exist"
                         + (f" — use '{fix}'" if fix else f"; systems are {', '.join(systems())}"))
    return hints


@tool
def graph_query(cypher: str, runtime: ToolRuntime) -> Command:
    """Explore the plant's structure and history: one read-only Cypher query you write.

    The graph knows what the sensors cannot: which tags a system has and their setpoints,
    every alert over ~2 years, every maintenance work order with its costs and downtime, and
    the parts each job consumed. It holds no sensor values. Write the query that returns the
    whole fact and the ids later steps will need, aggregating in Cypher.

    The data
    `(Tag)-[:MEASURED_AT]->(System)` · `(Alert)-[:GENERATED_ON]->(System)` ·
    `(MaintenanceLog)-[:PERFORMED_ON]->(System)` · `(MaintenanceLog)-[:CONSUMED {quantity,
    line_cost}]->(Item)`. `System.name` is 'bfpa', 'bfpb', 'cepa', 'cepb' or 'turbine'.

    Doing it well
    - Latest alert: `ORDER BY a.start_ts DESC, a.alert_id DESC LIMIT 1`; add
      `a.has_telemetry = true` when the alert must have sensor data behind it (for a plot).
    - Dates are zoned datetimes: `a.start_ts >= datetime('2026-09-01T00:00:00Z')`.
    - An alert's work orders: `m.related_alert_id = a.alert_id`; follow-up work on the same
      system: `m.start_ts` from the alert start to a few days after its end — say the rule used.
    - Maintenance totals: no date filter unless the brief gives a window; sum `total_cost`,
      `labor_cost`, `total_item_cost`, `downtime_hours`, and `count(m)`; group by
      `maintenance_class` when the mix matters.
    - Parts: `MATCH (m)-[c:CONSUMED]->(i:Item)` then `sum(c.quantity)`, `sum(c.line_cost)`.
    - Tags that alarm most: `OPTIONAL MATCH (a:Alert)-[:GENERATED_ON]->(s) WHERE a.tag_name =
      t.tag_name` and `count(a)`.
    - Always order results fully (add ids as tie-breakers) so the same query returns the same
      rows in the same order.

    Checked before it runs: write clauses rejected; planned with EXPLAIN, so unknown labels,
    relationships and properties come back with suggestions; a date compared to a plain string
    is rejected (it silently matches nothing). READ session. An identical query is not run twice.

    Returns up to 50 rows inline and stores the full record set under an artifact_id. An
    empty result comes with likely causes.
    """
    t0 = time.perf_counter()
    key = call_hash("graph_query", cypher)
    reason = loop_guard(runtime, "graph_query", key)
    if reason:
        return refuse(runtime, "graph_query", t0, key, reason)
    try:
        safe = validate_cypher(cypher)
        problems = unknown_names(explain(safe))
        if problems:
            raise ValueError("; ".join(problems))
        rows = run_read(safe)
    except Exception as e:  # noqa: BLE001
        return failed(runtime, "graph_query", t0, key, str(e), cypher=cypher[:_MAX_QUERY_LOG])
    summary = {}
    if not rows:
        summary["empty_result_hints"] = graph_empty_hints(safe) or ["no obvious cause — check filters"]
    return records_result(runtime, "graph_query", t0, key, rows, safe, summary)


# ── python ───────────────────────────────────────────────────────────────────────
@tool
def python_analysis(code: str, artifact_ids: list[str], runtime: ToolRuntime) -> Command:
    """Turn fetched data into insight: any analysis and any figures, in Python you write.

    The other specialists fetch; this is where the data gets understood — statistics,
    correlation and regression, clustering operating regions, anomaly and change detection,
    trends, distributions — and where the figures an engineer would want to see are drawn.
    Runs in an isolated sandbox process on the artifacts you pass.

    What you have
    - `df` (the first artifact), `dfs` ({artifact_id: DataFrame}), `pd`, `np`, `plt`.
      Import scipy, sklearn, statistics, math, datetime, json, collections, itertools as needed.
      Parse timestamps with `pd.to_datetime(df['ts'], utc=True)` when they arrive as text;
      pivot long data with `df.pivot_table(index='ts', columns='tag_name', values='value')`.
    - Variables and imports persist across calls in this step: look at the data once, then
      build on it.

    Figures — every figure you draw is kept (saved or left open, up to 8 per call) and comes
    back with its own artifact id. Defaults are already set (12×6 in, 150 dpi, grid, tab10
    colours, readable dates), so spend the effort on making each figure explain itself:
    - a title saying what, where and when; axis labels with units; a legend naming each series;
    - setpoints as labelled horizontal lines (alarm_hi amber, alarm_hihi red); an event window
      shaded with `axvspan`; the peak marked and annotated with its value and time;
    - a distinct colour per tag or system; stacked subplots (`sharex=True`) when units
      differ; scatter with `alpha` for dense data, a fit line and r in the legend; clusters
      coloured with centroids marked;
    - `fig.suptitle(...)` on multi-panel figures — the title becomes the figure's caption.

    Rules code enforces: no filesystem, network, os or sys; randomised sklearn estimators
    need `random_state=0` so results repeat; a hard timeout per call. stdout (≤4,000 chars) is
    all you read back — print labelled results, never whole DataFrames.

    Returns stdout and `figures: [{artifact_id, path, title}]`.
    """
    t0 = time.perf_counter()
    key = call_hash("python_analysis", {"code": code, "ids": sorted(artifact_ids or [])})
    reason = loop_guard(runtime, "python_analysis", key)
    if reason:
        return refuse(runtime, "python_analysis", t0, key, reason)

    frames: dict[str, pd.DataFrame] = {}
    for aid in artifact_ids or []:
        art = store.get(aid)
        if isinstance(art, TableArtifact):
            frames[aid] = art.df
        elif isinstance(art, RecordsArtifact):
            frames[aid] = pd.DataFrame(art.rows)
    if artifact_ids and not frames:
        return failed(runtime, "python_analysis", t0, key,
                      f"no loadable artifacts among {artifact_ids}; available: {store.ids()}")
    try:
        validate_python(code)
    except Exception as e:  # noqa: BLE001
        return failed(runtime, "python_analysis", t0, key, str(e), code=code[:_MAX_QUERY_LOG])

    delegation = ((runtime.config or {}).get("configurable") or {}).get("delegation_id")
    figure_name = f"figure_{len(store.ids()) + 1}.png"
    sandbox, ephemeral = session(delegation)
    try:
        resp = sandbox.run(code, frames, figure_name)
    except SandboxError as e:
        return failed(runtime, "python_analysis", t0, key, str(e), code=code[:_MAX_QUERY_LOG])
    finally:
        if ephemeral:
            sandbox.close()
    stdout = (resp.get("stdout") or "")[:_MAX_STDOUT]
    if not resp.get("ok"):
        return failed(runtime, "python_analysis", t0, key, resp.get("error") or "failed",
                      code=code[:_MAX_QUERY_LOG], stdout=stdout)

    update: dict = {}
    payload: dict = {"stdout": stdout or "(no output — print() your results)"}
    extra: dict = {}
    figures = []
    for drawn in resp.get("figures") or []:
        _FIG_DIR.mkdir(parents=True, exist_ok=True)
        fig = FigureArtifact(png_path="", caption=drawn.get("title") or "analysis figure",
                             n_points=sum(len(f) for f in frames.values()),
                             provenance=Provenance(capability="python_analysis"))
        fig_id = store.put(fig, "f")
        target = _FIG_DIR / f"analysis_{fig_id}.png"
        shutil.copyfile(drawn["path"], target)
        fig.png_path = str(target)
        figures.append({"artifact_id": fig_id, "path": str(target), "title": fig.caption})
    if figures:
        update["blackboard"] = {f["artifact_id"]: _json_safe(store.get(f["artifact_id"]).digest())
                                for f in figures}
        payload["figures"] = figures
        # The first figure's id stays in the event so reuse checks and traces point at it.
        extra = {"artifact_id": figures[0]["artifact_id"], "figure_path": figures[0]["path"],
                 "figures": [f["artifact_id"] for f in figures]}
    update["tool_events"] = [_event("python_analysis", t0, call_hash=key, artifact_ids=artifact_ids,
                                    code=code[:_MAX_QUERY_LOG], stdout_chars=len(stdout), **extra)]
    update["messages"] = [_msg(runtime, payload)]
    return Command(update=update)
