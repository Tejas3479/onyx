"""Onyx Report API — generate GFR-compliant benchmark reports."""

import logging
import typing

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import asc, desc, select

from database import (
    BenchmarkAuditLog,
    DelegationRecord,
    PriceResult,
    PriceSearch,
    async_session_maker,
)
from models import ReportFromQueryRequest, ReportRequest
from routers.auth_routes import require_current_user
from services.base_product import resolve_base_product
from services.freight_estimator import estimate_freight
from services.price_extractor import compute_statistics
from services.procurement_threshold import evaluate_procurement_threshold
from services.report_generator import generate_report_html, save_report
from services.tier_waterfall import get_price_benchmark

logger = logging.getLogger("onyx.reports")

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.post("/reports/generate")
async def generate_report(req: ReportRequest, user=Depends(require_current_user)):
    """Generate a GFR-compliant price benchmark report from DB by search_id."""
    async with async_session_maker() as session:
        search = await session.get(PriceSearch, req.search_id)
        if not search:
            raise HTTPException(status_code=404, detail="Search ID not found")

        result_stmt = select(PriceResult).where(PriceResult.search_id == req.search_id)
        results_db = (await session.execute(result_stmt)).scalars().all()

        delegations = (
            await session.execute(
                select(DelegationRecord)
                .where(DelegationRecord.search_id == req.search_id)
                .order_by(desc(DelegationRecord.created_at))
            )
        ).scalars().all()
        audit_log = (
            await session.execute(
                select(BenchmarkAuditLog)
                .where(BenchmarkAuditLog.search_id == req.search_id)
                .order_by(asc(BenchmarkAuditLog.created_at))
            )
        ).scalars().all()

    delegation_list = [
        {
            "delegate_to_name": d.delegate_to_name,
            "delegate_to_email": d.delegate_to_email,
            "delegated_by_name": d.delegated_by_name,
            "note": d.note,
            "status": d.status,
            "decision": d.decision,
            "decision_note": d.decision_note,
            "created_at": d.created_at.isoformat(),
        }
        for d in delegations
    ]
    audit_list = [
        {
            "action": e.action,
            "actor_name": e.actor_name,
            "note": e.note,
            "created_at": e.created_at.isoformat(),
        }
        for e in audit_log
    ]

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

    priced = [r.price for r in results_db if r.price is not None]
    statistics = (
        search.statistics
        if isinstance(search.statistics, dict) and search.statistics
        else compute_statistics(priced)
    )

    html = generate_report_html(
        search_id=req.search_id,
        query=search.query,
        query_mode=search.query_mode,
        resolved_tier=search.resolved_tier,
        tier_label=search.tier_label,
        primary_result=primary,
        all_results=all_results,
        tier_trace=search.tier_skip_reasons
        if isinstance(search.tier_skip_reasons, dict)
        else {},
        statistics=statistics,
        department_name=req.department_name,
        signatory_name=req.signatory_name,
        any_demo_data=search.any_demo_data,
        estimated_value=search.estimated_value,
        delivery_location=search.delivery_location,
        specs=search.specs if isinstance(search.specs, dict) else None,
        procurement_threshold=(
            search.procurement_threshold
            if isinstance(search.procurement_threshold, dict)
            else None
        ),
        base_product=(
            search.base_product if isinstance(search.base_product, dict) else None
        ),
        freight=search.freight if isinstance(search.freight, dict) else None,
        delegations=delegation_list,
        audit_log=audit_list,
    )

    if req.output_format == "pdf":
        file_path = save_report(
            html,
            req.search_id,
            fmt="pdf",
            query=search.query,
            any_demo_data=search.any_demo_data,
            pdf_context={
                "statistics": statistics,
                "procurement_threshold": (
                    search.procurement_threshold
                    if isinstance(search.procurement_threshold, dict)
                    else None
                ),
                "specs": search.specs if isinstance(search.specs, dict) else None,
                "base_product": (
                    search.base_product if isinstance(search.base_product, dict) else None
                ),
                "freight": search.freight if isinstance(search.freight, dict) else None,
                "delegations": delegation_list,
                "audit_log": audit_list,
            },
        )
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

    file_path = save_report(html, req.search_id, fmt="html", query=search.query)
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
    user=Depends(require_current_user),
):
    """Generate a report by running a fresh benchmark and rendering the template.

    Supports both POST JSON payload and GET query parameters.
    """
    p_name = req.product_name if req else (product_name or "")
    dept_name = req.department_name if req else department_name
    sig_name = req.signatory_name if req else signatory_name
    fmt = req.output_format if req else output_format

    if not p_name:
        raise HTTPException(
            status_code=400, detail="product_name query parameter is required"
        )

    quantity = req.quantity if req else 1
    est_value = req.estimated_value if req else None
    delivery_location = req.delivery_location if req else None
    specs = req.specs if req else None
    category = req.category if req else None

    try:
        result = await get_price_benchmark(
            query=p_name,
            specs=specs,
            department=dept_name,
            category=category,
            query_mode="product",
            quantity=quantity,
        )
    except Exception as e:
        logger.exception("Benchmark for report failed")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e!s}")

    primary = result["primary_result"]
    any_demo_data = bool(primary.get("is_demo_data")) or any(
        r.get("is_demo_data") for r in result.get("all_results", [])
    )

    base_product = None
    try:
        base_product = await resolve_base_product(p_name, dept_name)
    except Exception:
        pass

    freight = None
    if delivery_location:
        freight = estimate_freight(
            location=delivery_location,
            unit_price=primary.get("price"),
            quantity=quantity,
        )

    threshold = (
        evaluate_procurement_threshold(
            value=est_value,
            quotes_obtained=(result.get("statistics") or {}).get(
                "competitive_pool", 0
            ),
            price_found=(primary.get("price") is not None),
        )
        if est_value is not None
        else None
    )

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
        any_demo_data=any_demo_data,
        estimated_value=est_value,
        delivery_location=delivery_location,
        specs=specs,
        procurement_threshold=threshold,
        base_product=base_product,
        freight=freight,
    )

    if fmt == "pdf":
        file_path = save_report(
            html,
            p_name,
            fmt="pdf",
            query=p_name,
            any_demo_data=any_demo_data,
            pdf_context={
                "statistics": result["statistics"],
                "procurement_threshold": threshold,
                "specs": specs,
                "base_product": base_product,
                "freight": freight,
            },
        )
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

    file_path = save_report(html, p_name, fmt="html", query=p_name)
    return FileResponse(
        file_path,
        media_type="text/html",
        filename=f"benchmark_report_{p_name[:20].replace(' ', '_')}.html",
    )
