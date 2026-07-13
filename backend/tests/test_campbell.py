import pytest
from app.aeroelastic.campbell import build_campbell_diagram


def test_exact_resonance_crossing_is_detected_with_zero_margin():
    r = build_campbell_diagram([10.0], rpm_min=400, rpm_max=800, n_harmonics=3)
    exact = [risk for risk in r.resonance_risks if risk.margin_percent == 0.0]
    assert len(exact) == 1
    assert exact[0].harmonic_number == 1
    assert exact[0].excitation_rpm == pytest.approx(600.0)


def test_resonance_far_outside_range_is_not_flagged():
    # 3P resonance would occur at RPM=200, far outside [400,800] and outside the 10% margin
    r = build_campbell_diagram([10.0], rpm_min=400, rpm_max=800, n_harmonics=3, resonance_margin_percent=10.0)
    flagged_harmonics = [risk.harmonic_number for risk in r.resonance_risks]
    assert 3 not in flagged_harmonics


def test_no_natural_frequencies_gives_no_resonance_risks():
    r = build_campbell_diagram([], rpm_min=400, rpm_max=800)
    assert r.resonance_risks == []


def test_excitation_lines_scale_linearly_with_harmonic_number():
    r = build_campbell_diagram([10.0], rpm_min=100, rpm_max=200, n_harmonics=3, n_rpm_points=5)
    # At any given RPM, the 2P line should be exactly twice the 1P line
    for i in range(5):
        assert r.excitation_lines_hz[2][i] == pytest.approx(2 * r.excitation_lines_hz[1][i])
        assert r.excitation_lines_hz[3][i] == pytest.approx(3 * r.excitation_lines_hz[1][i])


def test_rpm_range_has_correct_endpoints():
    r = build_campbell_diagram([10.0], rpm_min=300, rpm_max=900, n_rpm_points=10)
    assert r.rpm_range[0] == pytest.approx(300.0)
    assert r.rpm_range[-1] == pytest.approx(900.0)
