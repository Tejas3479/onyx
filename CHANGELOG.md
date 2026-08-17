# Changelog

All notable changes to Onyx are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Removed
- **Crawlix multi-page crawl pipeline** — removed `routers/crawl.py`, `services/crawl_manager.py`, `worker.py` (ARQ background worker), the `CrawlJob`/`BatchJob`/`Destination`/`ScheduledCrawl` tables, `arq`/`croniter`/`pinecone-client`/`weaviate-client`/`supabase` dependencies, the Docker `worker` service, and the dead front-end bundles. The single-URL anti-bot fetch engine (`/fetch`) that powers Tier 3 market survey is retained. Migration `9bdeb31f1488` drops the crawl tables.
- **Crawlix branding** — remaining "Crawlix" references scrubbed from UI and docs.

### Fixed
- JWT secret handling: missing/whitespace `JWT_SECRET_KEY` now fails fast instead of silently falling back to an insecure default.

### Security
- JWT enforcement on benchmark, report, and department-LPP endpoints. When `AUTH_DISABLED=true` (dev/demo) requests pass through anonymously; otherwise a valid Bearer JWT is mandatory (`routers/auth_routes.py:require_current_user`).
- Benchmark results now persist the real authenticated user id instead of a hardcoded `anonymous`.
- Department LPP uploads record the signed-in officer's email.
- Officer identity on the UI certificate is taken from the real signed-in JWT profile; the hardcoded officer-cycling list was removed.

---

## [2.0.0] — 2026-08-14

### Major Release — GFR Rule 149(vii) Price Reasonability Engine
Transformed Onyx into an automated price reasonability and market survey platform for government procurement, implementing the 5-tier waterfall hierarchy prescribed under General Financial Rules (GFR) 2017 Rule 149(vii).

### Added
- **5-Tier GFR Waterfall Engine (`services/tier_waterfall.py`)**:
  - **Tier 0 (Notified Rates):** Automated lookup of DGS&D rate contracts and Ministry-notified rates (`services/gem_rate_lookup.py`).
  - **Tier 1 (GeM Business Analytics & LPP):** Querying GeM Last Purchase Price (LPP) and verified marketplace catalog listings.
  - **Tier 2 (Department LPP Ingestion):** Historical department purchase record uploads (`.csv`, `.xlsx`) with fuzzy matching via `rapidfuzz` (`services/department_lpp.py`).
  - **Tier 3 (Multi-Source Online Market Survey):** Parallel concurrent querying of 6+ marketplaces (GeM, Amazon India, IndiaMART, Flipkart, CPPP, Google Shopping) with automatic outlier detection and reliability scoring (`services/search_orchestrator.py`).
  - **Tier 4 (Non-Standard Item Estimator):** Estimation for custom items (waveguides, antennas, SDRs) via spec-similarity ratios, landed import cost modeling (AliExpress/Customs), and automatic Local Purchase Committee referral recommendations (`services/non_standard_estimator.py`).
- **GFR Reasonability Certificate & Report Generator (`services/report_generator.py`)**:
  - Audit-ready Jinja2 HTML/PDF report template (`templates/report_template.html`) including tier traces, pricing statistics (Min/Max/Avg/Median), and officer signature blocks.
- **Dedicated Procurement Endpoints**:
  - `POST /api/v1/benchmark` — Main price reasonability waterfall endpoint.
  - `POST /api/v1/estimate/non-standard` — Standalone Tier 4 estimator endpoint.
  - `POST /api/v1/department-lpp/upload` & `GET /api/v1/department-lpp/records` — Department LPP management.
  - `POST /api/v1/reports/generate-from-query` — Direct report generation.
- **Authentication & User Management (`routers/auth_routes.py`)**:
  - User registration and JWT-based authentication for procurement officers.
- **GSA CALC-Inspired UI (`static/benchmark.html`)**:
  - Clean, responsive, government-grade user interface with real-time tier badge indicators, interactive waterfall traces, pricing statistics, and direct report downloads.
- **Automated Data Seeder (`services/data_seeder.py`)**:
  - Startup loader for DGS&D notified rates (`data/notified_rates.json`), GeM LPP reference cache (`data/gem_lpp_seed.json`), and demo survey cache (`data/demo_cache.json`).

### Changed
- Rebranded and refactored core architecture from scraper-only to dual procurement intelligence + scraping platform.
- Upgraded test suite with full tier waterfall coverage.

---

## [1.2.0] — 2026-07-28

