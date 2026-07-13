"""
PDF design report generator using reportlab. A condensed single-document
summary (vs. DOCX's more narrative sectioning) -- the two formats serve
different purposes (PDF for quick sharing/printing, DOCX for further
editing), both rendering from the same ReportData.
"""
from __future__ import annotations
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.reporting.report_data import ReportData

ACCENT = colors.HexColor("#2563EB")


def _table(rows: list[tuple[str, str]]) -> Table:
    t = Table(rows, colWidths=[2.6 * inch, 3.4 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def generate_pdf_report(data: ReportData) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], textColor=ACCENT, fontSize=18)
    h_style = ParagraphStyle("H1Custom", parent=styles["Heading1"], textColor=ACCENT, fontSize=13, spaceBefore=14)
    body = styles["BodyText"]
    body.fontSize = 9.5
    body.leading = 13

    story = []
    story.append(Paragraph(f"Hybrid VAWT Design Report — {data.geometry.name}", title_style))
    story.append(Paragraph(
        f"Target: {data.geometry.target_power_w:.0f} W &nbsp;|&nbsp; Material: {data.material_key} "
        f"&nbsp;|&nbsp; Operating point: {data.wind_speed_ms:.1f} m/s, TSR {data.operating_tsr:.2f}",
        body,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Executive Summary", h_style))
    story.append(_table([
        ("Peak power coefficient (Cp)", f"{data.peak_cp:.3f} at TSR {data.peak_cp_tsr:.2f}"),
        ("Structural safety factor", f"{data.structural_safety_factor:.2f}"),
        ("Estimated fatigue life", f"{data.fatigue_life_years:,.0f} years" if data.fatigue_life_years < 1e6 else "1,000,000+ years"),
        ("AEP", f"{data.aep_kwh:,.0f} kWh/yr"),
        ("LCOE", f"${data.lcoe_usd_per_kwh:.3f}/kWh"),
        ("NPV (20-yr)", f"${data.npv_usd:,.0f}"),
    ]))

    story.append(Paragraph("Geometry", h_style))
    d, s = data.geometry.darrieus, data.geometry.savonius
    story.append(_table([
        ("Darrieus blades", str(d.num_blades)),
        ("Rotor radius", f"{d.rotor_radius_m:.3f} m"),
        ("Blade height", f"{d.blade_height_m:.3f} m"),
        ("Chord", f"{d.chord_m:.3f} m"),
        ("Solidity", f"{d.solidity:.3f}"),
        ("Savonius buckets", str(s.num_buckets)),
    ]))

    story.append(Paragraph("Structural (Stage 3) &amp; Composites (Stage 4)", h_style))
    story.append(_table([
        ("Spar mass", f"{data.spar_mass_kg:.3f} kg"),
        ("Combined max stress", f"{data.structural_max_stress_pa/1e6:.1f} MPa"),
        ("Max deflection", f"{data.structural_max_deflection_m*1000:.2f} mm"),
        ("Safety factor", f"{data.structural_safety_factor:.2f}"),
        ("CFRP spar mass", f"{data.composite_cfrp_mass_kg*1000:.0f} g ({'feasible' if data.composite_cfrp_feasible else 'infeasible'})"),
        ("GFRP spar mass", f"{data.composite_gfrp_mass_kg*1000:.0f} g ({'feasible' if data.composite_gfrp_feasible else 'infeasible'})"),
    ]))

    story.append(Paragraph("Fatigue (Stage 5) &amp; Aeroelasticity (Stage 6)", h_style))
    life_str = f"{data.fatigue_life_years:,.0f} years" if data.fatigue_life_years < 1e6 else "1,000,000+ years"
    freqs_str = ", ".join(f"{f:.1f} Hz" for f in data.natural_frequencies_hz)
    story.append(_table([
        ("Estimated fatigue life", life_str),
        ("Cycles per year", f"{data.fatigue_cycles_per_year/1e6:.1f} million"),
        ("Natural frequencies", freqs_str),
        ("Resonance risks in range", str(data.resonance_risks_count)),
    ]))

    story.append(Paragraph("Economics (Stage 7)", h_style))
    story.append(_table([
        ("AEP", f"{data.aep_kwh:,.0f} kWh/yr"),
        ("Capacity factor", f"{data.capacity_factor*100:.1f}%"),
        ("Total CAPEX", f"${data.total_capex_usd:,.0f}"),
        ("LCOE", f"${data.lcoe_usd_per_kwh:.3f}/kWh"),
        ("NPV (20-yr)", f"${data.npv_usd:,.0f}"),
        ("IRR", f"{data.irr*100:.1f}%" if data.irr is not None else "N/A"),
        ("Simple payback", f"{data.payback_years:.1f} years" if data.payback_years != float("inf") else "never"),
    ]))

    story.append(Paragraph("Warnings &amp; Assumptions", h_style))
    if data.warnings:
        items = [ListItem(Paragraph(w, body)) for w in data.warnings]
        story.append(ListFlowable(items, bulletType="bullet"))
    else:
        story.append(Paragraph("No warnings raised for this design.", body))

    doc.build(story)
    buf.seek(0)
    return buf.read()
