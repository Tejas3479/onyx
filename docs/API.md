# Onyx API Reference

**Base URL:** `http://localhost:8000`  
**Authentication:** 
- **Procurement & Protected Endpoints:** Header `x-api-key: <your-key>` or `Authorization: Bearer <jwt-token>`
- **Health Check (`/api/health`):** No authentication required

---

## 📑 Table of Contents

- [Procurement & Price Benchmarking (GFR 149(vii))](#procurement--price-benchmarking-gfr-149vii)
  - [POST /api/v1/benchmark](#post-apiv1benchmark)
  - [POST /api/v1/estimate/non-standard](#post-apiv1estimatenon-standard)
  - [POST /api/v1/department-lpp/upload](#post-apiv1department-lppupload)
  - [GET /api/v1/department-lpp/records](#get-apiv1department-lpprecords)
  - [DELETE /api/v1/department-lpp/records](#delete-apiv1department-lpprecords)
  - [POST /api/v1/reports/generate-from-query](#post-apiv1reportsgenerate-from-query)
- [Authentication & User Management](#authentication--user-management)
  - [POST /auth/register](#post-authregister)
  - [POST /auth/login](#post-authlogin)
- [Core Scraping & Extraction](#core-scraping--extraction)
  - [POST /fetch](#post-fetch)
- [Crawling & Batch Processing](#crawling--batch-processing)
  - [POST /api/crawl](#post-apicrawl)
  - [GET /api/crawl](#get-apicrawl)
  - [GET /api/crawl/{id}](#get-apicrawlid)
  - [DELETE /api/crawl/{id}](#delete-apicrawlid)
  - [POST /api/crawl/batch](#post-apicrawlbatch)
  - [GET /api/crawl/batch/{id}](#get-apicrawlbatchid)
  - [GET /api/crawl/batch/{id}/download](#get-apicrawlbatchiddownload)
- [Browser Session Management](#browser-session-management)
  - [GET /api/sessions](#get-apisessions)
  - [DELETE /api/sessions/{id}](#delete-apisessionsid)
- [Admin & Configuration](#admin--configuration)
  - [POST /api/destinations](#post-apidestinations)
  - [GET /api/destinations](#get-apidestinations)
  - [DELETE /api/destinations/{id}](#delete-apidestinationsid)
  - [POST /api/schedule](#post-apischedule)
  - [GET /api/schedule](#get-apischedule)
  - [DELETE /api/schedule/{id}](#delete-apischeduleid)
  - [POST /api/proxies](#post-apiproxies)
  - [GET /api/proxies](#get-apiproxies)
  - [DELETE /api/proxies/{id}](#delete-apiproxiesid)
  - [GET /api/health](#get-apihealth)

---

# Procurement & Price Benchmarking (GFR 149(vii))

### POST /api/v1/benchmark

Executes the full 5-tier GFR Rule 149(vii) waterfall price reasonability check.

#### Request Body
```json
{
  "product_name": "HP ProBook 450",
  "query_mode": "product",
  "department": "Ministry of Electronics & IT",
  "category": "IT Equipment",
  "specs": {
    "ram_gb": 16,
    "storage_gb": 512
  },
  "quantity": 10
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `product_name` | string | **Yes** | Product name, model, or service description |
| `query_mode` | string | No | `"product"` (default), `"model"`, or `"custom"` |
| `department` | string | No | Department or Ministry name for Tier 2 lookup |
| `category` | string | No | Item category (e.g., `"IT Equipment"`, `"Stationery"`) |
| `specs` | object | No | Technical specifications dictionary |
| `quantity` | integer | No | Quantity being procured (default: 1) |

#### Response (`200 OK`)
```json
{
  "search_id": "9965eb1a-1d11-477d-8eb0-f9660ad50e8a",
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
    "price_range_low": null,
    "price_range_high": null,
    "currency": "INR",
    "confidence": "HIGH",
    "reliability": "HIGH",
    "evidence_url": "https://mkp.gem.gov.in/laptops/hp-probook-450-g10/p-5123456",
    "rationale": "GeM Last Purchase Price for 'HP ProBook 450 G10 Notebook PC'. Match score: 100%.",
    "is_demo_data": true
  },
  "all_results": [
    {
      "tier": 1,
      "tier_label": "GeM Business Analytics",
      "source_name": "GeM Last Purchase Price",
      "price": 71500.0,
      "price_range_low": null,
      "price_range_high": null,
      "currency": "INR",
      "confidence": "HIGH",
      "reliability": "HIGH",
      "evidence_url": "https://mkp.gem.gov.in/laptops/hp-probook-450-g10/p-5123456",
      "rationale": "GeM Last Purchase Price for 'HP ProBook 450 G10 Notebook PC'. Match score: 100%.",
      "is_demo_data": true
    }
  ],
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

### POST /api/v1/estimate/non-standard

Dedicated endpoint for Tier 4 estimation of non-standard, custom, or complex equipment (waveguides, antennas, software-defined radios).

#### Request Body
```json
{
  "product_name": "Waveguide Adapter WR-90 to SMA Female",
  "specs": {
    "frequency_ghz": 10.5,
    "power_watts": 50
  },
  "category": "Microwave / RF Equipment"
}
```

#### Response (`200 OK`)
```json
{
  "source_name": "Non-Standard Estimate (Spec Similarity)",
  "price": 14250.0,
  "price_range_low": 12112.5,
  "price_range_high": 17812.5,
  "currency": "INR",
  "evidence_url": null,
  "rationale": "Estimated from 2 similar item(s) with avg match score 78%. Weighted average: ₹12,390.00, adjusted by 1.15x for spec differences.",
  "confidence": "MEDIUM",
  "reliability": "LOW",
  "method_used": "spec_similarity",
  "comparable_items": [
    {
      "item": "WR-90 Waveguide Flange Standard",
      "price": 11500.0,
      "match_score": 0.82,
      "source": "Dept Record (DRDO)"
    }
  ],
  "spec_match_score": 0.78
}
```

---

### POST /api/v1/department-lpp/upload

Upload internal department purchase history spreadsheets to enable Tier 2 matching.

- **Content-Type:** `multipart/form-data`
- **File formats supported:** `.csv`, `.xlsx`, `.xls`
- **Expected columns:** `item_description` (or `item_name`/`product`), `unit_price` (or `rate`/`price`), `department`, `purchase_date`, `quantity`, `seller_name` (optional).

#### Response (`200 OK`)
```json
{
  "filename": "meity_purchase_orders_2024.xlsx",
  "records_ingested": 142,
  "status": "success",
  "department": "Ministry of Electronics & IT"
}
```

---

### GET /api/v1/department-lpp/records

List historical department purchase records stored in the database.

#### Query Parameters
- `department` (optional): Filter by department name
- `limit` (optional, default: 50): Number of records to return

---

### DELETE /api/v1/department-lpp/records

Delete department purchase records.

#### Query Parameters
- `department` (optional): Delete records for a specific department only (if omitted, clears all records).

---

### POST /api/v1/reports/generate-from-query

Generates an official GFR Price Reasonability Certificate in HTML or PDF format.

#### Query Parameters
- `product_name` (**required**): Product name to benchmark
- `department_name` (optional): Name of the purchasing department
- `signatory_name` (optional): Officer name for signature block (default: `"Authorized Officer"`)
- `output_format` (optional, default: `"html"`): `"html"` or `"pdf"`

#### Response
- Returns `text/html` or `application/pdf` inline file download.

---

# Authentication & User Management

### POST /auth/register

Register a procurement officer account.

#### Request Body
```json
{
  "name": "Rajesh Sharma",
  "email": "r.sharma@gov.in",
  "password": "SecurePassword123!",
  "department": "Ministry of Electronics & IT",
  "organization": "National Informatics Centre"
}
```

---

### POST /auth/login

Authenticate user credentials and receive a JWT Bearer token.

#### Request Body
```json
{
  "email": "r.sharma@gov.in",
  "password": "SecurePassword123!"
}
```

#### Response (`200 OK`)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

# Core Scraping & Extraction

### POST /fetch

Fetch a single URL. Supports both lightweight HTTP (`curl-cffi`) and full JS rendering (Playwright).

#### Request Body
```json
{
  "url": "https://example.com",
  "method": "GET",
  "output_format": "markdown",
  "render_js": false,
  "headers": {},
  "cookies": {},
  "body": null,
  "json_body": null,
  "session_id": null,
  "scroll": false,
  "proxy": null,
  "max_retries": 0,
  "timeout": 30,
  "impersonate": "chrome120",
  "strip_links": false,
  "css_selector": null,
  "wait_for_selector": null,
  "wait_timeout": 30,
  "wait_until": "networkidle",
  "actions": [],
  "screenshot": false,
  "screenshot_format": "png",
  "llm_api_key": null,
  "llm_provider": "openai",
  "llm_model": null,
  "json_schema": null,
  "extraction_prompt": null,
  "stealth": false
}
```

---

# Crawling & Batch Processing

### POST /api/crawl
Start an asynchronous recursive site crawl.

### GET /api/crawl
List all recent crawl jobs.

### GET /api/crawl/{id}
Poll crawl job status & retrieved pages.

### DELETE /api/crawl/{id}
Delete a crawl job and its results.

### POST /api/crawl/batch
Start a batch crawl job via file upload.

### GET /api/crawl/batch/{id}
Poll batch crawl status & progress.

### GET /api/crawl/batch/{id}/download
Download batch results in CSV/JSON format.

---

# Browser Session Management

### GET /api/sessions
List active browser sessions and cookie state.

### DELETE /api/sessions/{id}
Destroy a browser session and release cookies.

---

# Admin & Configuration

### POST /api/destinations
Register a vector DB destination (Pinecone / Weaviate / Supabase).

### POST /api/schedule
Create a recurring cron crawl schedule.

### POST /api/proxies
Register a proxy server.

### GET /api/health
Health status endpoint (returns `{"status": "ok"}`).