### Added
- **AI Vector Pipelines** — Push embeddings natively to Pinecone, Weaviate, and Supabase via new `Destination` configurations.
- **Scheduled Crawls** — Schedule recurring extractions using `croniter` and the ARQ background worker.
- **Client SDKs** — Official Python and Node.js (TypeScript) SDKs for easy integration.
- **Captcha Solving** — Integration with 2Captcha and CapSolver for bypassing complex anti-bot challenges during scraping.
- **Database Backend** — Shifted core states (Jobs, API Keys, Proxies, Destinations) to SQLite via SQLModel/SQLAlchemy.
- **API Key DB Support** — `verify_api_key` now checks both `VALID_KEYS` environment variable and SQLite `ApiKey` table.
- **Docker Image CI** — Automated Docker build testing in GitHub Actions.

### Changed
- Replaced legacy `SESSIONS_FILE` and `CRAWLS_FILE` disk writes with proper SQLite database backend.
- Updated `worker.py` and `app.py` with Python 3.9+ type annotations (`dict` instead of `Dict`) for `ruff` compliance.
- Dockerfile now runs `apt-get` update prior to `playwright install-deps` to fix broken package cache.

---

## [1.1.0] — 2026-07-22

### Added
- **Environment Variables Panel** — Save named API keys (Production, Test, Staging) in sidebar. Chip UI for instant switching. Masked display (`myke••••3x9a`). Persisted in `localStorage`.
- **Request Timing Waterfall** — Real server-side timing breakdown below meta bar: Security / Connect / TTFB / Processing phases. Proportional colored segments with hover tooltips and ms legend.
- **Request History** — Last 20 requests stored in `localStorage`. Sidebar panel with click-to-replay. Keyboard accessible (Enter/Space to replay). Clear button with confirmation.
- **Keyboard Shortcuts** — `Ctrl+Enter` / `Cmd+Enter` sends request. `Ctrl+K` / `Cmd+K` focuses URL bar. Works cross-platform.
- **Preview Theme Toggle** — Light/dark background switcher above iframe preview. State persists within session.
- **Visibility-aware Polling** — Health checks and session refresh pause when the browser tab is hidden. Resumes on tab focus.
- **Crawl extraction prompt** — Separate `<textarea>` for the crawl section, no longer shared with request builder.
- **XSS-safe JSON tree** — `renderJsonTree()` now HTML-escapes all keys and values via `escapeHtml()` before `innerHTML`.
- **SEO/A11y improvements** — `<title>`, `<meta name="description">`, SVG favicon, `<h1 class="sr-only">`, `prefers-reduced-motion` media query, `focus-visible` rings on all interactive elements.
- **JetBrains Mono font** — Code and monospace elements now use JetBrains Mono.
- **Timing fields in API response** — `FetchResponse` now includes a `timing` object with `security_ms`, `connect_ms`, `ttfb_ms`, `transfer_ms`, `total_ms`.

### Fixed
- **CRITICAL** — CORS misconfiguration: `allow_origins=["*"]` + `allow_credentials=True` is invalid per spec. Fixed to `allow_credentials=False`.
- **CRITICAL** — `is_ssrf_safe()` was synchronous DNS resolution inside an async route, blocking the event loop. Converted to `async def` using `loop.run_in_executor()`.
- **CRITICAL** — Race condition on `playwright_mgr.slots_free` counter. Added `asyncio.Lock` (`_slots_lock`) to guard all read-modify-write operations.
- **CRITICAL** — `import uuid` and `import base64` were mid-file (line 856+). Moved to top-of-file import block.
- **CRITICAL** — Duplicate `logging.basicConfig()` call in `fetcher.py`. Removed — `app.py` is the single source of truth.
- **CRITICAL** — `datetime.utcnow()` deprecated in Python 3.12+. All instances replaced with `datetime.now(timezone.utc)`.
- **HIGH** — Anthropic model `claude-3-haiku-20240307` deprecated. Updated to `claude-3-5-haiku-20241022`.
- **HIGH** — `cleanup_loop` did not handle `asyncio.CancelledError` on shutdown. Wrapped in `try/except asyncio.CancelledError`.
- **HIGH** — `MAX_SESSIONS` eviction used `>` instead of `>=`, allowing one extra session beyond the limit.
- **HIGH** — Crawl section shared `#extraction-prompt-textarea` with the request builder. Now uses dedicated `#crawl-extraction-prompt`.
