"""
Lightweight airfoil polar model.

For Stage 1 (fast BEM-type optimisation across hundreds/thousands of candidate
geometries) we do not want to depend on external XFOIL polar files. Instead we
use a well-established analytical approximation:

- Pre-stall: thin-airfoil theory Cl = 2*pi*sin(alpha - alpha0), clipped to a
  realistic max slope for thick sections (symmetric NACA00xx blades commonly
  used on Darrieus rotors have alpha0 = 0).
- Post-stall (deep stall / flat-plate regime): Viterna-Corrigan extrapolation,
  which is the standard method used in wind turbine BEM codes (including
  NREL's AeroDyn) to extend a finite polar to +/-90 degrees.
- Drag: a simple parabolic profile-drag model pre-stall, blending into flat
  plate drag (Cd ~ 2*sin(alpha)) post-stall via the same Viterna-Corrigan form.

This module is intentionally isolated behind a small interface
(`AirfoilPolar.cl_cd(alpha_rad)`) so that Stage 2+ can swap in real XFOIL/
XFLR5-derived polar tables (CSV lookup) without changing the BEM solver.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass
class AirfoilPolar:
    name: str = "NACA0018"
    cl_alpha: float = 2 * math.pi   # lift-curve slope, 1/rad (thin airfoil theory)
    alpha_stall_deg: float = 14.0   # static stall angle (typical thick symmetric section)
    cl_max: float = 1.05            # typical for NACA0018 at Re ~ 1e5-3e5
    cd0: float = 0.0095             # zero-lift profile drag coefficient
    k_induced: float = 0.02         # parabolic drag polar coefficient: Cd = cd0 + k*Cl^2

    def cl_cd(self, alpha_rad: float) -> tuple[float, float]:
        """Return (Cl, Cd) at the given angle of attack in radians, valid -180..180 deg."""
        alpha_deg = math.degrees(alpha_rad)
        a_stall = self.alpha_stall_deg
        sign = 1.0 if alpha_deg >= 0 else -1.0
        a_abs = abs(alpha_deg)

        if a_abs <= a_stall:
            # Linear pre-stall region
            cl = self.cl_alpha * alpha_rad
            # clip to realistic cl_max approach near stall
            cl = max(min(cl, self.cl_max * 1.02), -self.cl_max * 1.02)
            cd = self.cd0 + self.k_induced * cl * cl
            return cl, cd
        else:
            # Viterna-Corrigan post-stall extrapolation
            cl_stall = self.cl_alpha * math.radians(a_stall)
            cl_stall = max(min(cl_stall, self.cl_max), -self.cl_max)
            cd_stall = self.cd0 + self.k_induced * cl_stall * cl_stall

            ar_proxy = 10.0  # effective aspect-ratio proxy for the A/B coefficients
            cd_max = 1.0 + 0.065 * ar_proxy
            a_rad = math.radians(a_abs)

            b1 = cd_max
            a1 = b1 / 2.0
            b2 = (cd_stall - cd_max * (math.sin(math.radians(a_stall)) ** 2)) / max(
                math.cos(math.radians(a_stall)), 1e-6
            )
            a2 = (cl_stall - cd_max * math.sin(math.radians(a_stall)) * math.cos(math.radians(a_stall))) / max(
                (math.cos(math.radians(a_stall)) ** 2), 1e-6
            )

            cl_ext = a1 * math.sin(2 * a_rad) + a2 * (math.cos(a_rad) ** 2) / max(math.sin(a_rad), 1e-6)
            cd_ext = b1 * (math.sin(a_rad) ** 2) + b2 * math.cos(a_rad)

            # Guard against numerical blow-up right at 90 deg singularity in cl_ext
            cl_ext = max(min(cl_ext, cl_max_guard := 1.5), -1.5)
            return sign * cl_ext, cd_ext


# Small built-in library; Stage 2 can extend this with XFOIL-derived entries.
AIRFOIL_LIBRARY = {
    "NACA0012": AirfoilPolar(name="NACA0012", alpha_stall_deg=12.0, cl_max=0.95, cd0=0.008, k_induced=0.018),
    "NACA0015": AirfoilPolar(name="NACA0015", alpha_stall_deg=13.0, cl_max=1.00, cd0=0.009, k_induced=0.019),
    "NACA0018": AirfoilPolar(name="NACA0018", alpha_stall_deg=14.0, cl_max=1.05, cd0=0.0095, k_induced=0.020),
}


def get_airfoil(name: str) -> AirfoilPolar:
    return AIRFOIL_LIBRARY.get(name, AIRFOIL_LIBRARY["NACA0018"])
