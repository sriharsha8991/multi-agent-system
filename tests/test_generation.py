"""Generator tests that don't need a database (demo guarantees, determinism)."""

from __future__ import annotations

import numpy as np
import pytest

from mas.config import get_settings
from mas.datagen import alerts as al
from mas.datagen import build_telemetry as bt


@pytest.fixture(scope="module")
def data():
    return bt.generate_all(get_settings())


def test_shapes_and_null_budget(data):
    n = data.ctx.grid.n
    total = nulls = 0
    for sys in data.arrays:
        for name, arr in data.arrays[sys].items():
            assert arr.shape[0] == n
            total += arr.size
            nulls += int(np.isnan(arr).sum())
    assert nulls / total <= 0.0015


def test_dg1_latest_bfpa_alert_is_bearing(data):
    alerts = al.detect(data)
    bfpa = sorted([a for a in alerts if a["system"] == "bfpa"], key=lambda x: x["start_ts"])
    assert bfpa, "no bfpa alerts"
    assert bfpa[-1]["tag_name"] == "bearing_temp_1"
    assert bfpa[-1]["alert_level"] in ("hi", "hi_hi")


def test_dg1_bearing_excursion_exceeds_threshold(data):
    alerts = al.detect(data)
    bearing = [a for a in alerts if a["system"] == "bfpa"
               and a["tag_name"] == "bearing_temp_1" and a["has_telemetry"]]
    assert bearing
    a = sorted(bearing, key=lambda x: x["start_ts"])[-1]
    assert a["peak_value"] >= a["threshold_value"] + 2.0


def test_dg3_comparison_well_posed(data):
    day = data.ctx.grid.day_float
    last7 = day >= 23.0
    a = np.nanmean(data.arrays["bfpa"]["bearing_temp_1"][last7])
    b = np.nanmean(data.arrays["bfpb"]["bearing_temp_1"][last7])
    assert (a - b) >= 3.0


def test_determinism_same_arrays_twice():
    d1 = bt.generate_all(get_settings())
    d2 = bt.generate_all(get_settings())
    a1 = np.nan_to_num(d1.arrays["bfpa"]["bearing_temp_1"])
    a2 = np.nan_to_num(d2.arrays["bfpa"]["bearing_temp_1"])
    assert np.array_equal(a1, a2)


def test_operating_regions_separable(data):
    sk = pytest.importorskip("sklearn")
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    a = data.arrays["bfpa"]
    X = np.column_stack([a["flow_rate"], a["pump_efficiency"], a["vibration_overall"]])
    X = X[~np.isnan(X).any(axis=1)]
    Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    rng = np.random.default_rng(0)
    idx = rng.choice(len(Z), 3000, replace=False)
    km = KMeans(n_clusters=4, n_init=10, random_state=0).fit(Z[idx])
    sil = silhouette_score(Z[idx][:1200], km.labels_[:1200])
    assert sil >= 0.45
