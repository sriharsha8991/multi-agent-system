"""Instrument layer — per-tag noise, 1/f drift, ADC quantization, pathologies.

Turns clean physics into realistic transmitter output. Deterministic given the
seed. The pathology budget is kept well under 0.15% of samples (gate G-21) and
never touches an event's primary tag, so demo guarantees are unaffected.
"""

from __future__ import annotations

import numpy as np

from .. import catalog
from . import dsp
from .events import EVENTS
from .modes import GenContext


def _protected_tags(system: str) -> set[str]:
    prot: set[str] = set()
    for e in EVENTS:
        if e.system == system:
            prot.add(e.primary_tag)
            prot.update(d.tag for d in e.degradations)
            if e.freeze:
                prot.add(e.freeze[0])
    return prot


def apply(system: str, arrays: dict[str, np.ndarray], ctx: GenContext) -> None:
    n = ctx.grid.n
    settings = ctx.settings
    tmap = catalog.tag_map(system)

    for name, spec in tmap.items():
        arr = arrays[name]
        if spec.family == "status":
            arrays[name] = np.round(np.clip(arr, 0.0, 1.0))
            continue

        rng = settings.rng(system, name, "instr")
        if spec.noise_sigma and spec.noise_sigma > 0:
            arr = arr + rng.normal(0.0, spec.noise_sigma, n)
            if not spec.is_derived:
                arr = arr + dsp.one_over_f(rng, n, spec.noise_sigma * 0.3)

        if spec.precision and spec.precision > 0:
            arr = np.round(arr / spec.precision) * spec.precision

        # physical floor for inherently non-negative quantities
        if spec.normal_min is not None and spec.normal_min >= 0 and spec.unit != "":
            if spec.driver not in ("expansion",):
                arr = np.maximum(arr, 0.0)

        arrays[name] = arr

    _inject_pathologies(system, arrays, ctx)


def _inject_pathologies(system: str, arrays: dict[str, np.ndarray],
                        ctx: GenContext) -> None:
    """A tiny, deterministic budget of spikes and NULL dropouts."""
    n = ctx.grid.n
    rng = ctx.settings.rng(system, "pathologies")
    protected = _protected_tags(system)
    candidates = [t.tag_name for t in catalog.tags_for(system)
                  if t.family not in ("status",) and t.tag_name not in protected
                  and not t.is_derived]
    if not candidates:
        return

    # a few single-sample spikes
    for name in rng.choice(candidates, size=min(6, len(candidates)), replace=False):
        spec = catalog.tag_map(system)[name]
        k = int(rng.integers(1, 4))
        idx = rng.integers(0, n, size=k)
        span = max(spec.normal_max - spec.normal_min, spec.precision * 10, 1.0)
        arrays[name][idx] = arrays[name][idx] + rng.choice([-1.0, 1.0]) * span * 0.8

    # a couple of brief NULL dropouts (stuck/dead transmitter comms)
    for name in rng.choice(candidates, size=min(4, len(candidates)), replace=False):
        start = int(rng.integers(0, n - 30))
        length = int(rng.integers(3, 15))
        arrays[name][start:start + length] = np.nan
