"""Multi-Agent Systems for Industrial Asset Analytics.

Data layer package: catalog (source of truth), db (schema spin-up + IO),
datagen (physics-driven telemetry + derived graph), eval (quality gates).
"""

__version__ = "0.1.0"

# The five physical assets, in canonical order. Used everywhere as the
# authoritative system list.
SYSTEMS: tuple[str, ...] = ("bfpa", "bfpb", "cepa", "cepb", "turbine")
