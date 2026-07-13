"""
Euler critical buckling load for slender columns -- standard closed-form
formula, used here as a secondary check alongside the bending/stress
analysis (buckling governs for slender members under compressive axial
load; bending stress governs for transverse/distributed loading, which is
the blade's dominant load case).

Effective length factors (K) for standard end conditions:
    pinned-pinned:      K = 1.0
    fixed-free (cantilever): K = 2.0
    fixed-fixed:         K = 0.5
    fixed-pinned:        K = 0.7
"""
from __future__ import annotations
import math

K_FACTORS = {
    "pinned-pinned": 1.0,
    "cantilever": 2.0,
    "fixed-fixed": 0.5,
    "fixed-pinned": 0.7,
}


def euler_critical_buckling_load(EI: float, length_m: float, end_condition: str = "pinned-pinned") -> float:
    if end_condition not in K_FACTORS:
        raise ValueError(f"end_condition must be one of {list(K_FACTORS)}")
    K = K_FACTORS[end_condition]
    L_eff = K * length_m
    return (math.pi ** 2) * EI / (L_eff ** 2)
