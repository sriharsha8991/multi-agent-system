"""Typed catalog records — the in-code source of truth.

``TagSpec`` and ``ItemSpec`` are the objects from which both databases are
projected: the Postgres ``sensor_catalog`` row, the Postgres wide-table column,
and the Neo4j ``Tag`` node are all built from the same ``TagSpec`` at seed time,
so they cannot disagree (this is what gate G-08 / G-15 verify).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

# The ten sensor families. Every table must carry >=1 tag in each of the first
# four (the spec's "pressure / temperature / flow / vibration"); G-04 enforces
# coverage across all ten.
FAMILIES: tuple[str, ...] = (
    "pressure",
    "temperature",
    "flow",
    "vibration",
    "speed",
    "level",
    "electrical",
    "chemistry",
    "derived",
    "status",
)


@dataclass(slots=True)
class TagSpec:
    """One sensor / measurement channel."""

    tag_name: str
    system: str
    family: str
    unit: str
    description: str
    driver: str
    driver_params: dict[str, Any] = field(default_factory=dict)
    kks_tag: str = ""
    location: str = ""
    sensor_type: str = ""
    precision: float = 0.1
    noise_sigma: float = 0.1
    normal_min: float = 0.0
    normal_max: float = 100.0
    alarm_lolo: float | None = None
    alarm_lo: float | None = None
    alarm_hi: float | None = None
    alarm_hihi: float | None = None
    is_derived: bool = False

    # Postgres/Neo4j bridge — the tag name IS the column name (MOD-01/§6.3).
    @property
    def sql_column(self) -> str:
        return self.tag_name

    def catalog_row(self) -> dict[str, Any]:
        """Row for the Postgres ``sensor_catalog`` table."""
        return {
            "system": self.system,
            "tag_name": self.tag_name,
            "family": self.family,
            "unit": self.unit,
            "description": self.description,
            "kks_tag": self.kks_tag,
            "location": self.location,
            "sensor_type": self.sensor_type,
            "precision": self.precision,
            "normal_min": self.normal_min,
            "normal_max": self.normal_max,
            "alarm_lolo": self.alarm_lolo,
            "alarm_lo": self.alarm_lo,
            "alarm_hi": self.alarm_hi,
            "alarm_hihi": self.alarm_hihi,
            "is_derived": self.is_derived,
        }

    def tag_node(self, sampling_interval_s: int) -> dict[str, Any]:
        """Property map for the Neo4j ``Tag`` node.

        Deliberately excludes any time-series: only identity, unit, description,
        static alarm setpoints and design ranges (Data Separation Rule / G-07).
        """
        return {
            "tag_name": self.tag_name,
            "system": self.system,
            "family": self.family,
            "unit": self.unit,
            "description": self.description,
            "kks_tag": self.kks_tag,
            "location": self.location,
            "sensor_type": self.sensor_type,
            "precision": self.precision,
            "normal_min": self.normal_min,
            "normal_max": self.normal_max,
            "alarm_lolo": self.alarm_lolo,
            "alarm_lo": self.alarm_lo,
            "alarm_hi": self.alarm_hi,
            "alarm_hihi": self.alarm_hihi,
            "sampling_interval_s": sampling_interval_s,
            "is_derived": self.is_derived,
            "sql_table": self.system,
            "sql_column": self.tag_name,
        }


@dataclass(slots=True)
class ItemSpec:
    """A spare part or consumable used during maintenance."""

    item_code: str
    name: str
    category: str
    description: str
    unit_cost: float  # in the configured currency (INR)
    uom: str = "each"
    manufacturer: str = ""
    part_number: str = ""
    stock_qty: int = 0
    reorder_level: int = 0
    lead_time_days: int = 0

    def item_node(self, currency: str) -> dict[str, Any]:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["currency"] = currency
        return d
