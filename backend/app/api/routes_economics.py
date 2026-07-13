from fastapi import APIRouter, HTTPException

from app.schemas.economics import (
    EconomicAnalysisRequest, EconomicAnalysisResponse, AEPResultOut, CapexBreakdownOut,
)
from app.api.routes_geometry import to_domain
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material, MATERIAL_LIBRARY
from app.composites.lamina import PLY_LIBRARY
from app.economics.economic_analysis import analyze_economics

router = APIRouter(prefix="/economics", tags=["economics"])


@router.post("/analyze", response_model=EconomicAnalysisResponse)
def analyze(req: EconomicAnalysisRequest):
    if req.material not in MATERIAL_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown material. Available: {list(MATERIAL_LIBRARY)}")
    if req.ply_material not in PLY_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown ply material. Available: {list(PLY_LIBRARY)}")

    domain = to_domain(req.geometry)
    mat = get_material(req.material)
    spar = spar_from_blade_geometry(
        domain.darrieus.chord_m, domain.darrieus.blade_thickness_ratio,
        req.spar_width_fraction, req.spar_wall_thickness_m,
    )
    spar_mass = spar.area_m2 * domain.darrieus.blade_height_m * mat.density_kg_m3

    result = analyze_economics(
        domain, spar_mass_kg=spar_mass, ply_material_key=req.ply_material,
        electricity_price_usd_per_kwh=req.electricity_price_usd_per_kwh,
        discount_rate=req.discount_rate, project_lifetime_years=req.project_lifetime_years,
        weibull_k=req.weibull_k, weibull_c=req.weibull_c,
        opex_fraction_of_capex=req.opex_fraction_of_capex,
    )

    return EconomicAnalysisResponse(
        aep=AEPResultOut(**result.aep.__dict__),
        capex=CapexBreakdownOut(**result.capex.__dict__),
        annual_opex_usd=result.annual_opex_usd,
        lcoe_usd_per_kwh=result.lcoe_usd_per_kwh,
        npv_usd=result.npv_usd,
        irr=result.irr,
        simple_payback_years=result.simple_payback_years,
        annual_revenue_usd=result.annual_revenue_usd,
        warnings=result.warnings,
    )
