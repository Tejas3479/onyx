"""GFR-compliant price benchmarking report generator.

Renders HTML reports from Jinja2 templates. PDF generation via WeasyPrint
is optional (falls back to HTML-only if WeasyPrint is unavailable).
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("onyx.report_generator")

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Reports output directory
REPORT_DIR = Path("data/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Jinja2 environment
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def generate_report_html(
    search_id: str,
    query: str,
    query_mode: str,
    resolved_tier: int,
    tier_label: str,
    primary_result: dict[str, Any],
    all_results: list[dict[str, Any]],
    tier_trace: dict[str, str],
    statistics: dict[str, Any],
    department_name: str | None = None,
    signatory_name: str | None = None,
    any_demo_data: bool = False,
    estimated_value: float | None = None,
    delivery_location: str | None = None,
    specs: dict[str, Any] | None = None,
    procurement_threshold: dict[str, Any] | None = None,
    base_product: dict[str, Any] | None = None,
    freight: dict[str, Any] | None = None,
    delegations: list[dict[str, Any]] | None = None,
    audit_log: list[dict[str, Any]] | None = None,
) -> str:
    """Generate HTML report content from benchmark results."""
    template = jinja_env.get_template("report_template.html")

    # Tier method descriptions for the report
    tier_methods = {
        0: "DGS&D Rate Contract / Ministry Notified Rate",
        1: "GeM Business Analytics / GeM Last Purchase Price",
        2: "Department's Own Last Purchase Price (uploaded records)",
        3: "Online Market Survey (Amazon, GeM Catalog, IndiaMART, Flipkart, Google Shopping)",
        4: "Non-Standard Item Estimation (spec-similarity / import cost basis)",
    }

    context = {
        "search_id": search_id,
        "query": query,
        "query_mode": query_mode,
        "resolved_tier": resolved_tier,
        "tier_label": tier_label,
        "tier_method": tier_methods.get(resolved_tier, "Unknown"),
        "primary_result": primary_result,
        "all_results": all_results,
        "tier_trace": tier_trace,
        "statistics": statistics,
        "department_name": department_name or "Not specified",
        "signatory_name": signatory_name or "Authorized Officer",
        "generated_at": datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC"),
        "report_id": str(uuid.uuid4())[:8].upper(),
        "any_demo_data": any_demo_data,
        "estimated_value": estimated_value,
        "delivery_location": delivery_location,
        "specs": specs or {},
        "procurement_threshold": procurement_threshold,
        "base_product": base_product,
        "freight": freight,
        "delegations": delegations or [],
        "audit_log": audit_log or [],
    }

    return template.render(**context)


def save_report(
    html_content: str,
    search_id: str,
    fmt: str = "html",
    query: str = "",
    any_demo_data: bool = False,
    pdf_context: dict[str, Any] | None = None,
) -> str:
    """Save report to disk. Returns the file path.

    Args:
        html_content: Rendered HTML string
        search_id: Search ID for filename
        fmt: 'html' or 'pdf'
        query: The product/service name shown on the certificate (avoids
            leaking the raw search_id into official documents).
        any_demo_data: When True, renders a watermark on PDF output noting
            that the benchmark relied on demo/seeded data.
        pdf_context: Optional compliance snapshot (statistics, threshold,
            specs, base product, freight, delegations, audit) rendered into
            the ReportLab fallback certificate so the PDF artifact carries the
            full reasonability story even without WeasyPrint.
    """
    # search_id may be a UUID or, from /reports/generate-from-query, a raw
    # product name — sanitize it so it can't break the on-disk path.
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", search_id)[:40] or "report"
    filename = (
        f"report_{safe_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )

    if fmt == "pdf":
        # 1. Try WeasyPrint (Linux/Docker with GTK)
        try:
            from weasyprint import HTML

            pdf_path = REPORT_DIR / f"{filename}.pdf"
            HTML(string=html_content).write_pdf(str(pdf_path))
            logger.info("PDF report saved via WeasyPrint: %s", pdf_path)
            return str(pdf_path)
        except Exception as e:
            logger.warning(f"WeasyPrint unavailable ({e}), trying ReportLab...")

        # 2. Try ReportLab (Native cross-platform vector PDF)
        try:
            import html as html_lib

            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import (
                HRFlowable,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            pdf_path = REPORT_DIR / f"{filename}.pdf"
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36,
            )
            styles = getSampleStyleSheet()

            # Custom styles
            title_style = ParagraphStyle(
                "CertTitle",
                parent=styles["Heading1"],
                fontSize=15,
                leading=18,
                alignment=1,
                textColor=colors.HexColor("#0f172a"),
                fontName="Helvetica-Bold",
            )
            subtitle_style = ParagraphStyle(
                "CertSubtitle",
                parent=styles["Normal"],
                fontSize=10,
                leading=13,
                alignment=1,
                textColor=colors.HexColor("#334155"),
                fontName="Helvetica",
            )
            body_style = ParagraphStyle(
                "CertBody",
                parent=styles["Normal"],
                fontSize=9.5,
                leading=13,
                textColor=colors.HexColor("#1e293b"),
                fontName="Helvetica",
            )
            bold_style = ParagraphStyle(
                "CertBold",
                parent=styles["Normal"],
                fontSize=10,
                leading=13,
                textColor=colors.HexColor("#0f172a"),
                fontName="Helvetica-Bold",
            )

            story = []
            story.append(Paragraph("GOVERNMENT OF INDIA", title_style))
            story.append(
                Paragraph(
                    "PRICE REASONABILITY & STATUTORY MARKET SURVEY CERTIFICATE",
                    subtitle_style,
                )
            )
            story.append(
                Paragraph(
                    "<i>Issued under General Financial Rules (GFR) 2017, Rule 149(vii)</i>",
                    subtitle_style,
                )
            )
            story.append(Spacer(1, 10))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=1.5,
                    color=colors.HexColor("#0f172a"),
                    spaceBefore=2,
                    spaceAfter=12,
                )
            )

            # Summary Box
            meta_data = [
                [
                    Paragraph(
                        f"<b>Report ID:</b> ONX-{search_id[:8].upper()}", body_style
                    ),
                    Paragraph(
                        f"<b>Date:</b> {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}",
                        body_style,
                    ),
                ],
                [
                    Paragraph(
                        f"<b>Product/Service:</b> {html_lib.escape(query or search_id)}",
                        body_style,
                    ),
                    Paragraph("<b>Authority:</b> GFR 2017 Rule 149(vii)", body_style),
                ],
            ]
            meta_table = Table(meta_data, colWidths=[260, 260])
            meta_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                        (
                            "INNERGRID",
                            (0, 0),
                            (-1, -1),
                            0.5,
                            colors.HexColor("#e2e8f0"),
                        ),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(meta_table)
            story.append(Spacer(1, 14))

            # Audit statement
            statement = (
                "This official document certifies that automated price reasonability verification has been performed "
                "in accordance with the statutory order of precedence mandated under <b>GFR 2017 Rule 149(vii)</b> and "
                "the <i>Manual for Procurement of Goods and Services</i>. All higher-priority statutory tiers were "
                "exhaustively evaluated prior to market survey discovery."
            )
            story.append(Paragraph(statement, body_style))
            story.append(Spacer(1, 14))

            # Waterfall Table
            tier_rows = [
                [
                    Paragraph("<b>GFR Hierarchy Tier</b>", bold_style),
                    Paragraph("<b>Statutory Source</b>", bold_style),
                    Paragraph("<b>Precedence Status</b>", bold_style),
                ],
                [
                    Paragraph("Tier 0: Notified Rates", body_style),
                    Paragraph("DGS&D / Ministry Rate Contracts", body_style),
                    Paragraph("Evaluated (Highest Statutory Priority)", body_style),
                ],
                [
                    Paragraph("Tier 1: GeM BA / LPP", body_style),
                    Paragraph("GeM Business Analytics & Verified LPP", body_style),
                    Paragraph("Evaluated (Direct GeM Orders)", body_style),
                ],
                [
                    Paragraph("Tier 2: Department LPP", body_style),
                    Paragraph("Department Historical PO Database", body_style),
                    Paragraph(
                        "Evaluated (Fuzzy Match & Inflation Adjusted)", body_style
                    ),
                ],
                [
                    Paragraph("Tier 3: Market Survey", body_style),
                    Paragraph("Multi-Source Marketplace Crawl", body_style),
                    Paragraph("Evaluated (Public Domain Benchmarking)", body_style),
                ],
                [
                    Paragraph("Tier 4: Non-Standard", body_style),
                    Paragraph("Landed Import Cost / Spec Multipliers", body_style),
                    Paragraph("Fallback (Rule 155 LPC / Rule 166 PAC)", body_style),
                ],
            ]
            tier_table = Table(tier_rows, colWidths=[140, 190, 190])
            tier_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(tier_table)
            story.append(Spacer(1, 16))

            # ── Compliance story (persisted at run time) ──
            ctx = pdf_context or {}
            stats = ctx.get("statistics") or {}
            threshold = ctx.get("procurement_threshold") or {}
            specs = ctx.get("specs") or {}
            base_product = ctx.get("base_product") or {}
            freight = ctx.get("freight") or {}
            delegations = ctx.get("delegations") or []
            audit_log = ctx.get("audit_log") or []

            if stats.get("l1") is not None or (
                stats.get("band_low") is not None
                and stats.get("band_high") is not None
            ):
                story.append(
                    Paragraph(
                        "<b>L1 Competitive Bid &amp; Reasonableness Band</b>",
                        bold_style,
                    )
                )
                if stats.get("l1") is not None:
                    l1_line = (
                        f"L1 Competitive Bid: <b>Rs. {stats['l1']:,.2f}</b>"
                    )
                    if stats.get("l1_source"):
                        l1_line += f" ({html_lib.escape(str(stats['l1_source']))})"
                    story.append(Paragraph(l1_line, body_style))
                if stats.get("competitive_pool") is not None:
                    story.append(
                        Paragraph(
                            f"Competitive Pool: {stats['competitive_pool']} "
                            "independent quote(s)",
                            body_style,
                        )
                    )
                if stats.get("band_low") is not None and stats.get(
                    "band_high"
                ) is not None:
                    within = "WITHIN band" if stats.get("within_band") else "OUTSIDE band - review required"
                    story.append(
                        Paragraph(
                            f"Reasonableness Band (±25%): Rs. {stats['band_low']:,.2f} "
                            f"- Rs. {stats['band_high']:,.2f} - <b>{within}</b>",
                            body_style,
                        )
                    )
                story.append(Spacer(1, 8))

            if threshold:
                compliant = threshold.get("compliant")
                story.append(
                    Paragraph(
                        "<b>Procurement Threshold Compliance</b>",
                        bold_style,
                    )
                )
                mode = html_lib.escape(
                    str(threshold.get("mode_label") or threshold.get("mode", "N/A"))
                )
                rule = html_lib.escape(str(threshold.get("rule", "N/A")))
                status = (
                    "<font color='#0d6e3e'><b>COMPLIANT</b></font>"
                    if compliant
                    else "<font color='#842029'><b>NON-COMPLIANT</b></font>"
                )
                story.append(
                    Paragraph(
                        f"Mode: {mode} ({rule}) - {status}",
                        body_style,
                    )
                )
                if threshold.get("quotes_obtained") is not None:
                    story.append(
                        Paragraph(
                            f"Quotes: {threshold.get('quotes_obtained')} / "
                            f"{threshold.get('min_quotes_required') or threshold.get('min_quotes') or 'N/A'} required",
                            body_style,
                        )
                    )
                if threshold.get("guidance"):
                    story.append(
                        Paragraph(
                            f"Guidance: {html_lib.escape(str(threshold['guidance']))}",
                            body_style,
                        )
                    )
                story.append(Spacer(1, 8))

            if specs:
                story.append(
                    Paragraph("<b>Golden Parameters</b>", bold_style)
                )
                story.append(
                    Paragraph(
                        "Configured baseline: "
                        + " ; ".join(
                            f"{html_lib.escape(str(k))}: {html_lib.escape(str(v))}"
                            for k, v in specs.items()
                        ),
                        body_style,
                    )
                )
                story.append(Spacer(1, 8))

            if base_product.get("canonical_name"):
                story.append(
                    Paragraph("<b>Canonical Base-Product Identity</b>", bold_style)
                )
                bp_line = html_lib.escape(str(base_product["canonical_name"]))
                if base_product.get("match_score") is not None:
                    bp_line += f" (identity match {base_product['match_score']}%)"
                story.append(Paragraph(bp_line, body_style))
                prior = base_product.get("prior_records", 0)
                if prior:
                    median = base_product.get("prior_median_price")
                    bp_line2 = f"Recognized from {prior} prior purchase record(s)"
                    if median is not None:
                        bp_line2 += f"; prior median Rs. {median:,.2f}"
                    story.append(Paragraph(bp_line2, body_style))
                else:
                    story.append(
                        Paragraph(
                            "No prior purchase records - this benchmark establishes "
                            "the reference price.",
                            body_style,
                        )
                    )
                story.append(Spacer(1, 8))

            if freight.get("landed_total") is not None:
                story.append(
                    Paragraph("<b>Landed Cost (Delivery Location)</b>", bold_style)
                )
                story.append(
                    Paragraph(
                        f"Goods Rs. {freight['goods_value']:,.2f} + Freight "
                        f"Rs. {freight['freight_amount']:,.2f} "
                        f"({freight.get('freight_pct', 0)}%) = "
                        f"<b>Landed Rs. {freight['landed_total']:,.2f}</b> "
                        f"({html_lib.escape(str(freight.get('delivery_location', '')))} - "
                        f"{html_lib.escape(str(freight.get('region_label', '')))})",
                        body_style,
                    )
                )
                story.append(Spacer(1, 8))

            if delegations or audit_log:
                story.append(
                    Paragraph("<b>Delegation &amp; Audit Trail</b>", bold_style)
                )
                for d in delegations:
                    decision = (d.get("decision") or "").upper()
                    story.append(
                        Paragraph(
                            f"Delegated to {html_lib.escape(str(d.get('delegate_to_name', '')))} "
                            f"by {html_lib.escape(str(d.get('delegated_by_name') or 'the benchmarking officer'))} - "
                            f"{html_lib.escape(str(d.get('status', ''))).upper()}"
                            + (f" / {decision}" if decision else ""),
                            body_style,
                        )
                    )
                for entry in audit_log:
                    story.append(
                        Paragraph(
                            f"{html_lib.escape(str(entry.get('action', '')))} - "
                            f"{html_lib.escape(str(entry.get('actor_name') or '—'))}"
                            + (
                                f" ({html_lib.escape(str(entry.get('note', '')))})"
                                if entry.get("note")
                                else ""
                            ),
                            body_style,
                        )
                    )
                story.append(Spacer(1, 8))

            # Statutory Note
            note_text = (
                "<b>Statutory Recommendation:</b> If no automated tier yields verified prices, refer procurement "
                "to the Local Purchase Committee per <b>GFR Rule 155</b> or obtain Proprietary Article Certificate (PAC) "
                "per <b>GFR Rule 166</b>."
            )
            story.append(Paragraph(note_text, body_style))
            story.append(Spacer(1, 35))

            # Signatures
            sign_data = [
                [
                    Paragraph(
                        "<b>_________________________</b><br/><b>[ Indenting Officer ]</b><br/>Prepared & Benchmarked by",
                        body_style,
                    ),
                    Paragraph(
                        "<b>_________________________</b><br/><b>[ Competent Financial Authority ]</b><br/>Approved & Sanctioned by",
                        body_style,
                    ),
                ]
            ]
            sign_table = Table(sign_data, colWidths=[260, 260])
            sign_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            story.append(sign_table)

            if any_demo_data:
                from reportlab.pdfgen import canvas as pdf_canvas

                class _WatermarkCanvas(pdf_canvas.Canvas):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self._watermarked = False

                    def showPage(self):
                        self._draw_watermark()
                        super().showPage()

                    def save(self):
                        self._draw_watermark()
                        super().save()

                    def _draw_watermark(self):
                        if self._watermarked:
                            return
                        self._watermarked = True
                        self.saveState()
                        self.setFont("Helvetica-Bold", 34)
                        self.setFillColor(colors.HexColor("#dc2626"))
                        self.setFillAlpha(0.16)
                        self.translate(300, 420)
                        self.rotate(45)
                        self.drawCentredString(0, 0, "DEMO MODE")
                        self.drawCentredString(0, 60, "NOT FOR OFFICIAL USE")
                        self.restoreState()

                doc.build(story, canvasmaker=_WatermarkCanvas)
            else:
                doc.build(story)
            logger.info("PDF report saved via ReportLab: %s", pdf_path)
            return str(pdf_path)
        except Exception as e:
            logger.error(f"ReportLab PDF generation failed: {e}. Falling back to HTML.")

    # HTML fallback
    html_path = REPORT_DIR / f"{filename}.html"
    html_path.write_text(html_content, encoding="utf-8")
    logger.info("HTML report saved: %s", html_path)
    return str(html_path)
