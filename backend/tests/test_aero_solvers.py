"""
Physical sanity tests for the Stage-1 aerodynamic solvers.

These aren't just "does it run" tests -- they check real physical
constraints (Betz limit, positive power, sensible Cp-lambda curve shape)
that a broken momentum-balance or sign error would violate. This is exactly
the class of bug the earlier hand-check caught (a swapped sin/cos in the
velocity triangle silently zeroed out net thrust and let Cp exceed physical
limits).
"""
import math
import pytest

from app.geometry.models import HybridRotorGeometry, DarrieusBladeGeometry
from app.aero.darrieus_bem import solve_darrieus_operating_point
from app.aero.hybrid_solver import solve_hybrid_operating_point, cp_lambda_curve, power_curve

BETZ_LIMIT = 0.593


def test_darrieus_cp_never_exceeds_betz_limit():
    geom = DarrieusBladeGeometry()
    for tsr in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
        point = solve_darrieus_operating_point(geom, wind_speed_ms=8.0, tip_speed_ratio=tsr)
        assert point.cp < BETZ_LIMIT, f"Cp={point.cp} exceeds Betz limit at TSR={tsr}"


def test_darrieus_power_is_positive_in_operating_range():
    geom = DarrieusBladeGeometry()
    point = solve_darrieus_operating_point(geom, wind_speed_ms=8.0, tip_speed_ratio=2.0)
    assert point.power_w > 0
    assert point.induction_factor > 0


def test_induction_factor_stays_in_physical_range():
    geom = DarrieusBladeGeometry()
    for tsr in [1.0, 2.0, 3.0, 4.0]:
        point = solve_darrieus_operating_point(geom, wind_speed_ms=8.0, tip_speed_ratio=tsr)
        assert 0.0 <= point.induction_factor <= 0.6


def test_cp_lambda_curve_has_a_single_dominant_peak_shape():
    """A sane Darrieus Cp-lambda curve rises then falls -- not monotonic, not flat."""
    geom = HybridRotorGeometry()
    curve = cp_lambda_curve(geom, wind_speed_ms=8.0, tsr_min=1.0, tsr_max=4.0, n_points=16)
    cps = [p.system_cp for p in curve]
    peak_idx = cps.index(max(cps))
    # peak should not sit exactly at either boundary of a wide TSR sweep
    assert 0 < peak_idx < len(cps) - 1


def test_hybrid_power_is_sum_of_stages():
    geom = HybridRotorGeometry()
    point = solve_hybrid_operating_point(geom, wind_speed_ms=8.0, tip_speed_ratio=2.0)
    assert point.total_power_w == pytest.approx(
        point.darrieus_power_w + point.savonius_power_w, rel=1e-6
    )


def test_power_curve_respects_cut_in_and_cut_out():
    geom = HybridRotorGeometry(cut_in_wind_speed_ms=3.0, cut_out_wind_speed_ms=20.0)
    results = power_curve(geom, [1.0, 3.0, 10.0, 25.0])
    assert results[0] is None    # below cut-in
    assert results[3] is None    # above cut-out
    assert results[1] is not None
    assert results[2] is not None


def test_power_increases_with_wind_speed_at_fixed_tsr():
    geom = HybridRotorGeometry()
    p1 = solve_hybrid_operating_point(geom, wind_speed_ms=6.0, tip_speed_ratio=2.25)
    p2 = solve_hybrid_operating_point(geom, wind_speed_ms=9.0, tip_speed_ratio=2.25)
    assert p2.total_power_w > p1.total_power_w


def test_300w_target_geometry_lands_in_plausible_power_band():
    """
    Default geometry sized loosely for the 300W target should produce a
    peak power (across a realistic wind-speed sweep) within an order of
    magnitude of the target -- catches gross unit or scaling errors, not a
    tight design-validation check (that's what the optimiser in Phase 12 is for).
    """
    geom = HybridRotorGeometry(target_power_w=300.0)
    results = power_curve(geom, [5, 6, 7, 8, 9, 10, 11, 12])
    powers = [p.total_power_w for p in results if p is not None]
    assert max(powers) > 30       # not effectively zero
    assert max(powers) < 3000     # not off by 10x+
