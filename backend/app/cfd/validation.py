"""
Compares CFD results (from results_parser.py, sourced from either a real
OpenFOAM run or the in-sandbox panel-method proxy) against the Stage-1 BEM
prediction for the same operating point, and quantifies the discrepancy --
the explicit "Compare CFD against BEM predictions and quantify error"
requirement from the master spec.

Honesty note on scope: forceCoeffs output averaged over a revolution gives a
mean resultant blade force magnitude, not a phase-resolved torque history, so
the comparison implemented here is a first-order loading-magnitude check
(BEM's momentum-theory thrust coefficient vs CFD's mean resultant force
coefficient) -- the standard first sanity check in published VAWT CFD
validation studies before doing a full phase-resolved torque comparison.
A phase-resolved comparison is a natural extension once real OpenFOAM
per-timestep output is available (this sandbox cannot produce that; see
openfoam_case_generator.py docstring).
"""
from __future__ import annotations
from dataclasses import dataclass
import math

from app.aero.darrieus_bem import DarrieusOperatingPoint
from app.cfd.results_parser import CFDAveragedResult


@dataclass
class ValidationReport:
    bem_ct: float
    cfd_ct_equivalent: float
    percent_error: float
    bem_power_w: float
    within_engineering_tolerance: bool  # <15% is the common rule-of-thumb threshold cited in VAWT BEM-vs-CFD literature
    notes: str


def compare_bem_to_cfd(
    bem_point: DarrieusOperatingPoint, cfd_result: CFDAveragedResult,
) -> ValidationReport:
    cfd_resultant_c = math.hypot(cfd_result.cd_mean, cfd_result.cl_mean)
    bem_ct = bem_point.ct_thrust_coeff

    if bem_ct == 0:
        percent_error = float("inf")
    else:
        percent_error = 100.0 * abs(cfd_resultant_c - bem_ct) / abs(bem_ct)

    within_tol = percent_error <= 15.0

    notes = (
        "First-order loading-magnitude comparison (BEM momentum-theory thrust "
        "coefficient vs CFD revolution-averaged resultant force coefficient). "
        "Not a phase-resolved torque comparison -- see module docstring."
    )

    return ValidationReport(
        bem_ct=bem_ct,
        cfd_ct_equivalent=cfd_resultant_c,
        percent_error=percent_error,
        bem_power_w=bem_point.power_w,
        within_engineering_tolerance=within_tol,
        notes=notes,
    )
