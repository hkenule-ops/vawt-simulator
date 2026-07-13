from fastapi import APIRouter
from fastapi.responses import Response

from app.schemas.cfd import (
    PanelMethodRequest, PanelMethodResponse,
    CFDCaseRequest, ForceCoeffsParseRequest, ForceCoeffsParseResponse,
    ValidationRequest, ValidationResponse,
)
from app.api.routes_geometry import to_domain
from app.cfd.panel_method import solve_panel_method
from app.cfd.case_builder import build_case_zip_bytes
from app.cfd.openfoam_case_generator import CFDCaseConfig
from app.cfd.results_parser import parse_force_coeffs, average_last_fraction
from app.cfd.validation import compare_bem_to_cfd
from app.aero.darrieus_bem import solve_darrieus_operating_point

router = APIRouter(prefix="/cfd", tags=["cfd"])


@router.post("/panel-method", response_model=PanelMethodResponse)
def run_panel_method(req: PanelMethodRequest):
    """
    Stage-2a: fast in-process 2D potential-flow surface pressure distribution
    for the blade section, used as an intermediate consistency check before
    committing to a full OpenFOAM run.
    """
    r = solve_panel_method(req.airfoil_thickness_ratio, req.alpha_deg, req.n_panels)
    return PanelMethodResponse(**r.__dict__)


@router.post("/openfoam-case")
def generate_openfoam_case(req: CFDCaseRequest):
    """
    Stage-2b: generates a downloadable, ready-to-run OpenFOAM case (zip) for
    the given design and operating point. Requires OpenFOAM installed
    locally/on a cluster to actually execute -- see the case README.
    """
    domain = to_domain(req.geometry)
    cfg = CFDCaseConfig(
        wind_speed_ms=req.wind_speed_ms,
        tip_speed_ratio=req.tip_speed_ratio,
        end_time_revolutions=req.end_time_revolutions,
    )
    zip_bytes = build_case_zip_bytes(domain, cfg)
    filename = f"{domain.name.replace(' ', '_')}_cfd_case.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/parse-results", response_model=ForceCoeffsParseResponse)
def parse_results(req: ForceCoeffsParseRequest):
    """Parse an uploaded OpenFOAM forceCoeffs coefficient.dat file's contents."""
    series = parse_force_coeffs(req.file_content)
    avg = average_last_fraction(series, req.averaging_window_fraction)
    return ForceCoeffsParseResponse(
        cd_mean=avg.cd_mean, cl_mean=avg.cl_mean, cm_mean=avg.cm_mean,
        n_samples_averaged=avg.n_samples_averaged,
        averaging_window_fraction=avg.averaging_window_fraction,
        n_total_samples=len(series.time),
    )


@router.post("/validate-against-bem", response_model=ValidationResponse)
def validate_against_bem(req: ValidationRequest):
    """Compare a CFD result (already parsed/averaged) against the Stage-1 BEM prediction."""
    from app.cfd.results_parser import CFDAveragedResult

    domain = to_domain(req.geometry)
    bem_point = solve_darrieus_operating_point(domain.darrieus, req.wind_speed_ms, req.tip_speed_ratio)
    cfd_result = CFDAveragedResult(
        cd_mean=req.cfd_cd_mean, cl_mean=req.cfd_cl_mean, cm_mean=0.0,
        n_samples_averaged=0, averaging_window_fraction=0.0,
    )
    report = compare_bem_to_cfd(bem_point, cfd_result)
    return ValidationResponse(**report.__dict__)
