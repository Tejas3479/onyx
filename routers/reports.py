"""Onyx Report API — generate GFR-compliant benchmark reports."""

import logging

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
    primary = {}
    all_results = []
    
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


@router.post("/reports/generate-from-query", response_class=HTMLResponse)
async def generate_report_from_query(req: ReportFromQueryRequest):
    """Generate a report by running a fresh benchmark and rendering the template."""
    try:
        result = await get_price_benchmark(
            query=req.product_name,
            department=req.department_name,
        )
    except Exception as e:
        logger.exception("Benchmark for report failed")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e!s}")

    primary = result["primary_result"]
    html = generate_report_html(
        search_id=req.product_name,
        query=req.product_name,
        query_mode="product",
        resolved_tier=result["resolved_tier"],
        tier_label=result["tier_label"],
        primary_result=primary,
        all_results=result["all_results"],
        tier_trace=result["tier_trace"],
        statistics=result["statistics"],
        department_name=req.department_name,
        signatory_name=req.signatory_name,
    )

    if req.output_format == "pdf":
        file_path = save_report(html, req.product_name, fmt="pdf")
        if file_path.endswith(".pdf"):
            return FileResponse(
                file_path,
                media_type="application/pdf",
                filename=f"benchmark_report_{req.product_name[:20]}.pdf",
            )
        else:
            return FileResponse(
                file_path,
                media_type="text/html",
                filename=f"benchmark_report_{req.product_name[:20]}.html",
            )

    file_path = save_report(html, req.product_name, fmt="html")
    return FileResponse(
        file_path,
        media_type="text/html",
        filename=f"benchmark_report_{req.product_name[:20]}.html",
    )
