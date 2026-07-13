"""
Airfoil surface geometry for the panel-method solver: generates panel boundary
points for a symmetric NACA00XX section using the standard analytic thickness
distribution, with cosine spacing (clusters points near the leading and
trailing edges, where curvature and pressure gradients are steepest).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


def naca00xx_half_thickness(x: np.ndarray, thickness_ratio: float) -> np.ndarray:
    """Standard NACA 4-digit symmetric thickness distribution, y_t(x), x in [0,1]."""
    t = thickness_ratio
    x = np.clip(x, 0.0, 1.0)
    return 5 * t * (
        0.2969 * np.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x ** 2
        + 0.2843 * x ** 3
        - 0.1015 * x ** 4
    )


@dataclass
class Panel:
    xa: float
    ya: float
    xb: float
    yb: float

    @property
    def xc(self) -> float:
        return 0.5 * (self.xa + self.xb)

    @property
    def yc(self) -> float:
        return 0.5 * (self.ya + self.yb)

    @property
    def length(self) -> float:
        return float(np.hypot(self.xb - self.xa, self.yb - self.ya))

    @property
    def tangent(self) -> tuple[float, float]:
        L = self.length
        return (self.xb - self.xa) / L, (self.yb - self.ya) / L

    @property
    def outward_normal(self) -> tuple[float, float]:
        """
        Normal obtained by rotating the tangent +90 degrees, which points
        outward for this class's trailing-edge-seamed, upper-surface-first
        traversal direction (verified numerically: positive angle of attack
        must produce positive lift, checked by an automated test).
        """
        tx, ty = self.tangent
        return -ty, tx


def naca_panels(thickness_ratio: float, n_panels: int = 80, chord: float = 1.0) -> list[Panel]:
    """
    Build `n_panels` boundary panels around a closed NACA00XX section using
    cosine spacing, traversed trailing-edge -> upper surface -> leading edge
    -> lower surface -> trailing edge (a closed loop that starts AND ends at
    the trailing edge). This matters: the Kutta condition ties together the
    two panels adjacent to the loop's seam (panel[0] and panel[-1]), and the
    Kutta condition is only physically meaningful at the trailing edge -- if
    the seam were placed at the leading edge instead (an earlier version of
    this function did exactly that), the solver still runs and "converges"
    numerically but enforces the wrong physical condition, silently breaking
    the fore-aft symmetry a symmetric airfoil must have at alpha=0.
    """
    n_pts = n_panels + 1
    theta = np.linspace(0, 2 * np.pi, n_pts)
    x_raw = 0.5 * (1 + np.cos(theta))  # TE (x=1) at theta=0, LE (x=0) at theta=pi, back to TE at 2pi

    xs = np.empty(n_pts)
    ys = np.empty(n_pts)
    for i, th in enumerate(theta):
        x = x_raw[i]
        yt = naca00xx_half_thickness(np.array([x]), thickness_ratio)[0]
        if th <= np.pi:
            xs[i], ys[i] = x, yt      # upper surface (TE -> LE)
        else:
            xs[i], ys[i] = x, -yt     # lower surface (LE -> TE)

    xs *= chord
    ys *= chord

    panels = []
    for i in range(n_panels):
        panels.append(Panel(xa=xs[i], ya=ys[i], xb=xs[i + 1], yb=ys[i + 1]))
    return panels
