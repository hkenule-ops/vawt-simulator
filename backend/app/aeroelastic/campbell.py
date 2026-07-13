"""
Campbell diagram: overlays the blade's natural frequencies (from modal
analysis) against the rotor's excitation frequencies (NP lines -- N times
per revolution, N=1,2,3...) across the operating RPM range, and flags any
crossing within the operating range as a resonance risk.

Simplification flagged explicitly: natural frequencies here are the
non-rotating (stationary) values from modal_analysis.py. A real rotating
blade shows centrifugal stiffening -- natural frequencies increase somewhat
with RPM (the classic turbomachinery "fan plot" effect) -- which isn't
modelled here. Using stationary frequencies is a reasonably conservative
simplification for a first-pass resonance check (it doesn't shift the
natural frequency lines upward the way rotation would), but isn't a
substitute for a full rotating-frame (Coriolis + centrifugal stiffening)
analysis before final design sign-off.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ResonanceRisk:
    mode_number: int
    natural_frequency_hz: float
    harmonic_number: int
    excitation_rpm: float
    margin_percent: float


@dataclass
class CampbellResult:
    rpm_range: list[float]
    natural_frequencies_hz: list[float]
    excitation_lines_hz: dict[int, list[float]]  # harmonic number -> frequency at each RPM
    resonance_risks: list[ResonanceRisk]


def build_campbell_diagram(
    natural_frequencies_hz: list[float],
    rpm_min: float, rpm_max: float,
    n_harmonics: int = 6,
    n_rpm_points: int = 30,
    resonance_margin_percent: float = 10.0,
) -> CampbellResult:
    rpm_range = [rpm_min + i * (rpm_max - rpm_min) / (n_rpm_points - 1) for i in range(n_rpm_points)]

    excitation_lines = {}
    for h in range(1, n_harmonics + 1):
        excitation_lines[h] = [rpm * h / 60.0 for rpm in rpm_range]

    resonance_risks: list[ResonanceRisk] = []
    for mode_idx, f_n in enumerate(natural_frequencies_hz):
        for h in range(1, n_harmonics + 1):
            # RPM at which this harmonic's excitation frequency equals f_n:
            # h * rpm / 60 = f_n  =>  rpm = 60 * f_n / h
            rpm_at_resonance = 60.0 * f_n / h
            if rpm_min <= rpm_at_resonance <= rpm_max:
                margin = 0.0  # exact crossing within range
                resonance_risks.append(ResonanceRisk(
                    mode_number=mode_idx + 1, natural_frequency_hz=f_n,
                    harmonic_number=h, excitation_rpm=rpm_at_resonance, margin_percent=margin,
                ))
            else:
                # also flag near-misses within resonance_margin_percent of the operating range edge
                nearest_edge = rpm_min if rpm_at_resonance < rpm_min else rpm_max
                if nearest_edge > 0:
                    pct_off = abs(rpm_at_resonance - nearest_edge) / nearest_edge * 100
                    if pct_off <= resonance_margin_percent:
                        resonance_risks.append(ResonanceRisk(
                            mode_number=mode_idx + 1, natural_frequency_hz=f_n,
                            harmonic_number=h, excitation_rpm=rpm_at_resonance, margin_percent=pct_off,
                        ))

    return CampbellResult(
        rpm_range=rpm_range,
        natural_frequencies_hz=list(natural_frequencies_hz),
        excitation_lines_hz=excitation_lines,
        resonance_risks=resonance_risks,
    )
