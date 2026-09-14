"""Concept glossary: plain-language measurements resolve to the same catalog tags every time."""
from __future__ import annotations

import pytest

from mas.catalog import glossary, tag_map


@pytest.mark.parametrize("concept, system, primary, n", [
    ("bearing temps", "bfpa", "bearing_temp_1", 14),
    ("load", "bfpa", "motor_power", 1),
    ("load", "turbine", "gross_power", 1),
    ("efficiency", "cepa", "pump_efficiency", 1),
    ("vibration", "turbine", "vibration_overall", 28),
    ("eccentricity", "bfpa", "shaft_eccentricity", 1),
])
def test_concepts_resolve_to_the_same_tags_every_time(concept, system, primary, n):
    r = glossary.resolve(concept, system)
    assert r.primary.tag_name == primary and len(r.tags) == n
    assert glossary.resolve(concept, system) == r


def test_unknown_concepts_resolve_to_nothing_with_suggestions():
    assert glossary.resolve("eccentricity", "cepa").source == "none"
    assert glossary.resolve("running hot", "bfpa").source == "none"
    assert glossary.suggestions("bearing temprature")[0].startswith("bearing temp")


def test_derived_units_are_filled_from_physics():
    m = tag_map("bfpa")
    assert glossary.display_unit(m["pump_head"]) == "m"
    assert glossary.display_unit(m["pump_efficiency"]) == "%"
    assert glossary.display_unit(m["health_index"]) == "index"
    assert glossary.display_unit(m["bearing_temp_1"]) == "degC"
    assert glossary.canonical_unit("°C") == glossary.canonical_unit("degC")


def test_split_concepts():
    assert glossary.split_concepts("load, efficiency and vibration") == ["load", "efficiency", "vibration"]
