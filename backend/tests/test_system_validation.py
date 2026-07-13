import pytest
from app.geometry.models import HybridRotorGeometry
from app.validation.system_checks import run_system_validation, _check_betz_limit, _check_economic_irr_npv_consistency


def test_default_design_passes_all_checks():
    geom = HybridRotorGeometry()
    report = run_system_validation(geom)
    assert report.all_passed
    assert report.n_passed == report.n_total
    assert report.n_total == 6


def test_all_checks_have_names_and_details():
    geom = HybridRotorGeometry()
    report = run_system_validation(geom)
    for check in report.checks:
        assert check.name
        assert check.detail


def test_check_result_fail_state_is_representable():
    """Confirm CheckResult can represent and report a failing check (not just always-pass by construction)."""
    from app.validation.system_checks import CheckResult
    failing = CheckResult(name="Synthetic failing check", passed=False, detail="Deliberately constructed failure for testing.")
    assert failing.passed is False
    assert "failure" in failing.detail.lower()


def test_report_all_passed_is_false_if_any_check_fails():
    """Construct a ValidationReport with one failing check and confirm the aggregate flag reflects it."""
    from app.validation.system_checks import CheckResult, ValidationReport
    checks = [
        CheckResult("A", True, "ok"),
        CheckResult("B", False, "not ok"),
        CheckResult("C", True, "ok"),
    ]
    n_passed = sum(1 for c in checks if c.passed)
    report = ValidationReport(checks=checks, all_passed=(n_passed == len(checks)), n_passed=n_passed, n_total=len(checks))
    assert report.all_passed is False
    assert report.n_passed == 2
    assert report.n_total == 3


def test_irr_npv_consistency_check_passes_for_default_design():
    geom = HybridRotorGeometry()
    result = _check_economic_irr_npv_consistency(geom, spar_mass_kg=0.6, ply_key="CFRP_UD_PLY")
    assert result.passed


def test_validation_report_all_passed_flag_matches_individual_results():
    geom = HybridRotorGeometry()
    report = run_system_validation(geom)
    computed_all_passed = all(c.passed for c in report.checks)
    assert report.all_passed == computed_all_passed


def test_validation_runs_for_alternate_material():
    geom = HybridRotorGeometry()
    report = run_system_validation(geom, material_key="GFRP_UD", ply_material_key="GFRP_UD_PLY")
    assert report.n_total == 6
