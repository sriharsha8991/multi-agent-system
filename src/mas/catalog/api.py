"""Public catalog interface — the single source of truth queried by every layer.

``sensor_catalog`` (Postgres), the wide-table columns, and the Neo4j ``Tag``
nodes are all projected from :func:`tags_for`. ``System`` node metadata lives in
:data:`SYSTEM_META`.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .items import build_items
from .spec import FAMILIES, ItemSpec, TagSpec
from .systems import EXPECTED_COUNTS, build_all

_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

# ── System (asset) metadata for the graph ────────────────────────────────────
SYSTEM_META: dict[str, dict] = {
    "bfpa": dict(
        name="bfpa", display_name="Boiler Feed Pump A", kks_code="LAC10 AP001",
        equipment_class="centrifugal_pump", sub_class="boiler_feed_pump",
        manufacturer="Sulzer", model="HPTd 260-6", rated_power_kw=9000.0,
        rated_flow_tph=320.0, rated_head_m=2100.0, rated_speed_rpm=5200.0,
        commissioned_date="2016-04-18", criticality="high", location="Feedwater Bay",
        sql_table="bfpa",
        aliases=["BFP-A", "BFP A", "Boiler Feed Pump A", "bfp_a", "bfpa", "pump a", "feed pump a"],
    ),
    "bfpb": dict(
        name="bfpb", display_name="Boiler Feed Pump B", kks_code="LAC20 AP001",
        equipment_class="centrifugal_pump", sub_class="boiler_feed_pump",
        manufacturer="Sulzer", model="HPTd 260-6", rated_power_kw=9000.0,
        rated_flow_tph=320.0, rated_head_m=2100.0, rated_speed_rpm=5200.0,
        commissioned_date="2016-04-18", criticality="high", location="Feedwater Bay",
        sql_table="bfpb",
        aliases=["BFP-B", "BFP B", "Boiler Feed Pump B", "bfp_b", "bfpb", "pump b", "feed pump b"],
    ),
    "cepa": dict(
        name="cepa", display_name="Condensate Extraction Pump A", kks_code="LCB10 AP001",
        equipment_class="centrifugal_pump", sub_class="condensate_extraction_pump",
        manufacturer="Sulzer", model="SJT 46-8", rated_power_kw=900.0,
        rated_flow_tph=300.0, rated_head_m=260.0, rated_speed_rpm=1480.0,
        commissioned_date="2016-03-02", criticality="medium", location="Condenser Bay",
        sql_table="cepa",
        aliases=["CEP-A", "CEP A", "Condensate Extraction Pump A", "cep_a", "cepa", "condensate pump a"],
    ),
    "cepb": dict(
        name="cepb", display_name="Condensate Extraction Pump B", kks_code="LCB20 AP001",
        equipment_class="centrifugal_pump", sub_class="condensate_extraction_pump",
        manufacturer="Sulzer", model="SJT 46-8", rated_power_kw=900.0,
        rated_flow_tph=300.0, rated_head_m=260.0, rated_speed_rpm=1480.0,
        commissioned_date="2016-03-02", criticality="medium", location="Condenser Bay",
        sql_table="cepb",
        aliases=["CEP-B", "CEP B", "Condensate Extraction Pump B", "cep_b", "cepb", "condensate pump b"],
    ),
    "turbine": dict(
        name="turbine", display_name="Steam Turbine", kks_code="MAA10",
        equipment_class="steam_turbine", sub_class="reheat_condensing_turbine",
        manufacturer="BHEL", model="K250-16.7", rated_power_kw=250000.0,
        rated_flow_tph=800.0, rated_head_m=0.0, rated_speed_rpm=3000.0,
        commissioned_date="2016-05-30", criticality="critical", location="TG Deck",
        sql_table="turbine",
        aliases=["Turbine", "Steam Turbine", "STG", "TG", "turbine", "steam turbine unit"],
    ),
}


@lru_cache(maxsize=1)
def _catalog() -> dict[str, list[TagSpec]]:
    return build_all()


@lru_cache(maxsize=1)
def _items() -> list[ItemSpec]:
    return build_items()


def systems() -> tuple[str, ...]:
    return tuple(SYSTEM_META.keys())


def tags_for(system: str) -> list[TagSpec]:
    return _catalog()[system]


def all_tags() -> list[TagSpec]:
    out: list[TagSpec] = []
    for sys in systems():
        out.extend(_catalog()[sys])
    return out


def tag_map(system: str) -> dict[str, TagSpec]:
    return {t.tag_name: t for t in tags_for(system)}


def column_names(system: str) -> list[str]:
    """Ordered Postgres columns for a system's wide table: ts + all tag columns."""
    return ["ts"] + [t.tag_name for t in tags_for(system)]


