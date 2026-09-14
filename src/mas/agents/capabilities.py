"""Capability registry — what each specialist owns, declared once (doc 10, O4).

Routing knowledge is enforced by code and described in the orchestrator system prompt.
Each agent declares the slot kinds and aggregations it can fill, how time applies to it,
and what inputs or system specifications it requires.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    agent: str
    summary: str
    slot_kinds: frozenset[str]
    aggregations: frozenset[str]
    clamp_time: bool            # clamp windows to telemetry coverage (history agents don't)
    links_tags: bool            # resolve slot concepts to catalog tags in the brief
    needs_inputs: bool          # must receive artifact ids from prior step dependencies
    needs_systems: bool         # slots must name systems (or tags)


REGISTRY: dict[str, Capability] = {
    "graph_agent": Capability(
        agent="graph_agent",
        summary="Neo4j Metadata & History: Tag/sensor catalog metadata & setpoints, alert history, "
                "maintenance work orders, spare parts consumption & costs. "
                "NARROWS the data for later steps: which tags matter for a symptom (alarm "
                "history, family, setpoints), the alert and its window — handed over as "
                "$sN.tags / $sN.alert_id. "
                "STRICT BOUNDARY: Does NOT have sensor telemetry or time-series values.",
        slot_kinds=frozenset({"lookup"}),
        aggregations=frozenset({"value", "count", "sum", "latest", "list", "rank"}),
        clamp_time=False, links_tags=False, needs_inputs=False, needs_systems=False,
    ),
    "sql_agent": Capability(
        agent="sql_agent",
        summary="PostgreSQL Telemetry Analyst: Raw minute-by-minute sensor values & time-series — "
                "per-tag min/max/avg/stddev stats, extreme timestamps, time above threshold, "
                "system comparisons, and bucketed series for plotting. "
                "REQUIRES: Must specify systems or tags for the slot.",
        slot_kinds=frozenset({"measure"}),
        aggregations=frozenset({"value", "max", "min", "avg", "sum", "count", "stddev", "latest",
                                "series", "duration_above", "compare"}),
        clamp_time=True, links_tags=True, needs_inputs=False, needs_systems=True,
    ),
    "coder_agent": Capability(
        agent="coder_agent",
        summary="Python Data Science Sandbox: Advanced analytics (correlation, regression, clustering, "
                "anomaly detection, trend/distribution analysis) and custom figures/plots on data ALREADY fetched. "
                "REQUIRES: Step must depend on sql_agent or graph_agent to receive input artifacts. Cannot query databases directly.",
        slot_kinds=frozenset({"derive"}),
        aggregations=frozenset({"value", "correlation", "regression", "cluster", "anomaly",
                                "trend", "distribution", "compare", "stddev", "figure",
                                "analysis"}),
        clamp_time=True, links_tags=True, needs_inputs=True, needs_systems=False,
    ),
}

#: Strict 1-to-1 mapping from slot kind to the sole specialist agent permitted to execute it.
KIND_AGENT = {"lookup": "graph_agent", "measure": "sql_agent", "derive": "coder_agent"}


def get_agent_for_kind(kind: str) -> str:
    """Return the agent name responsible for a given slot kind."""
    if kind not in KIND_AGENT:
        raise ValueError(f"Unknown slot kind {kind!r}. Expected one of {set(KIND_AGENT.keys())}")
    return KIND_AGENT[kind]


def capability(agent: str) -> Capability:
    return REGISTRY[agent]


def can_fill(agent: str, kind: str, aggregation: str) -> list[str]:
    """Reasons ``agent`` cannot fill a slot of this kind/aggregation ([] == it can)."""
    cap = REGISTRY.get(agent)
    if not cap:
        return [f"Unknown agent '{agent}'"]
    problems = []
    if kind not in cap.slot_kinds:
        expected_agent = KIND_AGENT.get(kind, "another agent")
        problems.append(f"{agent} does not fill {kind} slots (that is {expected_agent})")
    if aggregation not in cap.aggregations:
        problems.append(f"{agent} does not do '{aggregation}' "
                        f"(it does: {', '.join(sorted(cap.aggregations))})")
    return problems


def render_team() -> str:
    """Render a structured, clear team description for the supervisor prompt to prevent misrouting."""
    lines = [
        "### Specialist Routing Rules (Strict 1-to-1 Mapping)",
        "- **lookup** slots -> ONLY **graph_agent** (Neo4j: metadata, alerts, work orders, spare parts)",
        "- **measure** slots -> ONLY **sql_agent** (PostgreSQL: sensor time-series values & telemetry stats)",
        "- **derive** slots -> ONLY **coder_agent** (Python: stats, plots, figures on fetched artifacts)",
        "",
        "### Data flow",
        "graph_agent narrows (which tags, which alert window) -> sql_agent retrieves exactly that "
        "data -> coder_agent analyses it and draws the figures. Skip a stage the question does "
        "not need.",
        "",
        "### Team Capabilities & Operational Constraints"
    ]
    for cap in REGISTRY.values():
        reqs = []
        if cap.needs_systems:
            reqs.append("requires `systems` or `tags`")
        if cap.needs_inputs:
            reqs.append("requires `depends_on` (input artifacts from prior step)")
        req_str = f" [{'; '.join(reqs)}]" if reqs else ""

        lines.append(
            f"- **{cap.agent}** — {cap.summary}\n"
            f"  * Slot Kind: `{list(cap.slot_kinds)[0]}`{req_str}\n"
            f"  * Supported Aggregations: `{', '.join(sorted(cap.aggregations))}`"
        )
    return "\n".join(lines)

