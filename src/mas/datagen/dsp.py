"""Small vectorized signal-processing helpers used across the generator."""

from __future__ import annotations

import numpy as np


def first_order_lag(x: np.ndarray, tau_steps: float) -> np.ndarray:
    """Causal first-order (exponential) lag — the thermal/mechanical inertia model.

    ``y[i] = y[i-1] + alpha*(x[i]-y[i-1])`` with ``alpha = 1 - exp(-1/tau_steps)``.
    Makes temperatures and loads ramp smoothly instead of teleporting, which is
    the single detail that most separates plausible from synthetic telemetry.
    """
    x = np.asarray(x, dtype=float)
    if tau_steps <= 0:
        return x.copy()
    alpha = 1.0 - np.exp(-1.0 / float(tau_steps))
    try:  # fast C path
        from scipy.signal import lfilter
        y = lfilter([alpha], [1.0, -(1.0 - alpha)], x, zi=None)
        # seed initial condition so y[0] ~ x[0] instead of alpha*x[0]
        y = y + (1.0 - alpha) ** np.arange(x.shape[0]) * (x[0] - alpha * x[0])
        return y
    except Exception:
        y = np.empty_like(x)
        acc = float(x[0])
        for i in range(x.shape[0]):
            acc += alpha * (float(x[i]) - acc)
            y[i] = acc
        return y


def diurnal(hour_of_day: np.ndarray, peak_hour: float = 14.0) -> np.ndarray:
    """Smooth [0,1] daily curve peaking at ``peak_hour`` (trough 12 h earlier)."""
    return 0.5 * (1.0 + np.sin(2.0 * np.pi * (hour_of_day - peak_hour + 6.0) / 24.0))


def random_walk(rng: np.random.Generator, n: int, step: float,
                lo: float, hi: float, start: float | None = None) -> np.ndarray:
    """Reflected random walk bounded to ``[lo, hi]`` (slow instrument drift)."""
    if start is None:
        start = 0.5 * (lo + hi)
    incr = rng.normal(0.0, step, size=n)
    walk = start + np.cumsum(incr)
    # reflect into bounds
    span = hi - lo
    if span <= 0:
        return np.full(n, lo)
    folded = np.abs((walk - lo) % (2 * span))
    folded = np.where(folded > span, 2 * span - folded, folded)
    return lo + folded


def one_over_f(rng: np.random.Generator, n: int, sigma: float) -> np.ndarray:
    """Cheap 1/f-ish drift: cumulative sum of white noise, detrended, scaled."""
    if sigma <= 0:
        return np.zeros(n)
    w = np.cumsum(rng.normal(0.0, 1.0, size=n))
    w -= np.linspace(w[0], w[-1], n)  # remove linear trend
    s = np.std(w)
    if s == 0:
        return np.zeros(n)
    return (w / s) * sigma


def scale01_to(x01: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return lo + (hi - lo) * x01
