"""Central configuration and reproducibility primitives.

Everything time- or randomness-related in the data layer flows through this module:

* ``NOW_ANCHOR`` — the single frozen "now" that defines the telemetry window and
  against which all temporal reasoning ("yesterday", "last 7 days") resolves.
  Pinned by default so ``make seed`` is byte-identical; set ``NOW_ANCHOR=live``
  for a fresh wall-clock window.
* ``MASTER_SEED`` — the one integer every RNG derives from, via
  :meth:`Settings.rng`, keyed by ``(system, tag_name, ...)`` so adding a tag can
  never perturb an existing tag's values.

The resolved anchor/seed/window are persisted to ``run_metadata`` at seed time and
read back by the validators (and, later, the agents), so nothing ever calls
``now()`` twice.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from functools import cached_property, lru_cache
from pathlib import Path

import numpy as np
from pydantic_settings import BaseSettings, SettingsConfigDict


def _stable_hash(keys: tuple[object, ...]) -> int:
    """Process-independent hash of a key tuple (Python's ``hash`` is salted)."""
    joined = "\x1f".join(str(k) for k in keys).encode("utf-8")
    digest = hashlib.sha256(joined).digest()[:8]
    return int.from_bytes(digest, "big")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── reproducibility ──────────────────────────────────────────────────
    master_seed: int = 20260907
    now_anchor: str = "2026-09-07T00:00:00+00:00"  # or "live"

    # ── generation shape ─────────────────────────────────────────────────
    sample_seconds: int = 60
    window_days: int = 30
    maintenance_history_months: int = 24
    currency: str = "INR"

    # ── postgres ─────────────────────────────────────────────────────────
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_db: str = "mas"
    pg_user: str = "mas"
    pg_password: str = "mas_pw"
    pg_reader_user: str = "mas_reader"
    pg_reader_password: str = "mas_reader_pw"

    # ── neo4j ────────────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "mas_neo4j_pw"
    neo4j_database: str = "neo4j"

    # ── llm (gemini) ─────────────────────────────────────────────────────
    # Gemini 3.x is the current generation (2.5 is prior-gen; 2.0 is shut down).
    # Google recommends gemini-3.8-flash for autonomous agents, and Flash-tier now
    # rivals prior Pro tiers (doc 08 §9) — so the reasoning role uses it, not a Pro.
    # Role-based, all configurable via .env; verify with client.models.list().
    gemini_api_key: str = ""
    gemini_reasoning_model: str = "gemini-3.7-flash"    # supervisor, query generation
    gemini_fast_model: str = "gemini-3.7-flash"         # synthesizer, intake, self-reflection
    gemini_lite_model: str = "gemini-3.7-flash"    # high-volume, eval-judge
    llm_seed: int = 7  # pinned with temperature=0 for reproducibility (doc 08 §7)
    # Sampling is an experiment knob (doc 10, O8), not a settled choice: Gemini 3 guidance
    # is to keep the default temperature 1.0, while this system has run at 0. Compare the
    # two on fact pass^k before changing the default. Empty/None → provider default.
    gemini_temperature: float | None = 0.0
    gemini_seed: int | None = None
    specialist_thinking_budget: int | None = None

    # ── python sandbox (doc 10, S4) ──────────────────────────────────────
    # "subprocess": a separate interpreter per delegation with a hard timeout (default,
    # works everywhere). "docker": the same worker inside a no-network, read-only container
    # built from docker/py-sandbox.Dockerfile — the real isolation boundary.
    py_sandbox_backend: str = "subprocess"
    py_sandbox_timeout_s: int = 60
    py_sandbox_image: str = "mas-py-sandbox:latest"
    py_sandbox_memory: str = "1g"

    # ── derived: time ────────────────────────────────────────────────────
    @cached_property
    def anchor(self) -> datetime:
        """The resolved 'now', tz-aware UTC, truncated to the minute."""
        if self.now_anchor.strip().lower() == "live":
            dt = datetime.now(timezone.utc)
        else:
            dt = datetime.fromisoformat(self.now_anchor)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
        return dt.replace(second=0, microsecond=0)

    @property
    def window_start(self) -> datetime:
        return self.anchor - timedelta(days=self.window_days)

    @property
    def window_end(self) -> datetime:
        return self.anchor

    @property
    def n_steps(self) -> int:
        """Number of telemetry rows per table over the window."""
        return (self.window_days * 86400) // self.sample_seconds

    def time_axis(self) -> np.ndarray:
        """The full timestamp axis as numpy datetime64[s], length ``n_steps``.

        Runs ``[window_start, anchor)`` at ``sample_seconds`` cadence — i.e. the
        last row is one interval before the anchor, so MAX(ts) == anchor - step.
        Gate G-03's exact bounds are asserted against this axis.
        """
        start = np.datetime64(self.window_start.replace(tzinfo=None), "s")
        step = np.timedelta64(self.sample_seconds, "s")
        return start + np.arange(self.n_steps) * step

    # ── derived: randomness ──────────────────────────────────────────────
    def rng(self, *keys: object) -> np.random.Generator:
        """A deterministic ``Generator`` for a named stream.

        Derived as ``SeedSequence(master_seed, spawn_key=hash(keys))`` so each
        ``(system, tag_name)`` (or any key tuple) owns an independent, stable
        stream. Adding a new key never shifts an existing one.
        """
        # Fold the string keys into a stable non-negative int entropy value.
        key_hash = _stable_hash(("mas",) + keys)
        seq = np.random.SeedSequence([self.master_seed, key_hash])
        return np.random.default_rng(seq)

    # ── derived: connections ─────────────────────────────────────────────
    def pg_dsn(self, *, reader: bool = False) -> str:
        user = self.pg_reader_user if reader else self.pg_user
        pw = self.pg_reader_password if reader else self.pg_password
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} "
            f"user={user} password={pw}"
        )

    def run_metadata(self, generator_version: str) -> dict[str, str]:
        """The key/value snapshot persisted to the ``run_metadata`` table."""
        return {
            "now_anchor": self.anchor.isoformat(),
            "master_seed": str(self.master_seed),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "sample_seconds": str(self.sample_seconds),
            "window_days": str(self.window_days),
            "maintenance_history_months": str(self.maintenance_history_months),
            "currency": self.currency,
            "generator_version": generator_version,
        }


def load_env_file(path: str | None = None) -> list[str]:
    """Export ``.env`` into ``os.environ``; returns the names actually set.

    ``Settings`` reads ``.env`` straight into *this object* and never touches the process
    environment — which is fine for our own config, but invisible to libraries configured
    purely through environment variables. LangSmith is the one that bites: without this, a
    run started from a script or a notebook is **silently untraced**, while the same graph
    run under ``langgraph dev`` traces fine (the CLI exports ``.env`` itself, via the
    ``"env"`` key in ``langgraph.json``).

    Existing environment variables win, so an explicit export still overrides the file.
    """
    import os

    env_path = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return []

    applied: list[str] = []
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            applied.append(key)
    return applied


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton so the anchor is resolved exactly once."""
    return Settings()
