from fastapi import APIRouter, HTTPException

from app.schemas.aeroelastic import (
    AeroelasticAnalysisRequest, AeroelasticAnalysisResponse, ModalResultOut,
    CampbellResultOut, ResonanceRiskOut, HarmonicContentOut,
)
from app.api.routes_geometry import to_domain
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material, MATERIAL_LIBRARY
from app.aeroelastic.blade_aeroelastic_analysis import analyze_blade_aeroelastics

router = APIRouter(prefix="/aeroelastic", tags=["aeroelastic"])


@router.post("/analyze-blade", response_model=AeroelasticAnalysisResponse)
def analyze_aeroelastics(req: AeroelasticAnalysisRequest):
    if req.material not in MATERIAL_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown material. Available: {list(MATERIAL_LIBRARY)}")

    domain = to_domain(req.geometry)
    mat = get_material(req.material)
    spar = spar_from_blade_geometry(
        domain.darrieus.chord_m, domain.darrieus.blade_thickness_ratio,
        req.spar_width_fraction, req.spar_wall_thickness_m,
    )
    EI = mat.youngs_modulus_pa * spar.i_flapwise_m4
    mass_per_length = spar.area_m2 * mat.density_kg_m3

    result = analyze_blade_aeroelastics(
        domain, ei_flapwise=EI, mass_per_length_kg_m=mass_per_length,
        operating_tsr=req.operating_tsr, boundary=req.boundary, n_modes=req.n_modes,
    )

    return AeroelasticAnalysisResponse(
        modal=ModalResultOut(**result.modal.__dict__),
        campbell=CampbellResultOut(
            rpm_range=result.campbell.rpm_range,
            natural_frequencies_hz=result.campbell.natural_frequencies_hz,
            excitation_lines_hz={str(k): v for k, v in result.campbell.excitation_lines_hz.items()},
            resonance_risks=[ResonanceRiskOut(**r.__dict__) for r in result.campbell.resonance_risks],
        ),
        harmonics=HarmonicContentOut(**result.harmonics.__dict__),
        operating_rpm_min=result.operating_rpm_min,
        operating_rpm_max=result.operating_rpm_max,
        warnings=result.warnings,
    )
