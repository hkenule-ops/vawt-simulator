"""
Parses OpenFOAM `forceCoeffs` function-object output
(postProcessing/forceCoeffs1/0/coefficient.dat, tab-separated, with a
'#'-prefixed header row) into structured time-series data, and computes
revolution-averaged coefficients -- the standard way to report VAWT CFD
results, since instantaneous Cl/Cd/Cm oscillate strongly with blade azimuth
and only make sense averaged over a full rotation once the flow field has
become periodic (typically after 3-4 revolutions from a cold start).
"""
from __future__ import annotations
from dataclasses import dataclass
import io


@dataclass
class ForceCoeffsTimeSeries:
    time: list[float]
    cd: list[float]
    cl: list[float]
    cm: list[float]


@dataclass
class CFDAveragedResult:
    cd_mean: float
    cl_mean: float
    cm_mean: float
    n_samples_averaged: int
    averaging_window_fraction: float


def parse_force_coeffs(text: str) -> ForceCoeffsTimeSeries:
    """
    Expected column layout (OpenFOAM forceCoeffs function object, common
    versions): Time Cd Cd(f) Cd(r) Cl Cl(f) Cl(r) CmPitch ...
    We only need Time, Cd, Cl, CmPitch; column order is header-driven so we
    don't hard-code positions beyond identifying the labelled columns.
    """
    time, cd, cl, cm = [], [], [], []
    header_cols: list[str] | None = None

    for line in io.StringIO(text):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            # header lines look like: # Time Cd Cd(f) Cd(r) Cl Cl(f) Cl(r) CmPitch ...
            tokens = line.lstrip("#").split()
            if tokens and tokens[0] == "Time":
                header_cols = tokens
            continue
        if header_cols is None:
            # Fall back to the common default column order if no header found.
            header_cols = ["Time", "Cd", "Cd(f)", "Cd(r)", "Cl", "Cl(f)", "Cl(r)", "CmPitch"]
        parts = line.split()
        if len(parts) < len(header_cols):
            continue
        row = dict(zip(header_cols, parts))
        try:
            time.append(float(row["Time"]))
            cd.append(float(row["Cd"]))
            cl.append(float(row["Cl"]))
            cm.append(float(row.get("CmPitch", row.get("Cm", 0.0))))
        except (KeyError, ValueError):
            continue

    return ForceCoeffsTimeSeries(time=time, cd=cd, cl=cl, cm=cm)


def average_last_fraction(series: ForceCoeffsTimeSeries, fraction: float = 0.25) -> CFDAveragedResult:
    """
    Average over the last `fraction` of the time series (default: last 25%),
    which for a well-set-up run of several revolutions captures roughly the
    final revolution once startup transients have died out.
    """
    n = len(series.time)
    if n == 0:
        return CFDAveragedResult(0.0, 0.0, 0.0, 0, fraction)
    start_idx = max(0, int(n * (1 - fraction)))
    window_cd = series.cd[start_idx:]
    window_cl = series.cl[start_idx:]
    window_cm = series.cm[start_idx:]
    m = len(window_cd) or 1
    return CFDAveragedResult(
        cd_mean=sum(window_cd) / m,
        cl_mean=sum(window_cl) / m,
        cm_mean=sum(window_cm) / m,
        n_samples_averaged=m,
        averaging_window_fraction=fraction,
    )
