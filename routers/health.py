"""Onyx health & readiness probe — status, seeded-data counts, benchmark totals."""

import os

from fastapi import APIRouter
from sqlalchemy import func, select, text

from database import (
    DepartmentPurchaseRecord,
    GemLPPCache,
    NotifiedRate,
    PriceResult,
    PriceSearch,
    async_session_maker,
)
from fetcher import playwright_mgr, redis_client, session_manager
from services.search_orchestrator import _load_demo_cache

router = APIRouter(tags=["health"])

APP_VERSION = "2.1.0"

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")


@router.get("/api/health")
async def health():
    # Check Database
    db_status = "ok"
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e!s}"

    # Check Redis
    redis_status = "ok"
    try:
        await redis_client.ping()
    except Exception as e:
        redis_status = f"offline (local memory mode: {e!s})"

    active_sessions = 0
    try:
        active_sessions = await session_manager.count_sessions()
    except Exception:
        active_sessions = 0

    # Seeded reference-data counts + benchmark totals
    counts: dict[str, int] = {
        "notified_rates": 0,
        "gem_lpp": 0,
        "department_records": 0,
        "benchmark_runs": 0,
        "price_results": 0,
    }
    try:
        async with async_session_maker() as session:
            counts["notified_rates"] = (
                await session.execute(select(func.count()).select_from(NotifiedRate))
            ).scalar() or 0
            counts["gem_lpp"] = (
                await session.execute(select(func.count()).select_from(GemLPPCache))
            ).scalar() or 0
            counts["department_records"] = (
                await session.execute(
                    select(func.count()).select_from(DepartmentPurchaseRecord)
                )
            ).scalar() or 0
            counts["benchmark_runs"] = (
                await session.execute(select(func.count()).select_from(PriceSearch))
            ).scalar() or 0
            counts["price_results"] = (
                await session.execute(select(func.count()).select_from(PriceResult))
            ).scalar() or 0
    except Exception:
        pass

    try:
        demo_cache_keys = len(_load_demo_cache())
    except Exception:
        demo_cache_keys = 0

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": APP_VERSION,
        "demo_mode": DEMO_MODE,
        "database": db_status,
        "redis": redis_status,
        "active_sessions": active_sessions,
        "playwright_slots_free": playwright_mgr.slots_free,
        "seeded_data": {
            "notified_rates": counts["notified_rates"],
            "gem_lpp_entries": counts["gem_lpp"],
            "department_purchase_records": counts["department_records"],
            "demo_cache_keys": demo_cache_keys,
        },
        "benchmarks": {
            "total_runs": counts["benchmark_runs"],
            "total_price_results": counts["price_results"],
        },
    }
