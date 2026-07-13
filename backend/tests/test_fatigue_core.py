import pytest
from app.fatigue.sn_curve import SNCurve
from app.fatigue.rainflow import RainflowCycle
from app.fatigue.miners_rule import compute_miners_damage


def test_sn_curve_matches_basquin_closed_form():
    sn = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=10.0)
    n = sn.cycles_to_failure(500e6)
    assert n == pytest.approx((500e6 / 1000e6) ** -10, rel=1e-9)


def test_sn_curve_gives_one_cycle_at_static_strength():
    sn = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=10.0)
    assert sn.cycles_to_failure(1000e6) == pytest.approx(1.0)


def test_sn_curve_gives_one_cycle_above_static_strength():
    sn = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=10.0)
    assert sn.cycles_to_failure(1500e6) == pytest.approx(1.0)


def test_higher_fatigue_exponent_gives_longer_life_below_static_strength():
    """A steeper (higher m) S-N curve should predict more cycles to failure below the static limit."""
    sn_low_m = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=8.0)
    sn_high_m = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=12.0)
    assert sn_high_m.cycles_to_failure(500e6) > sn_low_m.cycles_to_failure(500e6)


def test_miners_rule_gives_exactly_unity_damage_at_exactly_ni_cycles():
    """Definitional check: applying exactly N_i cycles at a constant stress level must give D=1.0."""
    sn = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=10.0)
    n_i = sn.cycles_to_failure(500e6)
    cycles = [RainflowCycle(range_=1000e6, mean=0, count=n_i)]
    result = compute_miners_damage(cycles, sn)
    assert result.total_damage == pytest.approx(1.0, rel=1e-9)


def test_miners_rule_damage_is_additive_across_cycles():
    sn = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=10.0)
    cycles_a = [RainflowCycle(range_=1000e6, mean=0, count=100)]
    cycles_b = [RainflowCycle(range_=800e6, mean=0, count=200)]
    d_a = compute_miners_damage(cycles_a, sn).total_damage
    d_b = compute_miners_damage(cycles_b, sn).total_damage
    d_combined = compute_miners_damage(cycles_a + cycles_b, sn).total_damage
    assert d_combined == pytest.approx(d_a + d_b, rel=1e-9)


def test_empty_cycle_list_gives_zero_damage():
    sn = SNCurve(static_strength_pa=1000e6, fatigue_exponent_m=10.0)
    result = compute_miners_damage([], sn)
    assert result.total_damage == 0.0
