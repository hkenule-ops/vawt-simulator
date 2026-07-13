"""
CSV export -- plain tabular data, no narrative, for import into other
tools (Excel, MATLAB, Python/pandas, etc). Two tables concatenated with a
blank-line separator: a summary key-value table and the full Cp-lambda curve.
"""
from __future__ import annotations
import csv
import io

from app.reporting.report_data import ReportData


def generate_csv_export(data: ReportData) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["Hybrid VAWT Design Report", data.geometry.name])
    writer.writerow([])
    writer.writerow(["Parameter", "Value"])
    writer.writerow(["Target power (W)", data.geometry.target_power_w])
    writer.writerow(["Material", data.material_key])
    writer.writerow(["Peak Cp", round(data.peak_cp, 4)])
    writer.writerow(["Peak Cp TSR", round(data.peak_cp_tsr, 3)])
    writer.writerow(["Structural safety factor", round(data.structural_safety_factor, 3)])
    writer.writerow(["Max stress (MPa)", round(data.structural_max_stress_pa / 1e6, 2)])
    writer.writerow(["Max deflection (mm)", round(data.structural_max_deflection_m * 1000, 3)])
    writer.writerow(["Spar mass (kg)", round(data.spar_mass_kg, 4)])
    writer.writerow(["CFRP spar mass (g)", round(data.composite_cfrp_mass_kg * 1000, 1)])
    writer.writerow(["GFRP spar mass (g)", round(data.composite_gfrp_mass_kg * 1000, 1)])
    writer.writerow(["Fatigue life (years)", data.fatigue_life_years if data.fatigue_life_years < 1e6 else "1000000+"])
    writer.writerow(["AEP (kWh/yr)", round(data.aep_kwh, 1)])
    writer.writerow(["Capacity factor", round(data.capacity_factor, 4)])
    writer.writerow(["Total CAPEX (USD)", round(data.total_capex_usd, 2)])
    writer.writerow(["LCOE (USD/kWh)", round(data.lcoe_usd_per_kwh, 4)])
    writer.writerow(["NPV (USD)", round(data.npv_usd, 2)])
    writer.writerow(["IRR", round(data.irr, 4) if data.irr is not None else "N/A"])

    writer.writerow([])
    writer.writerow(["Cp-Lambda Curve"])
    writer.writerow(["Tip-Speed Ratio", "System Cp", "Total Power (W)", "Induction Factor"])
    for p in data.cp_lambda_points:
        writer.writerow([round(p.tip_speed_ratio, 3), round(p.system_cp, 4),
                          round(p.total_power_w, 1), round(p.induction_factor, 4)])

    return buf.getvalue().encode("utf-8")
