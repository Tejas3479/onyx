<div align="center">

<h1>◆ Onyx</h1>
<p><strong>AI-Powered Price Reasonability & Market Survey Platform for Public Procurement</strong></p>
<p><em>Fully compliant with General Financial Rules (GFR) 2017 Rule 149(vii) & Manual for Procurement of Goods</em></p>

[![License: MIT](https://img.shields.io/badge/License-MIT-7c6cf0.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-60a5fa.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-34d399.svg)](https://fastapi.tiangolo.com/)
[![GFR Rule 149(vii)](https://img.shields.io/badge/Compliance-GFR%20Rule%20149(vii)-059669.svg)](https://doe.gov.in)
[![Docker](https://img.shields.io/badge/Docker-ready-60a5fa.svg)](docker-compose.yml)
[![Test Suite](https://img.shields.io/badge/Tests-Passing%20(15%2F15)-brightgreen.svg)](tests/)

</div>

---

## 🏛️ What is Onyx?

**Onyx** is an automated price benchmarking and reasonability platform built for government departments, public sector units (PSUs), and procurement officers. It establishes legally defensible, audit-ready price reasonability by strictly executing the **GFR 2017 Rule 149(vii)** order of precedence:

1. **Tier 0 — Notified Rates & Rate Contracts**: Official DGS&D and Ministry-notified rates.
2. **Tier 1 — GeM Business Analytics & LPP**: GeM Last Purchase Price (LPP) and verified marketplace catalog listings.
3. **Tier 2 — Department's Own LPP**: Internal historical purchase data uploaded via CSV/Excel with fuzzy matching (`rapidfuzz`).
4. **Tier 3 — Multi-Source Online Market Survey**: Parallel real-time web surveys across GeM, Amazon India, IndiaMART, Flipkart, CPPP, and Google Shopping with automated outlier filtering and statistical confidence scoring.
5. **Tier 4 — Non-Standard Item Estimator**: Spec-similarity extrapolation, landed import cost modeling (AliExpress/Customs), and automated Local Purchase Committee (LPC) referral workflows for custom equipment (waveguides, antennae, SDRs, bespoke fabrications).

Onyx combines this procurement intelligence with a high-performance **underlying scraping, browser automation (Playwright), and anti-bot evasion engine (`curl-cffi`)**.

---

## ⚡ The 5-Tier Waterfall Architecture

```mermaid
flowchart TD
    START([User Enters Procurement Query<br/>Product Name / Specs / Dept / Category]) --> T0{Tier 0: Notified Rate?}
    
    T0 -- "✓ Match in DGS&D / Ministry Rates" --> R0[Resolve at Tier 0: Notified Rate]
    T0 -- "✗ No Rate Contract" --> T1{Tier 1: GeM Analytics / LPP?}
    
    T1 -- "✓ Found GeM LPP / Catalog Price" --> R1[Resolve at Tier 1: GeM LPP]
    T1 -- "✗ Not on GeM / No LPP" --> T2{Tier 2: Dept Own LPP?}
    
    T2 -- "✓ Found in Uploaded Dept Records" --> R2[Resolve at Tier 2: Dept LPP]
    T2 -- "✗ No Dept History" --> T3{Tier 3: Market Survey?}
    
    T3 -- "✓ Multiple Online Quotes Found" --> R3[Resolve at Tier 3: Market Survey<br/>Amazon, GeM, IndiaMART, Flipkart, Google]
    T3 -- "✗ No Direct Listings" --> T4[Tier 4: Non-Standard Estimator<br/>Spec-Similarity / Landed Import / LPC Referral]
    
    R0 --> REPORT[Generate GFR Reasonability Certificate & PDF/HTML Report]
    R1 --> REPORT
    R2 --> REPORT
    R3 --> REPORT
    T4 --> REPORT
```

---

## ✨ Key Features

| Capability | Description |
|---|---|
| ⚖️ **GFR 149(vii) Waterfall Engine** | Deterministic waterfall traversal prioritizing statutory rate contracts & GeM before market surveys. |
| 📊 **Department LPP Ingestion** | Upload internal department procurement archives (CSV/Excel) with fuzzy semantic matching and date weighting. |
| 🌐 **Parallel Market Survey Orchestrator** | Concurrently queries 6+ e-marketplaces (GeM, Amazon, IndiaMART, Flipkart, CPPP, Google Shopping) using `asyncio.gather`. |
| 📐 **Non-Standard Equipment Estimator** | Solves complex bespoke procurement (waveguides, microwave components, SDRs) via spec-similarity ratios and landed cost basis. |
| 📑 **Audit-Ready GFR Reports** | One-click export of formal Price Reasonability Certificates with complete tier traces, price statistics, and signature blocks. |
| 🖥️ **GSA CALC-Inspired UI** | Fast, data-dense web interface (`/benchmark.html`) designed for procurement workflows without visual clutter. |
| 🕵️ **Stealth Browser Engine** | Built-in Playwright headless browser pool + `curl-cffi` TLS fingerprint impersonation for robust data extraction. |
| 🛡️ **SSRF & Security Isolation** | Async DNS validation blocks internal subnet access; JWT auth + API key header validation for protected endpoints. |

---

## 🚀 Quick Start

### 1. Run with Docker (Recommended)

```bash
git clone https://github.com/Tejas3479/onyx.git
cd onyx

# Launch Onyx services (Web app + Worker + Redis)
API_KEYS=onyx-secret-key docker-compose up -d
```

Open **http://localhost:8000/benchmark.html** in your browser.

---

### 2. Local Python Setup

```bash
git clone https://github.com/Tejas3479/onyx.git
cd onyx

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies and Playwright browser binaries
pip install -r requirements.txt
playwright install chromium

# Launch the server (seeds reference data automatically on startup)
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

- **Price Benchmark UI:** `http://localhost:8000/benchmark.html`
- **Department LPP Upload:** `http://localhost:8000/upload_history.html`
- **Advanced Scraping Console:** `http://localhost:8000/`
- **Interactive API Docs (Swagger):** `http://localhost:8000/docs`

---

## 📡 API Reference Overview

See [docs/API.md](docs/API.md) for full request/response schemas and examples.

### Core Procurement & Benchmark Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/benchmark` | Execute 5-tier GFR waterfall price reasonability check |
| `POST` | `/api/v1/estimate/non-standard` | Dedicated Tier 4 estimator for custom/uncommon items |
| `POST` | `/api/v1/department-lpp/upload` | Upload Department LPP records (CSV / XLSX) |
| `GET` | `/api/v1/department-lpp/records` | Query uploaded department purchase history |
| `DELETE` | `/api/v1/department-lpp/records` | Clear department purchase records |
| `POST` | `/api/v1/reports/generate-from-query` | Generate official GFR HTML/PDF Reasonability Report |
| `POST` | `/auth/register` | Register procurement officer account |
| `POST` | `/auth/login` | Login and receive JWT access token |

### Scraping & Browser Automation Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/fetch` | Direct fetch with TLS impersonation or Playwright JS rendering |
| `POST` | `/api/crawl` | Initiate asynchronous recursive crawler |
| `GET` | `/api/sessions` | Inspect active persistent browser sessions |
| `GET` | `/api/health` | System health check (No auth required) |

---

## 🧪 Example API Query

### Run Price Benchmark

```bash
curl -X POST http://localhost:8000/api/v1/benchmark \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "HP ProBook 450",
    "query_mode": "product",
    "department": "Ministry of Electronics & IT",
    "category": "IT Equipment",
    "quantity": 5
  }'
```

### Example Response (Tier 1 Match)

```json
{
  "search_id": "7f8b9a1c-3e2d-4f1a-b5c6-d7e8f9a0b1c2",
  "query": "HP ProBook 450",
  "query_mode": "product",
  "status": "completed",
  "resolved_tier": 1,
  "tier_label": "GeM Business Analytics",
  "primary_result": {
    "tier": 1,
    "tier_label": "GeM Business Analytics",
    "source_name": "GeM Last Purchase Price",
    "price": 71500.0,
    "currency": "INR",
    "confidence": "HIGH",
    "reliability": "HIGH",
    "evidence_url": "https://mkp.gem.gov.in/laptops/hp-probook-450-g10/p-5123456",
    "rationale": "GeM Last Purchase Price for 'HP ProBook 450 G10 Notebook PC'. Match score: 100%."
  },
  "tier_trace": {
    "tier_0": "No matching active notified rate found",
    "tier_1": "Found: GeM Last Purchase Price (₹71,500.00)"
  },
  "statistics": {
    "min": 71500.0,
    "max": 74200.0,
    "avg": 72850.0,
    "median": 72850.0,
    "count": 2
  },
  "sources_checked": 2,
  "results_found": 2
}
```

---

## 🏛️ GFR 2017 Rule 149(vii) Compliance Matrix

| GFR Mandate | Onyx Implementation | Verification Mechanism |
|---|---|---|
| **1. Notified Rates / DGS&D** | `Tier 0` checks active ministry notified rate schedules. | Authority, contract number, and validity dates checked against DB. |
| **2. GeM Business Analytics / LPP** | `Tier 1` queries GeM LPP caches and verified catalog endpoints. | GeM Product ID, seller identification, and transaction history. |
| **3. Department LPP** | `Tier 2` inspects uploaded historical department orders. | Semantic text + spec similarity scoring (`rapidfuzz`). |
| **4. Market Survey** | `Tier 3` executes multi-marketplace parallel survey. | Interquartile outlier exclusion + reliability scoring. |
| **5. Non-Standard Items** | `Tier 4` performs spec-ratio extrapolation & landed import costing. | Rationale output with mandatory Local Purchase Committee referral. |

---

## 🛠️ Tech Stack

- **Backend Framework:** FastAPI, Uvicorn, SQLModel / SQLAlchemy, Pydantic v2
- **Data & Matching:** SQLite / PostgreSQL, `rapidfuzz`, `pandas`, `openpyxl`
- **Scraping Engine:** Playwright (Chromium), `curl-cffi` (HTTP/2 & TLS impersonation)
- **Reporting:** Jinja2, HTML5 Print Stylesheets / WeasyPrint
- **Frontend:** Vanilla JS (ES6+), GSA CALC Design System, Semantic CSS

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Verify test suite: `pytest` and `ruff check .`
4. Commit your changes: `git commit -m 'feat: add feature'`
5. Push to branch and open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
