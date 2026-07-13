"""
Weibull wind speed probability distribution -- the standard model for site
wind resource (IEC 61400-1/2 both use it as the default reference
distribution for annual energy and load estimates). Used here to weight how
many hours per year the turbine spends at each wind speed bin, which sets
how many fatigue cycles accumulate at each bin's stress amplitude.
"""
from __future__ import annotations
import math


def weibull_pdf(v: float, k: float, c: float) -> float:
    """Probability density at wind speed v (m/s), shape k, scale c (m/s)."""
    if v <= 0:
        return 0.0
    return (k / c) * (v / c) ** (k - 1) * math.exp(-((v / c) ** k))


def bin_probabilities(v_bins: list[float], k: float, c: float) -> list[float]:
    """
    Probability mass in each bin, via trapezoidal integration of the PDF
    over each bin's width (bins assumed to be bin centres with uniform or
    near-uniform spacing; width taken from neighbouring bin midpoints).
    """
    n = len(v_bins)
    probs = []
    for i, v in enumerate(v_bins):
        lo = v_bins[i - 1] if i > 0 else max(0.0, v - (v_bins[1] - v_bins[0]) / 2 if n > 1 else 0.5)
        hi = v_bins[i + 1] if i < n - 1 else v + (v_bins[i] - v_bins[i - 1]) / 2 if i > 0 else v + 0.5
        lo_edge = (v + lo) / 2 if i > 0 else max(0.0, v - 0.5)
        hi_edge = (v + hi) / 2 if i < n - 1 else v + 0.5
        # Numerically integrate the PDF across [lo_edge, hi_edge] with a few sub-steps.
        n_steps = 10
        step = (hi_edge - lo_edge) / n_steps
        area = 0.0
        for s in range(n_steps):
            v0 = lo_edge + s * step
            v1 = v0 + step
            area += 0.5 * (weibull_pdf(v0, k, c) + weibull_pdf(v1, k, c)) * step
        probs.append(max(area, 0.0))

    total = sum(probs)
    if total > 0:
        probs = [p / total for p in probs]
    return probs


def annual_hours_per_bin(v_bins: list[float], k: float, c: float) -> list[float]:
    probs = bin_probabilities(v_bins, k, c)
    return [p * 8760.0 for p in probs]
