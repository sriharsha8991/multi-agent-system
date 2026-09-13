"""Blackboard artifacts (L2).

Every subagent returns one of these; every downstream step reads it by handle. The
payload (a DataFrame, PNG bytes) lives here and is *never* serialized into a prompt —
only ``.digest()`` may reach the model (doc 07 §2). Digests are code-owned and
deterministic (``harness.digests``).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..harness.digests import profile_table
from ..llm.schemas import Provenance


@dataclass
class ScalarArtifact:
    value: float | int | str
    unit: str | None = None
    provenance: Provenance | None = None

    def digest(self) -> dict:
        return {"kind": "scalar", "value": self.value, "unit": self.unit}


@dataclass
class RecordsArtifact:
    """Small structured results (graph records). Inlined whole — kept bounded."""

    rows: list[dict]
    provenance: Provenance | None = None

    def digest(self) -> dict:
        return {"kind": "records", "count": len(self.rows), "rows": self.rows[:5]}


@dataclass
class TableArtifact:
    """A telemetry window. The DataFrame is the payload; only its profile is a digest."""

    df: pd.DataFrame
    provenance: Provenance | None = None

    def digest(self) -> dict:
        return profile_table(self.df)


@dataclass
class FigureArtifact:
    png_path: str
    caption: str
    n_points: int = 0
    provenance: Provenance | None = None

    def digest(self) -> dict:
        return {
            "kind": "figure",
            "caption": self.caption,
            "path": self.png_path,
            "n_points": self.n_points,
        }


Artifact = ScalarArtifact | RecordsArtifact | TableArtifact | FigureArtifact
