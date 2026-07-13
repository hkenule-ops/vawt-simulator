"""
Miner's rule (linear cumulative damage): for each stress cycle i with
applied count n_i and cycles-to-failure N_i (from the S-N curve at that
cycle's stress amplitude), damage contribution is n_i/N_i. Total damage
D = sum(n_i/N_i); failure is predicted when D reaches 1.0. Standard,
well-established method (Palmgren-Miner), despite its known limitation of
ignoring load-sequence effects -- appropriate for a first-pass design check.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.fatigue.rainflow import RainflowCycle
from app.fatigue.sn_curve import SNCurve


@dataclass
class DamageResult:
    total_damage: float
    n_cycles_considered: float
    dominant_cycle_range_pa: float
    dominant_cycle_damage_fraction: float


def compute_miners_damage(cycles: list[RainflowCycle], sn_curve: SNCurve) -> DamageResult:
    total_damage = 0.0
    n_cycles = 0.0
    per_cycle_damage: list[tuple[float, float]] = []  # (range, damage)

    for c in cycles:
        n_i = sn_curve.cycles_to_failure(c.range_ / 2)  # range -> amplitude
        d_i = (c.count / n_i) if n_i > 0 else float("inf")
        total_damage += d_i
        n_cycles += c.count
        per_cycle_damage.append((c.range_, d_i))

    if per_cycle_damage:
        dominant = max(per_cycle_damage, key=lambda t: t[1])
        dominant_range, dominant_damage = dominant
        dominant_fraction = dominant_damage / total_damage if total_damage > 0 else 0.0
    else:
        dominant_range, dominant_fraction = 0.0, 0.0

    return DamageResult(
        total_damage=total_damage,
        n_cycles_considered=n_cycles,
        dominant_cycle_range_pa=dominant_range,
        dominant_cycle_damage_fraction=dominant_fraction,
    )