def tag_count(system: str) -> int:
    return len(tags_for(system))


def search_tags(term: str, system: str | None = None) -> list[TagSpec]:
    """Tags matching a plain-language term, on one system or all.

    Every word of the term must appear (underscores read as spaces), so 'bearing
    temperature' finds `bearing_temp_1` in family `temperature`. Name/family/unit hits win;
    descriptions are only a fallback — a word like 'steam' appears in 60 descriptions and
    would drown the answer.
    """
    words = term.strip().lower().replace("_", " ").split()
    if not words:
        return []
    pool = tags_for(system) if system else all_tags()

    def _hit(text: str) -> bool:
        text = text.lower().replace("_", " ")
        return all(w in text for w in words)

    return ([t for t in pool if _hit(f"{t.tag_name} {t.family} {t.unit}")]
            or [t for t in pool if _hit(t.description)])


def items() -> list[ItemSpec]:
    return _items()


def item_map() -> dict[str, ItemSpec]:
    return {i.item_code: i for i in _items()}


def validate() -> list[str]:
    """Structural catalog checks. Returns a list of problems ([] == OK).

    Covers the catalog side of gates G-02, G-04, G-08 (naming) before any DB
    exists, so failures surface at import / unit-test time.
    """
    problems: list[str] = []
    seen_global: set[tuple[str, str]] = set()

    for sys in systems():
        tags = tags_for(sys)
        n = len(tags)
        if not (100 <= n <= 200):
            problems.append(f"{sys}: tag count {n} outside [100, 200]")
        if n != EXPECTED_COUNTS[sys]:
            problems.append(f"{sys}: tag count {n} != expected {EXPECTED_COUNTS[sys]}")

        names = [t.tag_name for t in tags]
        dupes = {x for x in names if names.count(x) > 1}
        if dupes:
            problems.append(f"{sys}: duplicate tag names {sorted(dupes)}")

        fams = {t.family for t in tags}
        for required in ("pressure", "temperature", "flow", "vibration"):
            if required not in fams:
                problems.append(f"{sys}: missing required family {required!r}")
        for fam in FAMILIES:
            if fam not in fams:
                problems.append(f"{sys}: missing family coverage {fam!r}")

        for t in tags:
            if not _IDENT_RE.match(t.tag_name):
                problems.append(f"{sys}: '{t.tag_name}' not a valid unquoted identifier")
            if t.family not in FAMILIES:
                problems.append(f"{sys}: '{t.tag_name}' has unknown family {t.family!r}")
            if t.normal_min is not None and t.normal_max is not None \
                    and t.normal_min >= t.normal_max:
                problems.append(f"{sys}: '{t.tag_name}' normal_min >= normal_max")
            key = (sys, t.tag_name)
            if key in seen_global:
                problems.append(f"duplicate (system, tag) {key}")
            seen_global.add(key)

    # cross-system comparability: the shared universal core must be identical
    core = ["bearing_temp_1", "vibration_overall", "shaft_speed", "ambient_temp"]
    for name in core:
        units = {}
        for sys in systems():
            tm = tag_map(sys)
            if name not in tm:
                problems.append(f"{sys}: missing universal-core tag {name!r}")
            else:
                units.setdefault(tm[name].unit, []).append(sys)
        if len(units) > 1:
            problems.append(f"universal-core '{name}' has inconsistent units: {units}")

    # items
    try:
        _items()
    except AssertionError as e:
        problems.append(f"items: {e}")

    return problems
