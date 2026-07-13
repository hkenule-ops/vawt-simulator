"""
Euler-Bernoulli beam finite element solver for the Darrieus blade spar under
static aerodynamic + centrifugal loading.

Standard 2-DOF-per-node (transverse displacement w, rotation theta) cubic
Hermite beam element, assembled into a global stiffness matrix, solved for a
simply-supported (pinned-pinned) beam -- the standard conservative
idealisation for an H-Darrieus straight blade supported by struts near each
end. Cantilever boundary conditions are also provided for blade
configurations without a tip strut.

Validated in tests/test_structural.py against the closed-form solution for a
uniformly-loaded simply-supported beam (max deflection = 5wL^4/384EI, max
moment = wL^2/8) -- this is the same rigor applied to the BEM and panel-
method solvers: don't trust a FEM implementation just because it runs,
check it against a known analytical answer.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class BeamFEAResult:
    x_m: list[float]                 # node positions along span
    deflection_m: list[float]        # transverse deflection at each node
    bending_moment_nm: list[float]   # bending moment at each node
    max_deflection_m: float
    max_deflection_location_m: float
    max_bending_moment_nm: float
    max_bending_stress_pa: float
    max_stress_location_m: float


def _element_stiffness(EI: float, L: float) -> np.ndarray:
    """Standard 4x4 Euler-Bernoulli beam element stiffness matrix, DOF order [w1,theta1,w2,theta2]."""
    return (EI / L ** 3) * np.array([
        [12,      6 * L,   -12,     6 * L],
        [6 * L,   4 * L**2, -6 * L,  2 * L**2],
        [-12,    -6 * L,    12,    -6 * L],
        [6 * L,   2 * L**2, -6 * L,  4 * L**2],
    ])


def _element_load_vector(w0: float, L: float) -> np.ndarray:
    """Equivalent nodal load vector for a uniform distributed load w0 (N/m) over the element."""
    return np.array([
        w0 * L / 2,
        w0 * L ** 2 / 12,
        w0 * L / 2,
        -w0 * L ** 2 / 12,
    ])


def solve_beam_udl(
    length_m: float, EI: float, distributed_load_n_m: float,
    n_elements: int = 40, boundary: str = "pinned-pinned",
    section_i_m4: float | None = None, section_c_m: float | None = None,
) -> BeamFEAResult:
    """
    Solve a uniform beam of given length and bending stiffness EI under a
    uniform distributed transverse load, with either pinned-pinned or
    cantilever (fixed at x=0, free at x=L) boundary conditions.
    """
    n_nodes = n_elements + 1
    L_e = length_m / n_elements
    ndof = 2 * n_nodes

    K = np.zeros((ndof, ndof))
    F = np.zeros(ndof)
    k_e = _element_stiffness(EI, L_e)
    f_e = _element_load_vector(distributed_load_n_m, L_e)

    for e in range(n_elements):
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            F[dofs[i]] += f_e[i]
            for j in range(4):
                K[dofs[i], dofs[j]] += k_e[i, j]

    if boundary == "pinned-pinned":
        fixed_dofs = [0, ndof - 2]  # w=0 at both ends, rotations free
    elif boundary == "cantilever":
        fixed_dofs = [0, 1]  # w=0 and theta=0 at the root, free tip
    else:
        raise ValueError("boundary must be 'pinned-pinned' or 'cantilever'")

    free_dofs = [d for d in range(ndof) if d not in fixed_dofs]
    K_ff = K[np.ix_(free_dofs, free_dofs)]
    F_f = F[free_dofs]
    d_f = np.linalg.solve(K_ff, F_f)

    d = np.zeros(ndof)
    d[free_dofs] = d_f

    deflection = d[0::2]
    x = np.linspace(0, length_m, n_nodes)

    # Recover internal bending moment at each node via M = EI * d2w/dx2,
    # computed from the element's internal force vector (k_e @ d_e - f_e),
    # which correctly accounts for the distributed load within each element
    # (not just nodal reactions from a plain stiffness-only recovery).
    moment_left = np.zeros(n_elements)
    moment_right = np.zeros(n_elements)
    for e in range(n_elements):
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        d_e = d[dofs]
        internal = k_e @ d_e - f_e
        # internal = [V1, M1, V2, M2] using the standard beam sign convention
        moment_left[e] = internal[1]
        moment_right[e] = -internal[3]

    moment_at_nodes = np.zeros(n_nodes)
    moment_at_nodes[0] = moment_left[0]
    moment_at_nodes[-1] = moment_right[-1]
    for i in range(1, n_nodes - 1):
        moment_at_nodes[i] = 0.5 * (moment_right[i - 1] + moment_left[i])

    max_defl_idx = int(np.argmax(np.abs(deflection)))
    max_moment_idx = int(np.argmax(np.abs(moment_at_nodes)))
    max_moment = float(moment_at_nodes[max_moment_idx])

    c = section_c_m if section_c_m is not None else 0.0
    I = section_i_m4 if section_i_m4 is not None else 0.0
    max_stress = (abs(max_moment) * c / I) if I > 0 else 0.0

    return BeamFEAResult(
        x_m=list(x),
        deflection_m=list(deflection),
        bending_moment_nm=list(moment_at_nodes),
        max_deflection_m=float(deflection[max_defl_idx]),
        max_deflection_location_m=float(x[max_defl_idx]),
        max_bending_moment_nm=max_moment,
        max_bending_stress_pa=max_stress,
        max_stress_location_m=float(x[max_moment_idx]),
    )
