"""
Stage-2a aerodynamic solver: a 2D constant-strength vortex panel method for
the airfoil cross-section used by the Darrieus blades.

This is NOT a substitute for real CFD (no viscosity, no separation, no
Reynolds-number dependence) -- it is a fast, dependency-free, in-process
potential-flow solver that:
  1. Resolves real section geometry (thickness, curvature), unlike the
     Stage-1 analytical polar model (app/aero/airfoil.py), giving a genuine
     surface pressure distribution Cp(x/c) rather than a single Cl(alpha).
  2. Provides an intermediate consistency check on Stage-1 results before
     committing to a full OpenFOAM run (see openfoam_case_generator.py),
     which is expensive and requires OpenFOAM installed locally / on a
     cluster -- not available in this environment.
  3. Slots into the same "Stage 2 validation" API surface that will accept
     real OpenFOAM `forceCoeffs` output once available (results_parser.py),
     so the frontend/report code doesn't care which one produced the numbers.

Method: classic constant-strength vortex panel method (surface vorticity
distribution, one unknown circulation density gamma_j per panel, closed by
the Kutta condition gamma_1 = -gamma_N). Panel-to-panel influence
coefficients are computed by numerically integrating the elementary 2D
point-vortex Biot-Savart law along each panel (scipy.integrate.quad) rather
than hand-derived closed-form arctan expressions -- this trades a small
amount of speed for much lower risk of a sign/algebra error, which matters
more here than raw performance since this only runs on Pareto-optimal
candidates, not the full optimisation sweep.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import integrate

from app.cfd.airfoil_geometry import Panel, naca_panels


@dataclass
class PanelMethodResult:
    x_over_c: list[float]        # control point x-locations, upper then lower
    cp: list[float]              # surface pressure coefficient at each control point
    is_upper: list[bool]
    cl: float
    cl_thin_airfoil_theory: float  # 2*pi*sin(alpha), reference value for sanity comparison
    alpha_deg: float
    converged: bool


def _vortex_induced_velocity(px: float, py: float, panel: Panel) -> tuple[float, float]:
    """
    Velocity induced at point (px,py) by a unit-strength (gamma=1) constant
    vortex sheet covering the full length of `panel`, via direct numerical
    integration of the elementary 2D point-vortex law
        V = Gamma / (2*pi*r^2) * (-dy, dx)
    along the panel's arc length.
    """
    L = panel.length
    tx, ty = panel.tangent

    def integrand_u(s):
        dx = px - (panel.xa + s * tx)
        dy = py - (panel.ya + s * ty)
        r2 = dx * dx + dy * dy
        return -dy / (2 * np.pi * r2) if r2 > 1e-12 else 0.0

    def integrand_v(s):
        dx = px - (panel.xa + s * tx)
        dy = py - (panel.ya + s * ty)
        r2 = dx * dx + dy * dy
        return dx / (2 * np.pi * r2) if r2 > 1e-12 else 0.0

    u, _ = integrate.quad(integrand_u, 0.0, L, limit=50)
    v, _ = integrate.quad(integrand_v, 0.0, L, limit=50)
    return u, v


def solve_panel_method(
    thickness_ratio: float, alpha_deg: float, n_panels: int = 80,
) -> PanelMethodResult:
    panels = naca_panels(thickness_ratio, n_panels=n_panels)
    n = len(panels)
    alpha = np.radians(alpha_deg)
    V_inf = (np.cos(alpha), np.sin(alpha))  # unit freestream

    # Self-influence of a panel on its own control point: the classic
    # analytic limit of the constant-vortex-sheet self-induced normal
    # velocity is exactly 0 (no normal velocity from a straight sheet on
    # itself); the numerical quad integral above already returns ~0 there
    # because of the symmetric +/- cancellation, so no special-casing needed.

    A = np.zeros((n, n))
    for i, pi in enumerate(panels):
        ni = pi.outward_normal
        for j, pj in enumerate(panels):
            u, v = _vortex_induced_velocity(pi.xc, pi.yc, pj)
            A[i, j] = u * ni[0] + v * ni[1]

    b = np.array([-(V_inf[0] * p.outward_normal[0] + V_inf[1] * p.outward_normal[1]) for p in panels])

    # Kutta condition replaces the last equation: gamma_1 + gamma_N = 0
    A[-1, :] = 0.0
    A[-1, 0] = 1.0
    A[-1, -1] = 1.0
    b[-1] = 0.0

    try:
        gamma = np.linalg.solve(A, b)
        converged = True
    except np.linalg.LinAlgError:
        gamma, *_ = np.linalg.lstsq(A, b, rcond=None)
        converged = False

    # Surface tangential velocity at each control point = freestream tangential
    # component + self-induced tangential component from its own panel's
    # vortex strength (classic result: local surface speed = gamma_j for a
    # constant-strength vortex sheet, in the panel's own tangential direction),
    # plus the influence of every other panel.
    Vt = np.zeros(n)
    for i, pi in enumerate(panels):
        ti = pi.tangent
        Vt[i] = V_inf[0] * ti[0] + V_inf[1] * ti[1]
        for j, pj in enumerate(panels):
            u, v = _vortex_induced_velocity(pi.xc, pi.yc, pj)
            Vt[i] += gamma[j] * (u * ti[0] + v * ti[1])

    cp = 1 - Vt ** 2

    # Lift via the Kutta-Joukowski-consistent circulation sum (total bound
    # circulation = sum of gamma_j * panel length; Cl = 2*Gamma for unit
    # chord, unit V_inf -- standard panel-method normalisation).
    total_circulation = sum(gamma[j] * panels[j].length for j in range(n))
    # Kutta-Joukowski sign convention: with this class's tangent/circulation
    # sign convention, L' = -rho*V_inf*Gamma (not +), confirmed by checking
    # that the underlying Cp distribution already shows upper-surface suction
    # for alpha>0 (physically correct) while the naive +2*Gamma sum reported
    # the opposite sign -- i.e. the flow field was right, only this final
    # summation's sign was backwards.
    cl = -2 * total_circulation
    cl_thin = 2 * np.pi * np.sin(alpha)

    x_over_c = [p.xc for p in panels]
    is_upper = [bool(p.yc >= 0) for p in panels]  # symmetric section: upper surface has y >= 0

    return PanelMethodResult(
        x_over_c=x_over_c,
        cp=list(cp),
        is_upper=is_upper,
        cl=float(cl),
        cl_thin_airfoil_theory=float(cl_thin),
        alpha_deg=alpha_deg,
        converged=converged,
    )
