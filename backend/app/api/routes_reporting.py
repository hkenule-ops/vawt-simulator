from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.reporting import ReportRequest
from app.api.routes_geometry import to_domain
from app.structural.materials import MATERIAL_LIBRARY
from app.composites.lamina import PLY_LIBRARY
from app.reporting.report_data import assemble_report_data
from app.reporting.docx_report import generate_docx_report
from app.reporting.xlsx_report import generate_xlsx_report
from app.reporting.pdf_report import generate_pdf_report
from app.reporting.csv_export import generate_csv_export

router = APIRouter(prefix="/reporting", tags=["reporting"])


def _validate_and_assemble(req: ReportRequest):
    if req.material not in MATERIAL_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown material. Available: {list(MATERIAL_LIBRARY)}")
    if req.ply_material not in PLY_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown ply material. Available: {list(PLY_LIBRARY)}")
    domain = to_domain(req.geometry)
    return assemble_report_data(
        domain, material_key=req.material, ply_material_key=req.ply_material,
        wind_speed_ms=req.wind_speed_ms, operating_tsr=req.operating_tsr,
    )


def _filename(geom_name: str, ext: str) -> str:
    return f"{geom_name.replace(' ', '_')}_report.{ext}"


@router.post("/docx")
def report_docx(req: ReportRequest):
    data = _validate_and_assemble(req)
    content = generate_docx_report(data)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{_filename(data.geometry.name, "docx")}"'},
    )


@router.post("/xlsx")
def report_xlsx(req: ReportRequest):
    data = _validate_and_assemble(req)
    content = generate_xlsx_report(data)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_filename(data.geometry.name, "xlsx")}"'},
    )


@router.post("/pdf")
def report_pdf(req: ReportRequest):
    data = _validate_and_assemble(req)
    content = generate_pdf_report(data)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(data.geometry.name, "pdf")}"'},
    )


@router.post("/csv")
def report_csv(req: ReportRequest):
    data = _validate_and_assemble(req)
    content = generate_csv_export(data)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{_filename(data.geometry.name, "csv")}"'},
    )
