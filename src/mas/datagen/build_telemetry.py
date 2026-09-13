"""Orchestrate the generator stages and COPY the telemetry into Postgres.

Per system:  physics → events (degradation) → instrument (noise) → freeze.
The final in-memory arrays are exactly what lands in the DB, so the alert
detector and validators run against them without a round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

import numpy as np

from .. import catalog
from ..config import Settings, get_settings
from . import events as ev
from . import instrument, physics
from .modes import GenContext, build_context

GENERATOR_VERSION = "1.0.0"


@dataclass(slots=True)
class GeneratedData:
    ctx: GenContext
    arrays: dict[str, dict[str, np.ndarray]]     # system -> tag -> values
    records: dict[str, list[ev.EventRecord]]     # system -> event records
    timestamps: np.ndarray                        # datetime64[s], shared axis

    def load_proxy(self, system: str) -> np.ndarray:
        return self.ctx.system_load(system)


def generate_system(system: str, ctx: GenContext) -> tuple[dict[str, np.ndarray],
                                                           list[ev.EventRecord]]:
    arrays = physics.generate(system, ctx)
    arrays.pop("__load__", None)
    records = ev.apply_degradations(system, arrays, ctx)
    instrument.apply(system, arrays, ctx)
    ev.apply_frozen(system, arrays, records, ctx)
    return arrays, records


def generate_all(settings: Settings | None = None) -> GeneratedData:
    settings = settings or get_settings()
    ctx = build_context(settings)
    arrays: dict[str, dict[str, np.ndarray]] = {}
    records: dict[str, list[ev.EventRecord]] = {}
    for system in catalog.systems():
        a, r = generate_system(system, ctx)
        arrays[system] = a
        records[system] = r
    return GeneratedData(ctx=ctx, arrays=arrays, records=records,
                         timestamps=ctx.grid.axis)


def _py_timestamps(axis: np.ndarray) -> list:
    return [ts.astype("datetime64[s]").astype("O").replace(tzinfo=timezone.utc)
            for ts in axis]


def _rows(system: str, arrays: dict[str, np.ndarray], ts: list):
    cols = [t.tag_name for t in catalog.tags_for(system)]
    series = [arrays[c] for c in cols]
    n = len(ts)
    for i in range(n):
        row = [ts[i]]
        for s in series:
            v = s[i]
            row.append(None if v != v else float(v))  # NaN -> SQL NULL
        yield row


def load_to_postgres(data: GeneratedData, settings: Settings | None = None) -> dict[str, int]:
    """COPY every system's telemetry into its wide table. Returns row counts."""
    from ..db import ddl
    from ..db import postgres as pg

    settings = settings or get_settings()
    ts = _py_timestamps(data.timestamps)
    counts: dict[str, int] = {}
    with pg.connect(settings) as conn:
        ddl.write_run_metadata(conn, settings.run_metadata(GENERATOR_VERSION))
        ddl.populate_sensor_catalog(conn)
        for system in catalog.systems():
            cols = catalog.column_names(system)
            pg.execute(conn, f'TRUNCATE "{system}"')
            counts[system] = pg.copy_rows(conn, system, cols,
                                          _rows(system, data.arrays[system], ts))
    return counts
