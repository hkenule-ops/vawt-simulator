import zipfile
import io
import pytest

from app.geometry.models import HybridRotorGeometry
from app.cfd.case_builder import build_case_zip_bytes
from app.cfd.openfoam_case_generator import CFDCaseConfig
from app.cfd.results_parser import parse_force_coeffs, average_last_fraction
from app.cfd.validation import compare_bem_to_cfd
from app.aero.darrieus_bem import solve_darrieus_operating_point

SAMPLE_FORCE_COEFFS = """\
# Force coefficients
# CofR              : (0 0 0)
# Time Cd Cd(f) Cd(r) Cl Cl(f) Cl(r) CmPitch
0.001 0.812 0.5 0.312 0.203 0.1 0.103 0.011
0.002 0.795 0.5 0.295 0.211 0.1 0.111 0.012
0.003 0.780 0.5 0.280 0.219 0.1 0.119 0.012
0.004 0.774 0.5 0.274 0.222 0.1 0.122 0.013
"""


def test_openfoam_case_zip_contains_expected_files():
    geom = HybridRotorGeometry(name="Test Case")
    cfg = CFDCaseConfig(wind_speed_ms=8.0, tip_speed_ratio=2.25)
    zip_bytes = build_case_zip_bytes(geom, cfg)

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = zf.namelist()
    expected_suffixes = [
        "README.md", "blade.stl",
        "system/controlDict", "system/fvSchemes", "system/fvSolution",
        "constant/dynamicMeshDict", "constant/transportProperties", "constant/turbulenceProperties",
        "0/U", "0/p",
    ]
    for suffix in expected_suffixes:
        assert any(n.endswith(suffix) for n in names), f"missing {suffix} in case zip"


def test_control_dict_has_valid_numeric_timestep():
    geom = HybridRotorGeometry()
    cfg = CFDCaseConfig(wind_speed_ms=8.0, tip_speed_ratio=2.25, end_time_revolutions=4.0)
    zip_bytes = build_case_zip_bytes(geom, cfg)
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    control_dict_name = next(n for n in zf.namelist() if n.endswith("system/controlDict"))
    content = zf.read(control_dict_name).decode()
    assert "deltaT" in content
    assert "endTime" in content
    # sanity: end time should be positive and consistent with 4 revolutions at this omega
    import re
    end_time = float(re.search(r"endTime\s+([\d.]+);", content).group(1))
    assert end_time > 0


def test_parse_force_coeffs_reads_all_rows():
    series = parse_force_coeffs(SAMPLE_FORCE_COEFFS)
    assert len(series.time) == 4
    assert series.cd[0] == pytest.approx(0.812)
    assert series.cl[-1] == pytest.approx(0.222)


def test_average_last_fraction_uses_correct_window():
    series = parse_force_coeffs(SAMPLE_FORCE_COEFFS)
    avg = average_last_fraction(series, fraction=0.5)
    # last 2 of 4 samples
    assert avg.n_samples_averaged == 2
    assert avg.cd_mean == pytest.approx((0.780 + 0.774) / 2)


def test_validation_report_flags_large_discrepancy():
    geom = HybridRotorGeometry()
    bem_point = solve_darrieus_operating_point(geom.darrieus, wind_speed_ms=8.0, tip_speed_ratio=2.25)
    from app.cfd.results_parser import CFDAveragedResult
    # Deliberately mismatched CFD result to check the tolerance flag fires
    bad_cfd = CFDAveragedResult(cd_mean=5.0, cl_mean=5.0, cm_mean=0, n_samples_averaged=1, averaging_window_fraction=0.25)
    report = compare_bem_to_cfd(bem_point, bad_cfd)
    assert report.percent_error > 15.0
    assert report.within_engineering_tolerance is False


def test_validation_report_passes_when_close():
    geom = HybridRotorGeometry()
    bem_point = solve_darrieus_operating_point(geom.darrieus, wind_speed_ms=8.0, tip_speed_ratio=2.25)
    from app.cfd.results_parser import CFDAveragedResult
    # Construct a CFD result whose resultant coefficient closely matches BEM's Ct
    import math
    target = bem_point.ct_thrust_coeff
    close_cfd = CFDAveragedResult(cd_mean=target, cl_mean=0.0, cm_mean=0, n_samples_averaged=1, averaging_window_fraction=0.25)
    report = compare_bem_to_cfd(bem_point, close_cfd)
    assert report.percent_error < 1.0
    assert report.within_engineering_tolerance is True


def test_straight_blade_stl_export_is_a_closed_solid():
    from app.cfd.stl_export import generate_blade_stl
    stl_text = generate_blade_stl(chord_m=0.09, thickness_ratio=0.18, span_m=1.2)
    assert stl_text.startswith("solid blade")
    assert stl_text.strip().endswith("endsolid blade")
    assert stl_text.count("facet normal") > 0


def test_twisted_helical_blade_stl_export_produces_more_geometry_than_straight():
    """A twisted/helical blade is lofted station-by-station, so it should
    produce meaningfully more triangles (side walls between stations) than
    the simple linear-extrusion straight-blade path."""
    from app.cfd.stl_export import generate_blade_stl
    straight = generate_blade_stl(chord_m=0.09, thickness_ratio=0.18, span_m=1.2)
    twisted = generate_blade_stl(
        chord_m=0.09, thickness_ratio=0.18, span_m=1.2,
        twist_angle_deg=10.0, helical_twist_deg=60.0, rotor_radius_m=0.6,
    )
    assert twisted.count("facet normal") > straight.count("facet normal")
    assert twisted.strip().endswith("endsolid blade")


def test_openfoam_case_readme_reports_actual_blade_shape():
    """The generated case README should describe the actual blade shape
    (straight vs twisted/helical) rather than a hardcoded 'not supported' note."""
    geom_straight = HybridRotorGeometry(name="Straight Case")
    geom_twisted = HybridRotorGeometry(name="Twisted Case")
    geom_twisted.darrieus.twist_angle_deg = 8.0
    geom_twisted.darrieus.helical_twist_deg = 45.0
    cfg = CFDCaseConfig(wind_speed_ms=8.0, tip_speed_ratio=2.25)

    zf_straight = zipfile.ZipFile(io.BytesIO(build_case_zip_bytes(geom_straight, cfg)))
    zf_twisted = zipfile.ZipFile(io.BytesIO(build_case_zip_bytes(geom_twisted, cfg)))

    readme_straight = zf_straight.read(
        [n for n in zf_straight.namelist() if n.endswith("README.md")][0]
    ).decode()
    readme_twisted = zf_twisted.read(
        [n for n in zf_twisted.namelist() if n.endswith("README.md")][0]
    ).decode()

    assert "not yet supported" not in readme_straight.lower()
    assert "not yet supported" not in readme_twisted.lower()
    assert "straight blade" in readme_straight.lower()
    assert "helical" in readme_twisted.lower() and "45.0" in readme_twisted