"""Concept glossary — plain-language measurements resolved to catalog tags, in code.

Users say "load", "efficiency" or "bearing temps"; the catalog says ``motor_power``,
``pump_efficiency``, ``bearing_temp_1..8``. Letting each agent guess that mapping made the
same clustering question use five features on one run and four on the next (doc 10, O2).
Here the mapping is fixed once:

* ``resolve(concept, system)`` → every matching tag plus one **primary** tag, deterministic;
* ``display_unit(tag)`` → the unit to report. Derived tags carry an empty unit in the
  seeded catalog; the physics code gives ``pump_head`` metres, ``hydraulic_power`` kW and
  ``pump_efficiency`` %, and every other derived tag is a synthetic 0–100 band ("index").

Resolution order: glossary concept (name or synonym) → all-words catalog search → nothing.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .api import search_tags, tags_for
from .spec import TagSpec

PUMPS = ("bfpa", "bfpb", "cepa", "cepb")

#: Units the seeded catalog leaves empty, taken from ``datagen.physics`` handlers.
UNIT_OVERRIDES = {"pump_head": "m", "hydraulic_power": "kW", "pump_efficiency": "%"}


@dataclass(frozen=True)
class Concept:
    name: str
    synonyms: tuple[str, ...] = ()
    family: str | None = None
    name_all: tuple[str, ...] = ()     # every word must appear in the tag name
    exclude: tuple[str, ...] = ()      # none of these may appear in the tag name
    tags: dict[str, tuple[str, ...]] = field(default_factory=dict)  # explicit, by system class
    primary: dict[str, str] = field(default_factory=dict)           # by system class
    derived: bool = False              # allow derived tags (KPIs)


def _cls(system: str) -> str:
    return "pump" if system in PUMPS else system


CONCEPTS: tuple[Concept, ...] = (
    Concept("bearing temperature", ("bearing temp", "bearing temps", "bearing temperatures"),
            family="temperature", name_all=("bearing",), exclude=("margin",),
            primary={"pump": "bearing_temp_1", "turbine": "bearing_temp_1"}),
    Concept("winding temperature", ("winding temp", "stator temperature", "motor temperature"),
            family="temperature", name_all=("winding",),
            primary={"pump": "winding_temp_1", "turbine": "stator_winding_temp_1"}),
    Concept("lube oil temperature", ("oil temperature", "lube oil temp"), family="temperature",
            name_all=("lube", "oil")),
    Concept("temperature", ("temp", "temps", "temperatures"), family="temperature"),
    Concept("vibration", ("vib", "overall vibration", "vibrations"), family="vibration",
            primary={"pump": "vibration_overall", "turbine": "vibration_overall"}),
    Concept("bearing vibration", ("bearing vib",), family="vibration", name_all=("bearing",)),
    Concept("eccentricity", ("shaft eccentricity",),
            tags={"pump": ("shaft_eccentricity",), "turbine": ("eccentricity",)},
            primary={"pump": "shaft_eccentricity", "turbine": "eccentricity"}),
    Concept("load", ("loading", "operating load"),
            tags={"pump": ("motor_power",), "turbine": ("gross_power",)},
            primary={"pump": "motor_power", "turbine": "gross_power"}),
    Concept("power", ("active power", "motor power", "gross power", "power output", "output"),
            tags={"pump": ("motor_power",), "turbine": ("gross_power",)},
            primary={"pump": "motor_power", "turbine": "gross_power"}),
    Concept("efficiency", ("pump efficiency", "cycle efficiency"),
            tags={"pump": ("pump_efficiency",), "turbine": ("cycle_efficiency",)},
            primary={"pump": "pump_efficiency", "turbine": "cycle_efficiency"}, derived=True),
    Concept("flow", ("flow rate", "flowrate"),
            tags={"pump": ("flow_rate",), "turbine": ("main_steam_flow",)},
            primary={"pump": "flow_rate", "turbine": "main_steam_flow"}),
    Concept("head", ("pump head",), tags={"pump": ("pump_head",)},
            primary={"pump": "pump_head"}, derived=True),
    Concept("discharge pressure", (), family="pressure", name_all=("discharge", "pressure"),
            primary={"pump": "discharge_pressure"}),
    Concept("suction pressure", (), family="pressure", name_all=("suction", "pressure"),
            primary={"pump": "suction_pressure"}),
    Concept("pressure", ("pressures",), family="pressure"),
    Concept("motor current", ("current", "amps"),
            tags={"pump": ("motor_current", "motor_current_phase_1", "motor_current_phase_2",
                           "motor_current_phase_3"),
                  "turbine": ("stator_current_1", "stator_current_2", "stator_current_3")},
            primary={"pump": "motor_current", "turbine": "stator_current_1"}),
    Concept("speed", ("shaft speed", "rpm"), family="speed",
            primary={"pump": "shaft_speed", "turbine": "shaft_speed"}),
    Concept("condenser vacuum", ("vacuum",), tags={"pump": ("condenser_vacuum",),
                                                    "turbine": ("condenser_vacuum",)},
            primary={"pump": "condenser_vacuum", "turbine": "condenser_vacuum"}),
    Concept("health index", ("health",), tags={"pump": ("health_index",)},
            primary={"pump": "health_index"}, derived=True),
    Concept("cavitation", ("cavitation index",), tags={"pump": ("cavitation_index",)},
            primary={"pump": "cavitation_index"}, derived=True),
    Concept("heat rate", (), tags={"turbine": ("heat_rate",)}, primary={"turbine": "heat_rate"},
            derived=True),
)

_BY_KEY = {k: c for c in CONCEPTS for k in (c.name, *c.synonyms)}


@dataclass(frozen=True)
class Resolution:
    concept: str | None          # glossary concept name; None when matched by search
    system: str
    tags: tuple[TagSpec, ...]    # all matching tags, catalog order
    primary: TagSpec | None
    source: str                  # "glossary" | "search" | "none"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().replace("_", " ").replace("-", " "))


def split_concepts(text: str) -> list[str]:
    """'load, efficiency and vibration' → ['load', 'efficiency', 'vibration']."""
    parts = re.split(r",|;|/|&|\band\b|\bplus\b", normalize(text))
    return [p.strip() for p in parts if p.strip()]


def _matches(concept: Concept, system: str) -> list[TagSpec]:
    pool = tags_for(system)
    explicit = concept.tags.get(_cls(system))
    if explicit is not None:
        by_name = {t.tag_name: t for t in pool}
        return [by_name[n] for n in explicit if n in by_name]
    if concept.tags and not concept.family:
        return []  # explicit-only concept with nothing for this system class
    out = []
    for t in pool:
        name = t.tag_name.replace("_", " ")
        if concept.family and t.family != concept.family:
            continue
        if not all(w in name for w in concept.name_all):
            continue
        if any(w in name for w in concept.exclude):
            continue
        if t.is_derived and not concept.derived:
            continue
        out.append(t)
    return out


def resolve(concept: str, system: str) -> Resolution:
    key = normalize(concept)
    c = _BY_KEY.get(key)
    if c is not None:
        tags = _matches(c, system)
        primary_name = c.primary.get(_cls(system))
        primary = next((t for t in tags if t.tag_name == primary_name), tags[0] if tags else None)
        return Resolution(c.name, system, tuple(tags), primary, "glossary" if tags else "none")
    found = [t for t in search_tags(key, system)]
    physical = [t for t in found if not t.is_derived] or found
    return Resolution(None, system, tuple(physical), physical[0] if physical else None,
                      "search" if physical else "none")


def suggestions(concept: str, n: int = 5) -> list[str]:
    return difflib.get_close_matches(normalize(concept), list(_BY_KEY), n=n, cutoff=0.4)


def concept_names() -> list[str]:
    return [c.name for c in CONCEPTS]


def display_unit(tag: TagSpec) -> str:
    if tag.unit:
        return tag.unit
    if tag.tag_name in UNIT_OVERRIDES:
        return UNIT_OVERRIDES[tag.tag_name]
    return "index" if tag.is_derived else ""


# ── unit families, for checking what agents report against what the catalog says ──
_UNIT_ALIASES = {
    "degc": "degC", "°c": "degC", "c": "degC", "deg c": "degC", "celsius": "degC",
    "um": "um", "µm": "um", "μm": "um", "micron": "um", "microns": "um",
    "mm/s": "mm/s", "bar": "bar", "barg": "barg", "mbara": "mbara", "mbar": "mbar",
    "kw": "kW", "mw": "MW", "t/h": "t/h", "tph": "t/h", "m3/h": "m3/h", "m³/h": "m3/h",
    "%": "%", "percent": "%", "a": "A", "amps": "A", "rpm": "rpm", "h": "h", "hours": "h",
    "hour": "h", "hrs": "h", "min": "min", "minutes": "min", "minute": "min", "inr": "INR",
    "₹": "INR", "m": "m", "index": "index", "kj/kwh": "kJ/kWh", "kg/kwh": "kg/kWh",
}


def canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    u = unit.strip()
    return _UNIT_ALIASES.get(u.lower(), u) if u else None
