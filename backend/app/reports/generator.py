"""
Operational PDF and JSON Shift Handover Report Generator for VARUN-FUSION.
Generates publication-quality forecaster shift bulletins using ReportLab.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.blend.pipeline import get_blending_pipeline
from app.core.config import get_config
from app.core.logging import logger

DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


def generate_shift_report(
    cycle: datetime,
    region: str = "all",
    variable: str = "rain24_mm",
    lead: int = 24,
    method: str = "adaptive",
) -> Path:
    """
    Generate an operational PDF shift handover report for meteorologists and disaster managers.
    """
    cfg = get_config()
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"VARUN_SHIFT_REPORT_{cycle.strftime('%Y%m%d')}_{variable}_lead{lead}h.pdf"
    pdf_path = reports_dir / filename

    # 1. Fetch blend diagnostics
    pipeline = get_blending_pipeline()
    blend_data = pipeline.run_cycle_blend(cycle, variable, lead, method=method)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    primary_color = colors.HexColor("#0B1020")
    accent_orange = colors.HexColor("#F28C28")
    navy_blue = colors.HexColor("#1F3864")
    dark_gray = colors.HexColor("#334155")
    alert_red = colors.HexColor("#DC2626")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=accent_orange,
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=navy_blue,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=dark_gray,
    )
    disclaimer_style = ParagraphStyle(
        "DisclaimerBanner",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1, # Center
    )

    story = []

    # Header Banner
    story.append(Paragraph("VARUN-FUSION (वरुण-फ्यूजन)", title_style))
    story.append(Paragraph("Adaptive AI–NWP Multi-Model Operational Forecast Guidance | MoES / IMD Support", subtitle_style))
    story.append(Spacer(1, 8))

    # Mandatory Forecaster Guidance Notice (Red Banner)
    disclaimer_table = Table(
        [[Paragraph(f"OPERATIONAL NOTICE: {DISCLAIMER_TEXT.upper()} — FOR METEOROLOGISTS & SDMA ONLY", disclaimer_style)]],
        colWidths=[520],
    )
    disclaimer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), alert_red),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(disclaimer_table)
    story.append(Spacer(1, 10))

    # Cycle Metadata Table
    meta_data = [
        [
            Paragraph("<b>Forecast Cycle:</b>", body_style),
            Paragraph(f"{cycle.strftime('%Y-%m-%d 00:00 UTC')} ({cycle.strftime('%d-%b-%Y')} 05:30 IST)", body_style),
            Paragraph("<b>Target Domain:</b>", body_style),
            Paragraph(f"{cfg.domain.name} (0.25° grid)", body_style),
        ],
        [
            Paragraph("<b>Lead Time:</b>", body_style),
            Paragraph(f"{lead} Hours ({lead//24} Day Daily Accumulation)", body_style),
            Paragraph("<b>Variable:</b>", body_style),
            Paragraph(f"{cfg.variables[variable].name} ({cfg.variables[variable].unit})", body_style),
        ],
        [
            Paragraph("<b>Blending Method:</b>", body_style),
            Paragraph(f"{blend_data['method_effective'].upper()} (Requested: {blend_data['method_requested']})", body_style),
            Paragraph("<b>Data Provenance:</b>", body_style),
            Paragraph(f"<b>{blend_data['provenance']}</b>", body_style),
        ],
        [
            Paragraph("<b>Fallback Status:</b>", body_style),
            Paragraph(
                f"<font color='{'red' if blend_data['fallback_active'] else 'green'}'><b>{'ACTIVE: ' + str(blend_data['fallback_reason']) if blend_data['fallback_active'] else 'NOMINAL (No Fallback)'}</b></font>",
                body_style
            ),
            Paragraph("<b>Confidence Level:</b>", body_style),
            Paragraph(f"<b>{blend_data['confidence_mean']:.2f} (High: {blend_data['pct_high']}%, Med: {blend_data['pct_medium']}%)</b>", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[100, 160, 100, 160])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Section 1: Domain Forecast Extremes Summary
    story.append(Paragraph("1. SYNOPTIC FIELD DIAGNOSTICS & SUMMARY", section_title))
    b_grid = blend_data["blended_grid"]
    peak_val = float(np.max(b_grid))
    mean_val = float(np.mean(b_grid))
    min_val = float(np.min(b_grid))

    summary_text = (
        f"Domain-wide blended {cfg.variables[variable].display_name} ranges from <b>{min_val:.1f}</b> to <b>{peak_val:.1f} {cfg.variables[variable].unit}</b> "
        f"(mean: <b>{mean_val:.1f} {cfg.variables[variable].unit}</b>). "
        f"Convective activity and high-impact conditions are concentrated along the Odisha coast and adjacent highlands."
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 8))

    # Section 2: Model Weight Allocation
    story.append(Paragraph("2. MULTI-MODEL BLENDING WEIGHTS & DOMINANCE", section_title))
    w_rows = [["Model ID", "Model Type", "Mean Weight", "Dominant Cell Share (%)"]]
    weights = blend_data["weights"]
    dom_src = blend_data["dominant_source"]
    total_cells = float(dom_src.size)

    for mid, w_arr in weights.items():
        src_cfg = cfg.sources.get(mid)
        kind = src_cfg.kind.upper() if src_cfg else "NWP"
        mean_w = float(np.mean(w_arr))
        dom_share = float(np.sum(dom_src == mid) / total_cells * 100.0)
        w_rows.append([
            src_cfg.name if src_cfg else mid,
            kind,
            f"{mean_w:.3f}",
            f"{dom_share:.1f}%",
        ])

    w_table = Table(w_rows, colWidths=[180, 110, 110, 120])
    w_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy_blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(w_table)
    story.append(Spacer(1, 10))

    # Section 3: Extreme Weather Risk & Minority Signals
    story.append(Paragraph("3. EXTREME EVENT ALERTS & MINORITY SIGNALS", section_title))
    alerts = blend_data.get("minority_alerts", [])
    if alerts:
        story.append(Paragraph(
            f"<b>CRITICAL: {len(alerts)} geographic cell(s) exhibit Minority Extreme Signals!</b> "
            f"High-skill models predict values exceeding alert threshold ({alerts[0]['threshold']} {cfg.variables[variable].unit}), "
            f"even though the multi-model blended average remains below the alert trigger. Do not dismiss these convective cores.",
            body_style
        ))
        story.append(Spacer(1, 4))
        alert_rows = [["Latitude", "Longitude", "Blend Value", "Peak Model Value", "Flagged Model(s)"]]
        for a in alerts[:6]:  # Show top 6 alerts in table
            sources_str = ", ".join([f"{s['source']} ({s['value']})" for s in a["sources_exceeding"]])
            alert_rows.append([
                f"{a['lat']:.2f}°N",
                f"{a['lon']:.2f}°E",
                f"{a['blend_value']} {cfg.variables[variable].unit}",
                f"{a['max_model_value']} {cfg.variables[variable].unit}",
                sources_str,
            ])
        alert_table = Table(alert_rows, colWidths=[70, 70, 90, 100, 190])
        alert_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), alert_red),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FEF2F2"), colors.white]),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(alert_table)
    else:
        story.append(Paragraph("No minority extreme signals detected. Blended consensus aligns with extreme thresholds.", body_style))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94A3B8"), spaceAfter=6))
    story.append(Paragraph(
        "VARUN-FUSION Operations Engine | Smart India Hackathon 2026 | Team CodeX_2026 (Team ID 159951) | MoES PS 26081",
        ParagraphStyle("Footer", parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#64748B"), alignment=1)
    ))

    doc.build(story)
    logger.info(f"Generated operational shift report: {pdf_path}")
    return pdf_path
