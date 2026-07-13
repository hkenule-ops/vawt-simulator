"""
CAPEX (capital expenditure) cost model: a parametric buildup, not a detailed
bill-of-materials costing (that would need supplier quotes). Blade material
cost is grounded in this platform's own Stage-4 composite spar mass output
(genuinely computed, not guessed); everything else (generator, electronics,
tower, foundation, installation) uses representative per-unit costs typical
of small wind turbine systems, clearly flagged as estimates.

Reference cost ranges (approximate, USD, small-wind-scale 300-500W class):
  - CFRP prepreg: $30-60/kg raw material (mid-range used here: $45/kg)
  - GFRP prepreg: $4-8/kg (mid-range: $6/kg)
  - These are material cost only -- not fabrication/labor, which is folded
    into a separate blade fabrication multiplier below.
"""
from __future__ import annotations
from dataclasses import dataclass

MATERIAL_COST_USD_PER_KG = {
    "CFRP_UD_PLY": 45.0,
    "GFRP_UD_PLY": 6.0,
}


@dataclass
class CapexBreakdown:
    blade_material_cost_usd: float
    blade_fabrication_cost_usd: float
    generator_electronics_cost_usd: float
    tower_foundation_cost_usd: float
    installation_cost_usd: float
    total_capex_usd: float


def estimate_capex(
    spar_mass_kg: float,
    ply_material_key: str,
    num_blades: int,
    target_power_w: float,
    fabrication_multiplier: float = 2.5,
    generator_cost_per_watt: float = 1.20,
    tower_foundation_cost_usd: float = 800.0,
    installation_fraction_of_hardware: float = 0.20,
) -> CapexBreakdown:
    """
    fabrication_multiplier: blade fabrication (layup labor, resin infusion,
    tooling amortization, waste) typically costs several times the raw
    material cost for small-batch/prototype production -- 2.5x is a
    representative mid-range estimate for low-volume composite blade
    manufacture, not mass-production pricing.
    generator_cost_per_watt: small permanent-magnet generator + electronics
    (rectifier, charge controller/inverter) cost, typical small-wind range
    ~$0.8-2.0/W rated.
    """
    material_cost_per_kg = MATERIAL_COST_USD_PER_KG.get(ply_material_key, 20.0)
    total_blade_mass = spar_mass_kg * num_blades
    blade_material_cost = total_blade_mass * material_cost_per_kg
    blade_fabrication_cost = blade_material_cost * (fabrication_multiplier - 1.0)

    generator_cost = target_power_w * generator_cost_per_watt

    hardware_subtotal = blade_material_cost + blade_fabrication_cost + generator_cost + tower_foundation_cost_usd
    installation_cost = hardware_subtotal * installation_fraction_of_hardware

    total = hardware_subtotal + installation_cost

    return CapexBreakdown(
        blade_material_cost_usd=blade_material_cost,
        blade_fabrication_cost_usd=blade_fabrication_cost,
        generator_electronics_cost_usd=generator_cost,
        tower_foundation_cost_usd=tower_foundation_cost_usd,
        installation_cost_usd=installation_cost,
        total_capex_usd=total,
    )
