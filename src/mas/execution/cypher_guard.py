"""Cypher validator (L3) — reject write clauses and known traps before execution.

There is no mature Cypher AST parser in Python, so the community-standard pattern applies:
a clause/procedure denylist here, plus a **read-access session** at execution
(``cypher_exec``) as the hard driver-level gate — belt and suspenders (doc 06 §4.2).

Two semantic checks sit beside the denylist (doc 10, S2):

* ``check_datetime_compare`` — comparing a zoned-datetime property to a string literal is
  not an error in Neo4j; it evaluates to null and silently matches nothing. ``EXPLAIN``
  does not warn about it either (verified), so it is caught here.
* ``unknown_names`` turns the server's ``EXPLAIN`` notifications (unknown label, property
  or relationship type) into a validation error with suggestions from the graph vocabulary.
"""
from __future__ import annotations

import difflib
import re

_WRITE_CLAUSE = re.compile(
    r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|DETACH|FOREACH|LOAD\s+CSV)\b", re.IGNORECASE
)
_WRITE_PROC = re.compile(
    r"\b(apoc\.(create|merge|refactor|periodic|trigger)|db\.create|db\.index\.\w+\.(create|drop))",
    re.IGNORECASE,
)

_TEMPORAL_PROPS = r"(start_ts|end_ts|acknowledged_ts|commissioned_date)"
_STRING_COMPARE = re.compile(
    rf"\.\s*{_TEMPORAL_PROPS}\s*(<=|>=|<>|=|<|>)\s*'([^']*)'"
    rf"|'([^']*)'\s*(<=|>=|<>|=|<|>)\s*\w+\s*\.\s*{_TEMPORAL_PROPS}",
    re.IGNORECASE,
)

#: The graph's vocabulary (``datagen.graph_seed``), for "did you mean" suggestions.
LABELS = ("System", "Tag", "Alert", "MaintenanceLog", "Item")
RELATIONSHIPS = ("MEASURED_AT", "GENERATED_ON", "PERFORMED_ON", "CONSUMED")
PROPERTIES = (
    "name", "display_name", "aliases", "equipment_class", "sub_class", "criticality",
    "manufacturer", "model", "rated_power_kw", "rated_flow_tph", "rated_head_m",
    "rated_speed_rpm", "commissioned_date", "location", "sql_table", "tag_count", "kks_code",
    "system", "tag_name", "family", "unit", "description", "kks_tag", "sensor_type",
    "precision", "normal_min", "normal_max", "alarm_lolo", "alarm_lo", "alarm_hi", "alarm_hihi",
    "sampling_interval_s", "is_derived", "sql_column", "alert_id", "alert_type", "severity",
    "priority", "message", "threshold_value", "peak_value", "start_ts", "end_ts",
    "duration_min", "status", "acknowledged_by", "acknowledged_ts", "has_telemetry",
    "alert_level", "work_order_id", "maintenance_type", "maintenance_class", "failure_mode",
    "detection_method", "downtime_hours", "labor_hours", "labor_cost", "total_item_cost",
    "total_cost", "currency", "technician", "related_alert_id", "item_code", "category",
    "part_number", "unit_cost", "uom", "stock_qty", "reorder_level", "lead_time_days",
    "quantity", "unit_cost_at_time", "line_cost",
)

_NOTIFICATION_KIND = {
    "UnknownLabelWarning": ("label", LABELS),
    "UnknownRelationshipTypeWarning": ("relationship type", RELATIONSHIPS),
    "UnknownPropertyKeyWarning": ("property", PROPERTIES),
}


class CypherValidationError(ValueError):
    """Raised when generated Cypher contains a write clause/procedure or a known trap."""


def validate_cypher(cypher: str) -> str:
    """Return the Cypher unchanged if read-only and free of known traps; raise otherwise."""
    if _WRITE_CLAUSE.search(cypher):
        raise CypherValidationError("write clause detected (CREATE/MERGE/DELETE/SET/...)")
    if _WRITE_PROC.search(cypher):
        raise CypherValidationError("write procedure detected")
    check_datetime_compare(cypher)
    return cypher


def check_datetime_compare(cypher: str) -> None:
    m = _STRING_COMPARE.search(cypher)
    if m:
        literal = m.group(3) if m.group(3) is not None else m.group(4)
        raise CypherValidationError(
            f"'{m.group(0).strip()}' compares a zoned datetime to a string, which matches "
            f"nothing without an error — write datetime('{literal}') instead")


def unknown_names(notifications: list[dict]) -> list[str]:
    """Problems from EXPLAIN notifications, with suggestions from the graph vocabulary."""
    problems = []
    for n in notifications:
        code = str(n.get("code") or "")
        kind = next((k for k in _NOTIFICATION_KIND if code.endswith(k)), None)
        if kind is None:
            continue
        what, vocab = _NOTIFICATION_KIND[kind]
        m = re.search(r"is:\s*([A-Za-z_][\w]*)\)", str(n.get("description") or ""))
        name = m.group(1) if m else "?"
        near = difflib.get_close_matches(name, vocab, n=3)
        problems.append(f"unknown {what} {name!r}" + (f" — did you mean {', '.join(near)}?" if near else ""))
    return problems
