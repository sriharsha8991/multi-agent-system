"""Catalog structural tests (no database required)."""

from __future__ import annotations

from mas import catalog

EXPECTED = {"bfpa": 130, "bfpb": 130, "cepa": 108, "cepb": 108, "turbine": 160}


def test_catalog_validates_clean():
    assert catalog.validate() == []


def test_exact_counts():
    for sys, want in EXPECTED.items():
        assert catalog.tag_count(sys) == want
    assert len(catalog.all_tags()) == sum(EXPECTED.values()) == 636


def test_counts_within_spec_band():
    for sys in catalog.systems():
        assert 100 <= catalog.tag_count(sys) <= 200


def test_family_coverage():
    for sys in catalog.systems():
        fams = {t.family for t in catalog.tags_for(sys)}
        for required in ("pressure", "temperature", "flow", "vibration"):
            assert required in fams, f"{sys} missing {required}"


def test_universal_core_shared_and_comparable():
    core = ["bearing_temp_1", "vibration_overall", "shaft_speed", "ambient_temp"]
    for name in core:
        units = {catalog.tag_map(sys)[name].unit for sys in catalog.systems()}
        assert len(units) == 1, f"{name} has inconsistent units {units}"


def test_no_unit_suffix_in_names():
    # MOD-01: units live in Tag.unit, not the tag name
    for t in catalog.all_tags():
        assert not t.tag_name.endswith(("_c", "_bar", "_mm", "_rpm", "_kw"))


def test_items_categories_and_costs():
    items = catalog.items()
    assert len(items) >= 80
    assert len({i.item_code for i in items}) == len(items)
    assert min(i.unit_cost for i in items) < 2000      # a cheap O-ring
    assert max(i.unit_cost for i in items) > 500000     # a turbine bearing
