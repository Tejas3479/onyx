import logging
import os
import time
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException
from rapidfuzz import fuzz

from auth import verify_api_key
from fetcher import playwright_mgr, run_fetch, session_manager
from models import FetchRequest, FetchResponse
from services.search_orchestrator import _load_demo_cache

logger = logging.getLogger("onyx.fetch")

router = APIRouter(tags=["fetch"])

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")


def _demo_snapshot_content(req: FetchRequest) -> str:
    """Build a clean structured marketplace snapshot for DEMO_MODE (no network)."""
    url = str(req.url)
    query = ""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        query = (qs.get("q") or qs.get("k") or [""])[0]
    except Exception:
        pass
    query = query.strip()

    netloc = urlparse(url).netloc or "marketplace"
    lines = [
        f"# Demo Snapshot — {netloc}",
        "",
        "> **DEMO MODE:** live crawl disabled in this build. Showing cached marketplace snapshot from the demo dataset.",
        "",
    ]

    cache = _load_demo_cache()
    matches = []
    for key, results in cache.items():
        if not results:
            continue
        score = fuzz.token_set_ratio(query.lower(), key.lower()) if query else 0
        if score >= 60:
            matches.append((score, key, results))
    matches.sort(key=lambda m: m[0], reverse=True)

    rows = []
    for _score, key, results in matches[:5]:
        for item in results:
            name = item.get("product_name") or key
            price = item.get("price")
            price_s = f"₹{price:,.2f}" if isinstance(price, (int, float)) else str(price or "—")
            rows.append(
                {
                    "product": name,
                    "price": price_s,
                    "source": item.get("source_name", "Marketplace"),
                    "vendor": item.get("vendor_name", "—"),
                    "availability": item.get("availability", "In Stock"),
                    "confidence": item.get("confidence", "HIGH"),
                    "evidence": item.get("source_url", url),
                }
            )
        if len(rows) >= 12:
            break

    if rows:
        lines.append("| # | Product | Price | Source | Vendor | Availability | Confidence | Evidence |")
        lines.append("|---|---------|-------|--------|--------|--------------|------------|----------|")
        for idx, r in enumerate(rows, start=1):
            evidence_host = urlparse(r["evidence"]).netloc or "link"
            lines.append(
                f"| {idx} | {r['product']} | {r['price']} | {r['source']} "
                f"| {r['vendor']} | {r['availability']} | {r['confidence']} "
                f"| [{evidence_host}]({r['evidence']}) |"
            )
        lines.append("")
        lines.append(f"*{len(rows)} listing(s) matched the query — all entries carry audit metadata from the demo dataset.*")
    else:
        lines += [
            "No cached snapshot matched this URL.",
            "",
            "The demo dataset covers: Cisco switches, HP ProBooks, A4 paper,",
            "executive chairs, SDR radios, radar waveguides, VHF transceivers,",
            "AC units, laser printers, and AMC contracts.",
        ]
    return "\n".join(lines)


# POST /fetch
@router.post(
    "/fetch",
    response_model=FetchResponse,
    dependencies=[Depends(verify_api_key)],
)
async def fetch_endpoint(req: FetchRequest):
    start = time.monotonic()

    if DEMO_MODE:
        content = _demo_snapshot_content(req)
        return FetchResponse(
            success=True,
            url=str(req.url),
            status_code=200,
            output_format=req.output_format,
            content=content,
            session_id=None,
            latency_ms=int((time.monotonic() - start) * 1000),
            retries_used=0,
        )

    logger.info(
        f"Received fetch request: {req.method} {req.url} (format: {req.output_format})"
    )

    # Determine session
    sid = req.session_id
    engine = "playwright" if req.render_js else "curl"
    session = None

    if sid:
        session = await session_manager.get_or_create(sid, engine)
    elif req.render_js:
        sid = None

    proxy_url = req.proxy.url if req.proxy else None

    result = await run_fetch(
        url=str(req.url),
        method=req.method.upper(),
        headers=req.headers,
        cookies=req.cookies,
        body=req.body,
        json_body=req.json_body,
        session=session,
        render_js=req.render_js,
        scroll=req.scroll,
        proxy_url=proxy_url,
        max_retries=req.max_retries,
        timeout=req.timeout,
        impersonate=req.impersonate,
        playwright_mgr=playwright_mgr,
        output_format=req.output_format,
        strip_links=req.strip_links,
        llm_api_key=req.llm_api_key,
        llm_provider=req.llm_provider,
        json_schema=req.json_schema,
        wait_for_selector=req.wait_for_selector,
        wait_timeout=req.wait_timeout,
        css_selector=req.css_selector,
        llm_model=req.llm_model,
        actions=req.actions,
        screenshot=req.screenshot,
        screenshot_format=req.screenshot_format,
        extraction_prompt=req.extraction_prompt,
        wait_until=req.wait_until,
        stealth=req.stealth,
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    success = result.get("error") is None

    logger.info(f"Fetch request resolved in {latency_ms}ms with success={success}")

    return FetchResponse(
        success=success,
        url=result.get("final_url", str(req.url)),
        status_code=result.get("status_code", 0),
        output_format=req.output_format,
        content=result.get("content") or "",
        session_id=sid,
        latency_ms=latency_ms,
        retries_used=result.get("retries_used", 0),
        error=result.get("error"),
        error_message=result.get("error_message"),
        screenshot=result.get("screenshot"),
        timing=result.get("timing"),
    )


# GET /api/sessions
@router.get("/api/sessions", dependencies=[Depends(verify_api_key)])
async def list_sessions():
    return await session_manager.list_sessions()


# DELETE /api/sessions/{session_id}
@router.delete("/api/sessions/{session_id}", dependencies=[Depends(verify_api_key)])
async def delete_session(session_id: str):
    if not await session_manager.get_session_meta(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    await session_manager.delete_session(session_id)
    return {"deleted": True, "session_id": session_id}
