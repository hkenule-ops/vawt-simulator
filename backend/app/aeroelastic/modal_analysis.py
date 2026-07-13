"""
Modal analysis for the blade spar: natural frequencies and mode shapes via
the generalized eigenvalue problem K*phi = omega^2*M*phi, using the same
Euler-Bernoulli beam element family as Phase 7's static beam FEM (same
4x4 stiffness matrix), paired with the standard consistent mass matrix.

Validated in tests/test_modal_analysis.py against closed-form analytical
natural frequencies for uniform beams -- pinned-pinned (exact formula) and
cantilever (using the well-known beta_n*L eigenvalue roots from vibration
theory) -- the same standard applied to every solver in this platform.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.linalg import eigh

# Cantilever beam eigenvalue roots (beta_n * L) for the first 4 modes,
# standard tabulated values from Euler-Bernoulli cantilever vibration theory
# (e.g. Blevins, "Formulas for Natural Frequency and Mode Shape").
CANTILEVER_BETA_L_ROOTS = [1.875104, 4.694091, 7.854757, 10.995541]


@dataclass
class ModalResult:
    natural_frequencies_hz: list[float]
    mode_shapes: list[list[float]]  # each mode: transverse deflection at each node (normalized)
    x_m: list[float]


def _element_stiffness(EI: float, L: float) -> np.ndarray:
    return (EI / L ** 3) * np.array([
        [12, 6 * L, -12, 6 * L],
        [6 * L, 4 * L**2, -6 * L, 2 * L**2],
        [-12, -6 * L, 12, -6 * L],
        [6 * L, 2 * L**2, -6 * L, 4 * L**2],
    ])


def _element_mass(rho_a: float, L: float) -> np.ndarray:
    """Consistent mass matrix for an Euler-Bernoulli beam element, mass per unit length rho_a = rho*A."""
    return (rho_a * L / 420) * np.array([
        [156, 22 * L, 54, -13 * L],
        [22 * L, 4 * L**2, 13 * L, -3 * L**2],
        [54, 13 * L, 156, -22 * L],
        [-13 * L, -3 * L**2, -22 * L, 4 * L**2],
    ])


def solve_modal_analysis(
    length_m: float, EI: float, mass_per_length_kg_m: float,
    n_elements: int = 40, boundary: str = "pinned-pinned", n_modes: int = 4,
) -> ModalResult:
    n_nodes = n_elements + 1
    L_e = length_m / n_elements
    ndof = 2 * n_nodes

    K = np.zeros((ndof, ndof))
    M = np.zeros((ndof, ndof))
    k_e = _element_stiffness(EI, L_e)
    m_e = _element_mass(mass_per_length_kg_m, L_e)

    for e in range(n_elements):
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            for j in range(4):
                K[dofs[i], dofs[j]] += k_e[i, j]
                M[dofs[i], dofs[j]] += m_e[i, j]

    if boundary == "pinned-pinned":
        fixed_dofs = [0, ndof - 2]
    elif boundary == "cantilever":
        fixed_dofs = [0, 1]
    else:
        raise ValueError("boundary must be 'pinned-pinned' or 'cantilever'")

    free_dofs = [d for d in range(ndof) if d not in fixed_dofs]
    K_ff = K[np.ix_(free_dofs, free_dofs)]
    M_ff = M[np.ix_(free_dofs, free_dofs)]

    eigenvalues, eigenvectors = eigh(K_ff, M_ff)
    eigenvalues = np.clip(eigenvalues, 0, None)  # guard tiny negative numerical noise
    omegas = np.sqrt(eigenvalues)
    freqs_hz = omegas / (2 * np.pi)

    n_modes = min(n_modes, len(freqs_hz))
    x = np.linspace(0, length_m, n_nodes)

    mode_shapes = []
    for m in range(n_modes):
        full_vec = np.zeros(ndof)
        full_vec[free_dofs] = eigenvectors[:, m]
        deflection = full_vec[0::2]
        max_abs = np.max(np.abs(deflection))
        if max_abs > 1e-12:
            deflection = deflection / max_abs  # normalize to unit peak amplitude
        mode_shapes.append(list(deflection))

    return ModalResult(
        natural_frequencies_hz=list(freqs_hz[:n_modes]),
        mode_shapes=mode_shapes,
        x_m=list(x),
    )
