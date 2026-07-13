from fastapi import APIRouter, HTTPException

from app.schemas.validation import ValidationRunRequest, ValidationReportOut, CheckResultOut
from app.api.routes_geometry import to_domain
from app.structural.materials import MATERIAL_LIBRARY
from app.composites.lamina import PLY_LIBRARY
from app.validation.system_checks import run_system_validation

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/run-checks", response_model=ValidationReportOut)
def run_checks(req: ValidationRunRequest):
    if req.material not in MATERIAL_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown material. Available: {list(MATERIAL_LIBRARY)}")
    if req.ply_material not in PLY_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown ply material. Available: {list(PLY_LIBRARY)}")

    domain = to_domain(req.geometry)
    report = run_system_validation(
        domain, material_key=req.material, ply_material_key=req.ply_material,
        operating_tsr=req.operating_tsr, wind_speed_ms=req.wind_speed_ms,
    )
    return ValidationReportOut(
        checks=[CheckResultOut(**c.__dict__) for c in report.checks],
        all_passed=report.all_passed, n_passed=report.n_passed, n_total=report.n_total,
    )
