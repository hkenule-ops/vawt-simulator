import pytest
from app.geometry.models import HybridRotorGeometry
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material
from app.aeroelastic.blade_aeroelastic_analysis import analyze_blade_aeroelastics


def _default_result(width_frac=0.5, wall_m=0.003, tsr=2.25):
    geom = HybridRotorGeometry()
    mat = get_material("CFRP_UD")
    spar = spar_from_blade_geometry(geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, width_frac, wall_m)
    EI = mat.youngs_modulus_pa * spar.i_flapwise_m4
    mass_per_length = spar.area_m2 * mat.density_kg_m3
    return analyze_blade_aeroelastics(geom, EI, mass_per_length, operating_tsr=tsr)


def test_aeroelastic_analysis_runs_and_returns_positive_frequencies():
    r = _default_result()
    assert all(f > 0 for f in r.modal.natural_frequencies_hz)
    assert r.modal.natural_frequencies_hz == sorted(r.modal.natural_frequencies_hz)


def test_operating_rpm_range_is_positive_and_ordered():
    r = _default_result()
    assert r.operating_rpm_min > 0
    assert r.operating_rpm_max > r.operating_rpm_min


def test_dominant_harmonic_is_1p_for_this_aero_model():
    """Given this platform's BEM azimuthal loading is dominated by the fundamental once-per-rev term."""
    r = _default_result()
    assert 1 in r.harmonics.dominant_harmonics
    assert r.harmonics.amplitude_n_m[0] > r.harmonics.amplitude_n_m[1]


def test_higher_ei_at_fixed_mass_raises_natural_frequency():
    """
    Isolate the actual physical relationship (f ~ sqrt(EI/mass_per_length))
    rather than changing spar width AND wall thickness together, which
    don't have a simple monotonic combined effect on frequency (mass can
    grow faster than stiffness) -- that was an invalid assumption in an
    earlier version of this test, not a bug in the analysis itself.
    """
    geom = HybridRotorGeometry()
    mass_per_length = 0.5
    r_soft = analyze_blade_aeroelastics(geom, ei_flapwise=1000.0, mass_per_length_kg_m=mass_per_length, operating_tsr=2.25)
    r_stiff = analyze_blade_aeroelastics(geom, ei_flapwise=4000.0, mass_per_length_kg_m=mass_per_length, operating_tsr=2.25)
    assert r_stiff.modal.natural_frequencies_hz[0] > r_soft.modal.natural_frequencies_hz[0]


def test_warnings_always_include_stationary_frequency_caveat():
    r = _default_result()
    assert any("non-rotating" in w.lower() or "stationary" in w.lower() for w in r.warnings)


def test_exact_resonance_triggers_warning_when_present():
    r = _default_result()
    if any(risk.margin_percent == 0.0 for risk in r.campbell.resonance_risks):
        assert any("resonance crossing detected" in w.lower() for w in r.warnings)
