"""
OPEX (annual operating expenditure): the standard simplified small-wind
approach of expressing annual O&M cost as a percentage of CAPEX per year
(typical small wind: 1-3% annually), rather than a detailed maintenance
schedule (inspection intervals, component replacement costs, etc.) which
would need field reliability data this platform doesn't have.
"""
from __future__ import annotations


def estimate_annual_opex(total_capex_usd: float, opex_fraction_of_capex: float = 0.02) -> float:
    return total_capex_usd * opex_fraction_of_capex
