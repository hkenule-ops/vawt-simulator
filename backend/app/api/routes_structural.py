from fastapi import APIRouter, HTTPException

from app.schemas.structural import (
    StructuralAnalysisRequest, StructuralAnalysisResponse, BeamResultOut, MaterialOut,
)
from app.api.routes_geometry import to_domain
from app.structural.blade_analysis import analyze_blade_structure
from app.structural.materials import MATERIAL_LIBRARY

router = APIRouter(prefix="/structural", tags=["structural"])


@router.get("/materials", response_model=list[MaterialOut])
def list_materials():
    return [
        MaterialOut(key=key, **{
            "name": mat.name, "density_kg_m3": mat.density_kg_m3,
            "youngs_modulus_pa": mat.youngs_modulus_pa, "shear_modulus_pa": mat.shear_modulus_pa,
            "yield_strength_pa": mat.yield_strength_pa, "ultimate_strength_pa": mat.ultimate_strength_pa,
        })
        for key, mat in MATERIAL_LIBRARY.items()
    ]


@router.post("/analyze-blade", response_model=StructuralAnalysisResponse)
def analyze_blade(req: StructuralAnalysisRequest):
    if req.material not in MATERIAL_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown material '{req.material}'. Available: {list(MATERIAL_LIBRARY)}")

    domain = to_domain(req.geometry)
    result = analyze_blade_structure(
        domain, req.material, req.wind_speed_ms, req.tip_speed_ratio,
        spar_width_fraction=req.spar_width_fraction,
        spar_wall_thickness_m=req.spar_wall_thickness_m,
        boundary=req.boundary,
    )
    return StructuralAnalysisResponse(
        material=result.material,
        spar_area_m2=result.spar_area_m2,
        spar_mass_kg=result.spar_mass_kg,
        flapwise_distributed_load_n_m=result.flapwise_distributed_load_n_m,
        edgewise_distributed_load_n_m=result.edgewise_distributed_load_n_m,
        centrifugal_distributed_load_n_m=result.centrifugal_distributed_load_n_m,
        flapwise=BeamResultOut(**result.flapwise.__dict__),
        edgewise=BeamResultOut(**result.edgewise.__dict__),
        max_flapwise_stress_pa=result.max_flapwise_stress_pa,
        max_edgewise_stress_pa=result.max_edgewise_stress_pa,
        combined_max_stress_pa=result.combined_max_stress_pa,
        yield_strength_pa=result.yield_strength_pa,
        safety_factor=result.safety_factor,
        euler_buckling_load_n=result.euler_buckling_load_n,
        nominal_axial_load_n=result.nominal_axial_load_n,
        buckling_safety_factor=result.buckling_safety_factor,
        warnings=result.warnings,
    )
