from __future__ import annotations
import io
import zipfile

from app.geometry.models import HybridRotorGeometry
from app.cfd.openfoam_case_generator import (
    CFDCaseConfig, generate_control_dict, generate_fv_schemes, generate_fv_solution,
    generate_dynamic_mesh_dict, generate_transport_properties, generate_turbulence_properties,
    generate_boundary_field_U, generate_boundary_field_p, generate_readme,
)
from app.cfd.stl_export import generate_blade_stl


def build_case_zip_bytes(geom: HybridRotorGeometry, cfg: CFDCaseConfig) -> bytes:
    files = {
        "README.md": generate_readme(geom, cfg),
        "blade.stl": generate_blade_stl(
            chord_m=geom.darrieus.chord_m,
            thickness_ratio=geom.darrieus.blade_thickness_ratio,
            span_m=geom.darrieus.blade_height_m,
        ),
        "system/controlDict": generate_control_dict(geom, cfg),
        "system/fvSchemes": generate_fv_schemes(),
        "system/fvSolution": generate_fv_solution(),
        "constant/dynamicMeshDict": generate_dynamic_mesh_dict(geom, cfg),
        "constant/transportProperties": generate_transport_properties(geom),
        "constant/turbulenceProperties": generate_turbulence_properties(),
        "0/U": generate_boundary_field_U(cfg),
        "0/p": generate_boundary_field_p(),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        case_root = geom.name.replace(" ", "_") or "vawt_cfd_case"
        for rel_path, content in files.items():
            zf.writestr(f"{case_root}/{rel_path}", content)
    buf.seek(0)
    return buf.read()
