import numpy as np
import pytest
from app.aeroelastic.harmonic_content import compute_harmonic_content


def test_fft_recovers_exact_amplitudes_of_synthetic_multiharmonic_signal():
    theta = np.linspace(0, 2 * np.pi, 144, endpoint=False)
    signal = 3.0 * np.sin(theta) + 1.2 * np.sin(2 * theta) + 0.4 * np.sin(3 * theta)
    h = compute_harmonic_content(signal, n_harmonics=5)
    assert h.amplitude_n_m[0] == pytest.approx(3.0, rel=1e-6)
    assert h.amplitude_n_m[1] == pytest.approx(1.2, rel=1e-6)
    assert h.amplitude_n_m[2] == pytest.approx(0.4, rel=1e-6)
    assert h.amplitude_n_m[3] == pytest.approx(0.0, abs=1e-9)


def test_pure_first_harmonic_signal_has_only_1p_dominant():
    theta = np.linspace(0, 2 * np.pi, 144, endpoint=False)
    signal = 5.0 * np.sin(theta)
    h = compute_harmonic_content(signal, n_harmonics=5)
    assert h.dominant_harmonics == [1]


def test_low_energy_harmonic_excluded_from_dominant_list():
    theta = np.linspace(0, 2 * np.pi, 144, endpoint=False)
    signal = 10.0 * np.sin(theta) + 0.1 * np.sin(4 * theta)  # 4P carries negligible energy
    h = compute_harmonic_content(signal, n_harmonics=5)
    assert 4 not in h.dominant_harmonics


def test_constant_signal_has_zero_harmonic_amplitudes():
    signal = np.full(144, 7.0)
    h = compute_harmonic_content(signal, n_harmonics=4)
    assert all(a == pytest.approx(0.0, abs=1e-9) for a in h.amplitude_n_m)
