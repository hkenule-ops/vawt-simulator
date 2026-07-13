import pytest
from app.economics.financial_metrics import (
    capital_recovery_factor, compute_npv, compute_irr, compute_simple_payback_years, compute_lcoe,
)


def test_crf_at_zero_discount_rate_equals_one_over_lifetime():
    assert capital_recovery_factor(0.0, 20) == pytest.approx(1.0 / 20)
    assert capital_recovery_factor(0.0, 10) == pytest.approx(0.1)


def test_crf_matches_known_reference_value():
    """8% discount rate, 20-year lifetime is a commonly cited reference case (~0.1019)."""
    crf = capital_recovery_factor(0.08, 20)
    assert crf == pytest.approx(0.10185, abs=1e-4)


def test_npv_at_zero_discount_rate_is_simple_sum():
    """At r=0, NPV = -CAPEX + n * annual_net_cash_flow -- trivial arithmetic."""
    npv = compute_npv(
        total_capex_usd=1000, annual_opex_usd=50, aep_kwh=1000,
        electricity_price_usd_per_kwh=0.30, discount_rate=0.0, lifetime_years=10,
    )
    assert npv == pytest.approx(-1000 + 10 * (300 - 50), rel=1e-9)


def test_irr_matches_hand_solvable_single_year_case():
    """CAPEX=1000, single year cash flow=1200, no OPEX -> r = 1200/1000 - 1 = 0.20 exactly."""
    irr = compute_irr(total_capex_usd=1000, annual_opex_usd=0, aep_kwh=1200,
                       electricity_price_usd_per_kwh=1.0, lifetime_years=1)
    assert irr == pytest.approx(0.20, rel=1e-4)


def test_irr_returns_none_when_cash_flow_never_positive():
    irr = compute_irr(total_capex_usd=1000, annual_opex_usd=500, aep_kwh=100,
                       electricity_price_usd_per_kwh=0.1, lifetime_years=10)
    assert irr is None


def test_payback_matches_simple_division():
    pb = compute_simple_payback_years(
        total_capex_usd=1000, annual_opex_usd=50, aep_kwh=1000, electricity_price_usd_per_kwh=0.25,
    )
    assert pb == pytest.approx(1000 / (250 - 50), rel=1e-9)


def test_payback_is_infinite_for_negative_cash_flow():
    pb = compute_simple_payback_years(
        total_capex_usd=1000, annual_opex_usd=1000, aep_kwh=100, electricity_price_usd_per_kwh=0.1,
    )
    assert pb == float("inf")


def test_lcoe_positive_and_finite_for_normal_inputs():
    lcoe = compute_lcoe(
        total_capex_usd=5000, annual_opex_usd=100, aep_kwh=1000,
        discount_rate=0.06, lifetime_years=20,
    )
    assert 0 < lcoe < float("inf")


def test_lcoe_increases_with_capex():
    lcoe_cheap = compute_lcoe(total_capex_usd=3000, annual_opex_usd=100, aep_kwh=1000, discount_rate=0.06, lifetime_years=20)
    lcoe_expensive = compute_lcoe(total_capex_usd=8000, annual_opex_usd=100, aep_kwh=1000, discount_rate=0.06, lifetime_years=20)
    assert lcoe_expensive > lcoe_cheap


def test_lcoe_decreases_with_more_energy_for_fixed_cost():
    lcoe_low_aep = compute_lcoe(total_capex_usd=5000, annual_opex_usd=100, aep_kwh=500, discount_rate=0.06, lifetime_years=20)
    lcoe_high_aep = compute_lcoe(total_capex_usd=5000, annual_opex_usd=100, aep_kwh=2000, discount_rate=0.06, lifetime_years=20)
    assert lcoe_high_aep < lcoe_low_aep
