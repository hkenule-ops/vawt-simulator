from fastapi import APIRouter, HTTPException

from app.schemas.composites import (
    LaminateRequest, LaminateResponse, CompositeOptimizeRequest, OptimizedSparOut, CompositeCompareResponse,
)
from app.api.routes_geometry import to_domain
from app.composites.lamina import get_ply, PLY_LIBRARY
from app.composites.laminate import Ply, analyze_laminate
from app.composites.optimizer import optimize_spar_layup, compare_materials, OptimizedSparDesign

router = APIRouter(prefix="/composites", tags=["composites"])


@router.get("/ply-materials")
def list_ply_materials():
    return [
        {"key": k, "name": m.name, "e1_pa": m.e1_pa, "e2_pa": m.e2_pa,
         "g12_pa": m.g12_pa, "v12": m.v12, "density_kg_m3": m.density_kg_m3,
         "tensile_strength_1_pa": m.tensile_strength_1_pa}
        for k, m in PLY_LIBRARY.items()
    ]


@router.post("/laminate", response_model=LaminateResponse)
def compute_laminate(req: LaminateRequest):
    """Run Classical Laminate Theory on an arbitrary stacking sequence."""
    if req.ply_material not in PLY_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown ply material. Available: {list(PLY_LIBRARY)}")
    mat = get_ply(req.ply_material)
    plies = [Ply(mat, angle) for angle in req.angles_deg]
    r = analyze_laminate(plies)
    return LaminateResponse(
        total_thickness_m=r.total_thickness_m, ex_pa=r.ex_pa, ey_pa=r.ey_pa, gxy_pa=r.gxy_pa,
        ex_flexural_pa=r.ex_flexural_pa, density_kg_m3=r.density_kg_m3,
        mass_per_area_kg_m2=r.mass_per_area_kg_m2, max_b_matrix_term=r.max_b_matrix_term,
    )


def _to_out(opt: OptimizedSparDesign) -> OptimizedSparOut:
    r = opt.result
    return OptimizedSparOut(
        material_key=opt.material_key, n_cap_plies=opt.n_cap_plies, n_web_pairs=opt.n_web_pairs,
        spar_width_fraction=opt.spar_width_fraction, feasible=opt.feasible,
        spar_mass_kg=r.spar_mass_kg, cap_thickness_m=r.cap_thickness_m, web_thickness_m=r.web_thickness_m,
        combined_max_stress_pa=r.combined_max_stress_pa, safety_factor=r.safety_factor,
        buckling_safety_factor=r.buckling_safety_factor, warnings=r.warnings,
    )


@router.post("/optimize-spar", response_model=OptimizedSparOut)
def optimize_spar(req: CompositeOptimizeRequest):
    if req.material not in PLY_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown ply material. Available: {list(PLY_LIBRARY)}")
    domain = to_domain(req.geometry)
    opt = optimize_spar_layup(
        domain, req.material, req.wind_speed_ms, req.tip_speed_ratio,
        target_safety_factor=req.target_safety_factor, boundary=req.boundary,
    )
    return _to_out(opt)


@router.post("/compare-materials", response_model=CompositeCompareResponse)
def compare_spar_materials(req: CompositeOptimizeRequest):
    domain = to_domain(req.geometry)
    results = compare_materials(
        domain, req.wind_speed_ms, req.tip_speed_ratio,
        target_safety_factor=req.target_safety_factor, boundary=req.boundary,
    )
    return CompositeCompareResponse(
        cfrp=_to_out(results["CFRP_UD_PLY"]),
        gfrp=_to_out(results["GFRP_UD_PLY"]),
    )
