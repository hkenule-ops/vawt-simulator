"""
Harmonic content of the actual aerodynamic excitation, via FFT of the
per-revolution azimuthal normal-force trace already computed by the Stage-1
BEM solver (app/aero/darrieus_bem.py). This is what makes the resonance
check in this phase data-driven rather than assumption-driven: rather than
just assuming "1P is the dominant excitation" (a common simplification),
this reads the harmonic content directly off the platform's own aerodynamic
model, which is not a pure sinusoid (lift/drag nonlinearity and stall mean
2P, 3P etc. carry real energy too -- confirmed, not assumed, by the FFT).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class HarmonicContent:
    harmonic_number: list[int]     # 1P, 2P, 3P, ...
    amplitude_n_m: list[float]     # amplitude of each harmonic, per unit span
    dominant_harmonics: list[int]  # harmonics carrying >5% of the total spectral energy


def compute_harmonic_content(azimuthal_trace: np.ndarray, n_harmonics: int = 8) -> HarmonicContent:
    """
    azimuthal_trace: one full revolution of a periodic per-unit-span load
    (e.g. from compute_normal_force_azimuthal_trace), uniformly sampled.
    """
    n = len(azimuthal_trace)
    fft_vals = np.fft.rfft(azimuthal_trace - np.mean(azimuthal_trace))
    amplitudes = 2.0 * np.abs(fft_vals) / n

    n_harmonics = min(n_harmonics, len(amplitudes) - 1)
    harmonic_numbers = list(range(1, n_harmonics + 1))
    harmonic_amplitudes = [float(amplitudes[h]) for h in harmonic_numbers]

    total_energy = sum(a ** 2 for a in harmonic_amplitudes)
    dominant = [
        h for h, a in zip(harmonic_numbers, harmonic_amplitudes)
        if total_energy > 0 and (a ** 2 / total_energy) > 0.05
    ]

    return HarmonicContent(
        harmonic_number=harmonic_numbers,
        amplitude_n_m=harmonic_amplitudes,
        dominant_harmonics=dominant,
    )
