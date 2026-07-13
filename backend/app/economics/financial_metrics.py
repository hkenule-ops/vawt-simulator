"""
Standard financial metrics for turbine economics: Levelized Cost of Energy
(LCOE), Net Present Value (NPV), Internal Rate of Return (IRR), and simple
payback period. All standard, well-established formulas -- validated in
tests/test_financial_metrics.py against hand-computable closed-form cases
(e.g. a single-year IRR problem solvable by algebra: CAPEX = CF1/(1+r)).

Revenue is assumed constant year-over-year (no electricity price escalation
or AEP degradation over the project lifetime) -- a simplification flagged
here and in the API docs, not a hidden assumption.
"""
from __future__ import annotations
from dataclasses import dataclass
from scipy.optimize import brentq


def capital_recovery_factor(discount_rate: float, lifetime_years: int) -> float:
    if lifetime_years <= 0:
        raise ValueError("lifetime_years must be positive")
    if abs(discount_rate) < 1e-12:
        return 1.0 / lifetime_years
    r, n = discount_rate, lifetime_years
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def compute_lcoe(
    total_capex_usd: float, annual_opex_usd: float, aep_kwh: float,
    discount_rate: float, lifetime_years: int,
) -> float:
    if aep_kwh <= 0:
        return float("inf")
    crf = capital_recovery_factor(discount_rate, lifetime_years)
    annualized_capex = total_capex_usd * crf
    return (annualized_capex + annual_opex_usd) / aep_kwh


def compute_npv(
    total_capex_usd: float, annual_opex_usd: float, aep_kwh: float,
    electricity_price_usd_per_kwh: float, discount_rate: float, lifetime_years: int,
) -> float:
    annual_revenue = aep_kwh * electricity_price_usd_per_kwh
    annual_net_cash_flow = annual_revenue - annual_opex_usd
    npv = -total_capex_usd
    for t in range(1, lifetime_years + 1):
        npv += annual_net_cash_flow / (1 + discount_rate) ** t
    return npv


def compute_irr(
    total_capex_usd: float, annual_opex_usd: float, aep_kwh: float,
    electricity_price_usd_per_kwh: float, lifetime_years: int,
) -> float | None:
    """Returns None if no real IRR exists in a reasonable search bracket (e.g. cash flows never recover CAPEX)."""
    annual_revenue = aep_kwh * electricity_price_usd_per_kwh
    annual_net_cash_flow = annual_revenue - annual_opex_usd
    if annual_net_cash_flow <= 0:
        return None

    def npv_at_rate(r: float) -> float:
        npv = -total_capex_usd
        for t in range(1, lifetime_years + 1):
            npv += annual_net_cash_flow / (1 + r) ** t
        return npv

    lo, hi = -0.99, 10.0
    if npv_at_rate(lo) * npv_at_rate(hi) > 0:
        return None  # no sign change in bracket -- no IRR found in a plausible range
    return brentq(npv_at_rate, lo, hi, xtol=1e-6)


def compute_simple_payback_years(
    total_capex_usd: float, annual_opex_usd: float, aep_kwh: float,
    electricity_price_usd_per_kwh: float,
) -> float:
    annual_revenue = aep_kwh * electricity_price_usd_per_kwh
    annual_net_cash_flow = annual_revenue - annual_opex_usd
    if annual_net_cash_flow <= 0:
        return float("inf")
    return total_capex_usd / annual_net_cash_flow


@dataclass
class FinancialMetrics:
    lcoe_usd_per_kwh: float
    npv_usd: float
    irr: float | None
    simple_payback_years: float
    annual_revenue_usd: float
    annual_net_cash_flow_usd: float
