"""
Phase 12 multi-objective optimization: searches rotor geometry (radius,
blade height, chord, spar sizing) to trade off Annual Energy Production,
Levelized Cost of Energy, and blade mass -- the three objectives explicitly
named in the master spec ("maximise AEP... minimise blade weight...
minimise LCOE"), subject to a structural safety-factor constraint so the
Pareto front only contains designs that actually pass the Stage-3/4
structural check, not just aerodynamically/economically attractive ones
that would fail in service.

Uses pymoo (the library the master spec explicitly names) rather than a
from-scratch genetic algorithm -- pymoo's NSGA-II is well-tested and
correctly implements the standard algorithm (fast non-dominated sorting,
crowding distance, simulated binary crossover, polynomial mutation); a
hand-rolled GA at this point in the project would add implementation risk
for a component that already has a mature, correct open-source
implementation available.

Performance note: each objective evaluation runs the fast (Stage-1-speed)
BEM/structural/AEP pipeline -- not the full-fidelity versions used
elsewhere in this platform (e.g. CFD or the fine-grained fatigue sweep).
This is deliberate: a multi-objective search evaluates hundreds of
candidate designs, and using full-fidelity solvers per evaluation would
make the search impractically slow for an interactive tool. The resulting
Pareto front should be treated as a fast preview / design-space exploration
aid -- promising candidates should still go through the full Stage 2-7
pipeline (CFD validation, detailed fatigue life, etc.) before being trusted
for a final design decision. This mirrors the "Stage 1 fast search, Stage 2+
validation" philosophy used throughout this platform.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from pymoo.core.problem import Problem

from app.geometry.models import HybridRotorGeometry, DarrieusBladeGeometry, SavoniusBucketGeometry, ShaftGeometry
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material
from app.economics.economic_analysis import analyze_economics


@dataclass
class DesignVariableBounds:
    rotor_radius_m: tuple[float, float] = (0.3, 1.2)
    blade_height_m: tuple[float, float] = (0.6, 2.5)
    chord_m: tuple[float, float] = (0.05, 0.20)
    spar_width_fraction: tuple[float, float] = (0.2, 0.7)
    spar_wall_thickness_m: tuple[float, float] = (0.0015, 0.008)


def _build_geometry(x: np.ndarray, base: HybridRotorGeometry) -> tuple[HybridRotorGeometry, float, float]:
    radius, height, chord, spar_width_frac, wall_m = x
    darrieus = DarrieusBladeGeometry(
        num_blades=base.darrieus.num_blades, blade_height_m=float(height), rotor_radius_m=float(radius),
        chord_m=float(chord), airfoil=base.darrieus.airfoil,
        blade_thickness_ratio=base.darrieus.blade_thickness_ratio,
    )
    geom = HybridRotorGeometry(
        name=base.name, target_power_w=base.target_power_w, darrieus=darrieus,
        savonius=base.savonius, shaft=base.shaft,
        rated_wind_speed_ms=base.rated_wind_speed_ms,
        cut_in_wind_speed_ms=base.cut_in_wind_speed_ms, cut_out_wind_speed_ms=base.cut_out_wind_speed_ms,
    )
    return geom, float(spar_width_frac), float(wall_m)


class RotorDesignProblem(Problem):
    """
    3 objectives (all minimized internally, per pymoo convention -- AEP is
    negated so "minimize -AEP" is equivalent to "maximize AEP"):
        f1 = -AEP_kWh
        f2 = LCOE_usd_per_kwh
        f3 = blade_mass_kg
    1 constraint (g <= 0 feasible):
        g1 = target_safety_factor - safety_factor
    """

    def __init__(
        self, base_geometry: HybridRotorGeometry, material_key: str = "CFRP_UD",
        ply_material_key: str = "CFRP_UD_PLY", target_safety_factor: float = 1.5,
        operating_tsr: float = 2.25, bounds: DesignVariableBounds | None = None,
        weibull_k: float = 2.0, weibull_c: float = 7.0,
        electricity_price_usd_per_kwh: float = 0.15,
    ):
        self.base_geometry = base_geometry
        self.material_key = material_key
        self.ply_material_key = ply_material_key
        self.target_safety_factor = target_safety_factor
        self.operating_tsr = operating_tsr
        self.weibull_k = weibull_k
        self.weibull_c = weibull_c
        self.electricity_price_usd_per_kwh = electricity_price_usd_per_kwh
        b = bounds or DesignVariableBounds()

        xl = np.array([b.rotor_radius_m[0], b.blade_height_m[0], b.chord_m[0],
                        b.spar_width_fraction[0], b.spar_wall_thickness_m[0]])
        xu = np.array([b.rotor_radius_m[1], b.blade_height_m[1], b.chord_m[1],
                        b.spar_width_fraction[1], b.spar_wall_thickness_m[1]])

        # A coarse 8-point wind-speed sweep (vs. the default 25 used for a
        # final AEP report) -- sufficient resolution for comparing designs
        # relative to each other during search, at roughly 3x the speed.
        self._fast_wind_bins = [float(v) for v in np.linspace(
            base_geometry.cut_in_wind_speed_ms, base_geometry.cut_out_wind_speed_ms, 8
        )]

        super().__init__(n_var=5, n_obj=3, n_constr=1, xl=xl, xu=xu)

    def _evaluate(self, X, out, *args, **kwargs):
        from app.structural.blade_analysis import analyze_blade_structure

        n = X.shape[0]
        F = np.zeros((n, 3))
        G = np.zeros((n, 1))

        for i in range(n):
            geom, spar_width_frac, wall_m = _build_geometry(X[i], self.base_geometry)

            try:
                struct = analyze_blade_structure(
                    geom, self.material_key, geom.rated_wind_speed_ms, self.operating_tsr,
                    spar_width_fraction=spar_width_frac, spar_wall_thickness_m=wall_m,
                    n_elements=20,
                )
                mat = get_material(self.material_key)
                spar = spar_from_blade_geometry(
                    geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, spar_width_frac, wall_m,
                )
                spar_mass = spar.area_m2 * geom.darrieus.blade_height_m * mat.density_kg_m3

                econ = analyze_economics(
                    geom, spar_mass_kg=spar_mass, ply_material_key=self.ply_material_key,
                    electricity_price_usd_per_kwh=self.electricity_price_usd_per_kwh,
                    weibull_k=self.weibull_k, weibull_c=self.weibull_c,
                    aep_wind_bins_ms=self._fast_wind_bins,
                    aep_n_azimuth=20, aep_tsr_search_points=5,
                )

                F[i, 0] = -econ.aep.aep_kwh
                F[i, 1] = econ.lcoe_usd_per_kwh
                F[i, 2] = struct.spar_mass_kg
                G[i, 0] = self.target_safety_factor - struct.safety_factor
            except Exception:
                # A failed evaluation (e.g. degenerate geometry) is scored as
                # maximally infeasible/unattractive rather than crashing the
                # whole generation.
                F[i, :] = [0.0, 10.0, 100.0]
                G[i, 0] = 100.0

        out["F"] = F
        out["G"] = G
