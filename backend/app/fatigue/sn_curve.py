"""
S-N (stress-life) fatigue curve using the standard Basquin power-law form:
    N(S) = (S / S_ref)^(-m)     [with N=1 cycle defined at S=S_ref=static strength]
equivalently:  S(N) = S_ref * N^(-1/m)

`m` is the fatigue exponent (sometimes called the S-N slope parameter, or
1/b in Basquin's original stress-based notation). Representative values used
here (m~10 for CFRP, m~9 for GFRP UD laminates) are typical of published
composite fatigue data at R=0.1 (e.g. reviews summarizing wind-blade
coupon testing, such as Mandell & Samborsky's DOE/MSU composite material
fatigue database) -- but real design fatigue curves are laminate- and
resin-specific and should come from coupon testing, not a single assumed
exponent. This module is flagged accordingly everywhere it's used; it is
a first-pass estimate, appropriate for this platform's stated incremental,
non-final-certification scope.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SNCurve:
    static_strength_pa: float
    fatigue_exponent_m: float
    max_cycles_cap: float = 1e18  # numerical ceiling only, far beyond any physically relevant count

    def cycles_to_failure(self, stress_amplitude_pa: float) -> float:
        if stress_amplitude_pa <= 0:
            return float("inf")
        ratio = stress_amplitude_pa / self.static_strength_pa
        if ratio >= 1.0:
            return 1.0  # at or above static strength: failure on/before the first cycle
        n = ratio ** (-self.fatigue_exponent_m)
        # This ceiling exists only to prevent float overflow for extremely low
        # stress ratios (Basquin's power law can return astronomically large
        # N there) -- it must NOT act as a low-stress damage floor. Capping N
        # to a small "practical" value like 1e8 would be backwards: it would
        # make very-low-stress, very-high-cycle-count bins look artificially
        # MORE damaging (real cycles / artificially-small N), when physically
        # those cycles should contribute almost no damage at all. This bug
        # was caught during Phase 9 development: an earlier version capped
        # at 1e8 and predicted an obviously-wrong ~0.2 year fatigue life for
        # a lightly-loaded, well-margined blade.
        return min(n, self.max_cycles_cap)


# Representative fatigue exponents for the ply materials already defined in
# app/composites/lamina.py -- kept as a separate lookup (rather than adding
# fields to PlyMaterial) since fatigue exponents are a distinct, less
# certain property than the static/elastic properties used elsewhere.
FATIGUE_EXPONENTS = {
    "CFRP_UD_PLY": 10.0,
    "GFRP_UD_PLY": 9.0,
}


def get_sn_curve(ply_material_key: str, static_strength_pa: float) -> SNCurve:
    m = FATIGUE_EXPONENTS.get(ply_material_key, 9.0)
    return SNCurve(static_strength_pa=static_strength_pa, fatigue_exponent_m=m)
