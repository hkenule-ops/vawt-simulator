"""
Phase 11 top-level economic analysis. Ties together:
  1. AEP (this module's energy_yield.py), from the Stage-1 BEM power curve
     integrated against a Weibull wind distribution.
  2. CAPEX, with blade material cost grounded in the actual Stage-4
     composite spar mass for the chosen material -- not a generic weight
     guess, the platform's own computed number.
  3. OPEX as a fraction of CAPEX.
  4. LCOE, NPV, IRR, and payback period from financial_metrics.py.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.geometry.models import HybridRotorGeometry
from app.economics.energy_yield import compute_aep, AEPResult
from app.economics.capex import estimate_capex, CapexBreakdown
from app.economics.opex import estimate_annual_opex
from app.economics.financial_metrics import (
    compute_lcoe, compute_npv, compute_irr, compute_simple_payback_years,
)


@dataclass
class EconomicAnalysisResult:
    aep: AEPResult
    capex: CapexBreakdown
    annual_opex_usd: float
    lcoe_usd_per_kwh: float
    npv_usd: float
    irr: float | None
    simple_payback_years: float
    annual_revenue_usd: float
    warnings: list[str]


def analyze_economics(
    geom: HybridRotorGeometry,
    spar_mass_kg: float,
    ply_material_key: str,
    electricity_price_usd_per_kwh: float = 0.15,
    discount_rate: float = 0.06,
    project_lifetime_years: int = 20,
    weibull_k: float = 2.0,
    weibull_c: float = 7.0,
    opex_fraction_of_capex: float = 0.02,
    aep_wind_bins_ms: list[float] | None = None,
    aep_n_azimuth: int = 36,
    aep_tsr_search_points: int = 8,
) -> EconomicAnalysisResult:
    aep_result = compute_aep(
        geom, weibull_k=weibull_k, weibull_c=weibull_c, wind_bins_ms=aep_wind_bins_ms,
        n_azimuth=aep_n_azimuth, tsr_search_points=aep_tsr_search_points,
    )

    capex_result = estimate_capex(
        spar_mass_kg=spar_mass_kg, ply_material_key=ply_material_key,
        num_blades=geom.darrieus.num_blades, target_power_w=geom.target_power_w,
    )
    annual_opex = estimate_annual_opex(capex_result.total_capex_usd, opex_fraction_of_capex)

    lcoe = compute_lcoe(
        capex_result.total_capex_usd, annual_opex, aep_result.aep_kwh,
        discount_rate, project_lifetime_years,
    )
    npv = compute_npv(
        capex_result.total_capex_usd, annual_opex, aep_result.aep_kwh,
        electricity_price_usd_per_kwh, discount_rate, project_lifetime_years,
    )
    irr = compute_irr(
        capex_result.total_capex_usd, annual_opex, aep_result.aep_kwh,
        electricity_price_usd_per_kwh, project_lifetime_years,
    )
    payback = compute_simple_payback_years(
        capex_result.total_capex_usd, annual_opex, aep_result.aep_kwh, electricity_price_usd_per_kwh,
    )
    annual_revenue = aep_result.aep_kwh * electricity_price_usd_per_kwh

    warnings = []
    if npv < 0:
        warnings.append(
            f"Negative NPV (${npv:,.0f}) at a {electricity_price_usd_per_kwh:.2f} $/kWh price and "
            f"{discount_rate*100:.0f}% discount rate -- this design is not economically viable under "
            f"these assumptions at this scale/price point."
        )
    if aep_result.capacity_factor > 0.45:
        warnings.append(
            f"Capacity factor ({aep_result.capacity_factor*100:.0f}%) is on the high side even for "
            f"an excellent wind site -- verify the Weibull scale (c={weibull_c} m/s) reflects a "
            f"realistic site resource, not an unusually favourable one."
        )
    warnings.append(
        "Revenue assumed constant (no electricity price escalation or AEP degradation over the "
        "project lifetime). CAPEX uses parametric cost estimates for generator/electronics/tower/"
        "installation, not supplier quotes -- treat as an order-of-magnitude estimate."
    )

    return EconomicAnalysisResult(
        aep=aep_result, capex=capex_result, annual_opex_usd=annual_opex,
        lcoe_usd_per_kwh=lcoe, npv_usd=npv, irr=irr, simple_payback_years=payback,
        annual_revenue_usd=annual_revenue, warnings=warnings,
    )
