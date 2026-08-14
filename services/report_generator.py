"""GFR-compliant price benchmarking report generator.

Renders HTML reports from Jinja2 templates. PDF generation via WeasyPrint
is optional (falls back to HTML-only if WeasyPrint is unavailable).
"""

import logging
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
    }

    return template.render(**context)


def save_report(
    html_content: str,
    search_id: str,
    fmt: str = "html",
) -> str:
    """Save report to disk. Returns the file path.

    Args:
        html_content: Rendered HTML string
        search_id: Search ID for filename
        fmt: 'html' or 'pdf'
    """
    filename = f"report_{search_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    if fmt == "pdf":
        try:
            from weasyprint import HTML
            pdf_path = REPORT_DIR / f"{filename}.pdf"
            HTML(string=html_content).write_pdf(str(pdf_path))
            logger.info("PDF report saved: %s", pdf_path)
            return str(pdf_path)
        except ImportError:
            logger.warning("WeasyPrint not available, falling back to HTML")
        except Exception as e:
            logger.warning("PDF generation failed: %s. Falling back to HTML", e)

    # HTML fallback
    html_path = REPORT_DIR / f"{filename}.html"
    html_path.write_text(html_content, encoding="utf-8")
    logger.info("HTML report saved: %s", html_path)
    return str(html_path)
