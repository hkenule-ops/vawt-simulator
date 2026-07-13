"""
Phase 10 top-level aeroelastic analysis. Ties together:
  1. Modal analysis (natural frequencies) of the blade spar, reusing the
     same EI/mass-per-length inputs as Phase 7/8's structural analysis.
  2. The operating RPM range, derived from the Stage-1 BEM's cut-in/cut-out
     wind speeds at a fixed operating TSR (same simplification as Phase 9's
     fatigue analysis).
  3. A Campbell diagram flagging resonance risk between natural frequencies
     and NP excitation lines across that RPM range.
  4. Real harmonic content of the blade's aerodynamic loading (via FFT of
     the actual Stage-1 BEM azimuthal force trace at the rated operating
     point), cross-checked against the natural frequencies -- so the
     "which harmonics matter" question is answered from the platform's own
     aerodynamic model, not assumed to just be 1P.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.geometry.models import HybridRotorGeometry
from app.aero.darrieus_bem import compute_normal_force_azimuthal_trace
from app.aeroelastic.modal_analysis import solve_modal_analysis, ModalResult
from app.aeroelastic.campbell import build_campbell_diagram, CampbellResult
from app.aeroelastic.harmonic_content import compute_harmonic_content, HarmonicContent


@dataclass
class AeroelasticResult:
    modal: ModalResult
    campbell: CampbellResult
    harmonics: HarmonicContent
    operating_rpm_min: float
    operating_rpm_max: float
    warnings: list[str]


def analyze_blade_aeroelastics(
    geom: HybridRotorGeometry,
    ei_flapwise: float,
    mass_per_length_kg_m: float,
    operating_tsr: float,
    boundary: str = "pinned-pinned",
    n_modes: int = 4,
    n_azimuth: int = 144,
) -> AeroelasticResult:
    d = geom.darrieus

    modal = solve_modal_analysis(
        d.blade_height_m, ei_flapwise, mass_per_length_kg_m,
        boundary=boundary, n_modes=n_modes,
    )

    omega_min = operating_tsr * geom.cut_in_wind_speed_ms / d.rotor_radius_m
    omega_max = operating_tsr * geom.cut_out_wind_speed_ms / d.rotor_radius_m
    rpm_min = omega_min * 60 / (2 * 3.141592653589793)
    rpm_max = omega_max * 60 / (2 * 3.141592653589793)

    campbell = build_campbell_diagram(
        modal.natural_frequencies_hz, rpm_min=rpm_min, rpm_max=rpm_max, n_harmonics=6,
    )

    trace = compute_normal_force_azimuthal_trace(
        d, geom.rated_wind_speed_ms, operating_tsr, n_azimuth=n_azimuth,
    )
    harmonics = compute_harmonic_content(trace, n_harmonics=6)

    warnings = []
    exact_resonances = [r for r in campbell.resonance_risks if r.margin_percent == 0.0]
    if exact_resonances:
        details = ", ".join(f"mode {r.mode_number} ({r.natural_frequency_hz:.1f} Hz) at {r.harmonic_number}P"
                             for r in exact_resonances)
        warnings.append(f"Resonance crossing detected within the operating RPM range: {details}.")

    near_misses = [r for r in campbell.resonance_risks if 0 < r.margin_percent <= 10.0]
    if near_misses:
        warnings.append(
            f"{len(near_misses)} natural frequency/harmonic combination(s) fall within 10% of "
            f"the operating RPM range boundary -- worth checking if the design's RPM range "
            f"expands in the future."
        )

    dominant_and_resonant = set(harmonics.dominant_harmonics) & {r.harmonic_number for r in exact_resonances}
    if dominant_and_resonant:
        warnings.append(
            f"Harmonic(s) {sorted(dominant_and_resonant)} carry significant real aerodynamic "
            f"loading energy AND cross a natural frequency within the operating range -- "
            f"highest-priority resonance risk."
        )

    warnings.append(
        "Natural frequencies are non-rotating (stationary) values; centrifugal stiffening "
        "(which raises natural frequencies somewhat with RPM in reality) is not modelled -- "
        "see module docstring."
    )

    return AeroelasticResult(
        modal=modal, campbell=campbell, harmonics=harmonics,
        operating_rpm_min=rpm_min, operating_rpm_max=rpm_max,
        warnings=warnings,
    )
