#!/usr/bin/env python
"""Generate docs/03-data-dictionary.md from the catalog (mirror of sensor_catalog)."""

from __future__ import annotations

import _bootstrap  # noqa: F401 - side-effect import: puts src/ on sys.path
import pathlib
from datetime import datetime, timezone

from mas import catalog
from mas.catalog import SYSTEM_META

OUT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "03-data-dictionary.md"


def _fmt(v) -> str:
    return "" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))


def main() -> None:
    lines = [
        "# Data Dictionary",
        "",
        f"_Auto-generated from the catalog on {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. "
        "Do not edit by hand — run `make data-dict`._",
        "",
        f"Total: **{len(catalog.all_tags())} tags** across **{len(catalog.systems())} systems**, "
        f"**{len(catalog.items())} spare-part items**.",
        "",
    ]
    for s in catalog.systems():
        meta = SYSTEM_META[s]
        tags = catalog.tags_for(s)
        lines += [
            f"## `{s}` — {meta['display_name']}",
            "",
            f"- KKS: `{meta['kks_code']}` · class: {meta['equipment_class']} / "
            f"{meta['sub_class']} · criticality: {meta['criticality']}",
            f"- {len(tags)} tags · rated {meta['rated_power_kw']:g} kW, "
            f"{meta['rated_speed_rpm']:g} rpm",
            "",
            "| tag_name | family | unit | normal | alarms (lo/lolo·hi/hihi) | description |",
            "|---|---|---|---|---|---|",
        ]
        for t in tags:
            normal = f"{_fmt(t.normal_min)}–{_fmt(t.normal_max)}"
            alarms = (f"{_fmt(t.alarm_lo)}/{_fmt(t.alarm_lolo)} · "
                      f"{_fmt(t.alarm_hi)}/{_fmt(t.alarm_hihi)}")
            lines.append(f"| `{t.tag_name}` | {t.family} | {t.unit} | {normal} | "
                         f"{alarms} | {t.description} |")
        lines.append("")

    # spare items
    lines += ["## Spare-part items", "",
              "| item_code | name | category | unit_cost (INR) | uom |",
              "|---|---|---|---:|---|"]
    for it in catalog.items():
        lines.append(f"| `{it.item_code}` | {it.name} | {it.category} | "
                     f"{it.unit_cost:,.0f} | {it.uom} |")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[data-dict] wrote {OUT} ({len(catalog.all_tags())} tags)")


if __name__ == "__main__":
    main()
