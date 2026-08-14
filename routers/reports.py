"""Onyx Report API — generate GFR-compliant benchmark reports."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from models import ReportRequest
from services.report_generator import generate_report_html, save_report
from services.tier_waterfall import get_price_benchmark

logger = logging.getLogger("onyx.reports")

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.post("/reports/generate")
async def generate_report(req: ReportRequest):
    """Generate a GFR-compliant price benchmark report.

    Takes a search_id from a previous benchmark run and generates
    a formal report suitable for procurement files.
    """
    # Re-run the benchmark to get fresh data
    # In production, this would fetch from the DB by search_id
    # For now, we need the query to re-run
    raise HTTPException(
        status_code=501,
        detail="Direct report generation from search_id requires DB persistence. "
               "Use /api/v1/reports/generate-from-query instead.",
    )


@router.post("/reports/generate-from-query", response_class=HTMLResponse)
async def generate_report_from_query(
    product_name: str,
    department_name: str | None = None,
    signatory_name: str | None = None,
    output_format: str = "html",
):
    """Generate a report by running a fresh benchmark and rendering the template."""
    try:
        result = await get_price_benchmark(
            query=product_name,
            department=department_name,
        )
    except Exception as e:
        logger.exception("Benchmark for report failed")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e!s}")

    primary = result["primary_result"]
    html = generate_report_html(
        search_id=product_name,
        query=product_name,
        query_mode="product",
        resolved_tier=result["resolved_tier"],
        tier_label=result["tier_label"],
        primary_result=primary,
        all_results=result["all_results"],
        tier_trace=result["tier_trace"],
        statistics=result["statistics"],
        department_name=department_name,
        signatory_name=signatory_name,
    )

    if output_format == "pdf":
        file_path = save_report(html, product_name, fmt="pdf")
        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename=f"benchmark_report_{product_name[:20]}.pdf",
        )

    # Save HTML and return inline
    save_report(html, product_name, fmt="html")
    return HTMLResponse(content=html)
