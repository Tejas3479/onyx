"""Onyx Report API — generate GFR-compliant benchmark reports."""

import logging
import typing

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select

from database import PriceResult, PriceSearch, async_session_maker
from models import ReportFromQueryRequest, ReportRequest
from services.report_generator import generate_report_html, save_report
from services.tier_waterfall import get_price_benchmark

logger = logging.getLogger("onyx.reports")

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.post("/reports/generate")
async def generate_report(req: ReportRequest):
    """Generate a GFR-compliant price benchmark report from DB by search_id."""
    async with async_session_maker() as session:
        search = await session.get(PriceSearch, req.search_id)
        if not search:
            raise HTTPException(status_code=404, detail="Search ID not found")
        
        result_stmt = select(PriceResult).where(PriceResult.search_id == req.search_id)
        results_db = (await session.execute(result_stmt)).scalars().all()

    # Reconstruct data structures for generate_report_html
    primary: dict[str, typing.Any] = {}
    all_results: list[dict[str, typing.Any]] = []
    
    # In database, PriceResult doesn't inherently track "primary" vs "all".
    # But usually the first one or the one with the source URL is treated as such,
    # or we can reconstruct based on resolved_tier and tier_skip_reasons.
    for r in results_db:
        result_dict = {
            "source_name": r.source_name,
            "evidence_url": r.source_url,
            "price": r.price,
            "currency": r.currency,
            "confidence": r.confidence,
            "rationale": r.raw_content,
        }
        all_results.append(result_dict)
        if not primary and r.price:
            primary = result_dict
            
    if not primary and all_results:
        primary = all_results[0]

    html = generate_report_html(
        search_id=req.search_id,
        query=search.query,
        query_mode=search.query_mode,
        resolved_tier=search.resolved_tier,
        tier_label=search.tier_label,
        primary_result=primary,
        all_results=all_results,
        tier_trace=search.tier_skip_reasons if isinstance(search.tier_skip_reasons, dict) else {},
        statistics={},  # Skip for now
        department_name=req.department_name,
        signatory_name=req.signatory_name,
    )

    if req.output_format == "pdf":
        file_path = save_report(html, req.search_id, fmt="pdf")
        if file_path.endswith(".pdf"):
            return FileResponse(
                file_path,
                media_type="application/pdf",
                filename=f"benchmark_report_{req.search_id[:8]}.pdf",
            )
        else:
            # Fallback was triggered
            return FileResponse(
                file_path,
                media_type="text/html",
                filename=f"benchmark_report_{req.search_id[:8]}.html",
            )

    file_path = save_report(html, req.search_id, fmt="html")
    return FileResponse(
        file_path,
        media_type="text/html",
        filename=f"benchmark_report_{req.search_id[:8]}.html",
    )


@router.get("/reports/generate-from-query")
@router.post("/reports/generate-from-query", response_class=HTMLResponse)
async def generate_report_from_query(
    req: ReportFromQueryRequest | None = None,
    product_name: str | None = None,
    department_name: str | None = None,
    signatory_name: str | None = None,
    output_format: str = "html",
):
    """Generate a report by running a fresh benchmark and rendering the template.
    
    Supports both POST JSON payload and GET query parameters.
    """
    p_name = req.product_name if req else (product_name or "")
    dept_name = req.department_name if req else department_name
    sig_name = req.signatory_name if req else signatory_name
    fmt = req.output_format if req else output_format

    if not p_name:
        raise HTTPException(status_code=400, detail="product_name query parameter is required")

    try:
        result = await get_price_benchmark(
            query=p_name,
            department=dept_name,
        )
    except Exception as e:
        logger.exception("Benchmark for report failed")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e!s}")

    primary = result["primary_result"]
    html = generate_report_html(
        search_id=p_name,
        query=p_name,
        query_mode="product",
        resolved_tier=result["resolved_tier"],
        tier_label=result["tier_label"],
        primary_result=primary,
        all_results=result["all_results"],
        tier_trace=result["tier_trace"],
        statistics=result["statistics"],
        department_name=dept_name,
        signatory_name=sig_name,
    )

    if fmt == "pdf":
        file_path = save_report(html, p_name, fmt="pdf")
        if file_path.endswith(".pdf"):
            return FileResponse(
                file_path,
                media_type="application/pdf",
                filename=f"benchmark_report_{p_name[:20].replace(' ', '_')}.pdf",
            )
        else:
            return FileResponse(
                file_path,
                media_type="text/html",
                filename=f"benchmark_report_{p_name[:20].replace(' ', '_')}.html",
            )

    file_path = save_report(html, p_name, fmt="html")
    return FileResponse(
        file_path,
        media_type="text/html",
        filename=f"benchmark_report_{p_name[:20].replace(' ', '_')}.html",
    )
