from fastapi import APIRouter, HTTPException

from app.schemas.fatigue import FatigueAnalysisRequest, FatigueAnalysisResponse
from app.api.routes_geometry import to_domain
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material, MATERIAL_LIBRARY
from app.composites.lamina import PLY_LIBRARY
from app.fatigue.fatigue_analysis import analyze_blade_fatigue

router = APIRouter(prefix="/fatigue", tags=["fatigue"])


@router.post("/analyze-blade", response_model=FatigueAnalysisResponse)
def analyze_fatigue(req: FatigueAnalysisRequest):
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
    EI = mat.youngs_modulus_pa * spar.i_flapwise_m4

    result = analyze_blade_fatigue(
        domain, ei_flapwise=EI, section_i_m4=spar.i_flapwise_m4, section_c_m=spar.c_flapwise_m,
        static_strength_pa=mat.yield_strength_pa, ply_material_key=req.ply_material,
        operating_tsr=req.operating_tsr, weibull_k=req.weibull_k, weibull_c=req.weibull_c,
        boundary=req.boundary,
    )
    return FatigueAnalysisResponse(**result.__dict__)
