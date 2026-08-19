import json
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

# ALLOWED LLM MODELS ALLOWLIST
ALLOWED_LLM_MODELS = {
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-4o",
    "gpt-4o-mini",
    "o4-mini",
    "o3-pro",
    "o3-mini",
    "claude-fable-5",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5",
    "claude-3-5-sonnet-20241022",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
}


# PYDANTIC SCHEMAS
class ProxyConfig(BaseModel):
    url: str = Field(
        ...,
        max_length=2000,
        description="Full proxy URL e.g. http://user:pass@host:port",
    )
    country_code: str | None = Field(None, max_length=10)

    @field_validator("url")
    @classmethod
    def validate_proxy_url(cls, v: str) -> str:
        v_str = v.strip()
        parsed = urlparse(v_str)
        if parsed.scheme.lower() not in (
            "http",
            "https",
            "socks5",
            "socks4",
            "socks5h",
        ):
            raise ValueError("Proxy URL scheme must be http, https, socks5, or socks4")
        if not parsed.netloc:
            raise ValueError("Invalid proxy URL format")
        return v_str


class ActionConfig(BaseModel):
    type: Literal["click", "wait", "scroll", "fill", "hover", "press"]
    selector: str | None = Field(None, max_length=500)
    value: str | None = Field(None, max_length=2000)
    duration: int | None = Field(None, ge=0, le=60)


class FetchRequest(BaseModel):
    url: HttpUrl
    method: str = Field("GET", max_length=10)
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    body: str | None = Field(None, max_length=10_000_000)  # 10MB max body
    json_body: dict | None = None
    session_id: str | None = Field(None, max_length=100)
    render_js: bool = False
    scroll: bool = False
    output_format: Literal["html", "markdown", "structured"] = "html"
    strip_links: bool = False
    proxy: ProxyConfig | None = None
    max_retries: int = Field(2, ge=0, le=5)
    timeout: int = Field(30, ge=1, le=120)
    impersonate: str = Field("chrome120", max_length=50)
    llm_api_key: str | None = Field(None, max_length=500)
    llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    json_schema: dict | None = None
    wait_for_selector: str | None = Field(None, max_length=500)
    wait_timeout: int = Field(30, ge=1, le=120)
    css_selector: str | None = Field(None, max_length=500)
    llm_model: str | None = Field(None, max_length=100)
    actions: list[ActionConfig] | None = Field(None, max_length=20)
    screenshot: bool = False
    screenshot_format: Literal["png", "jpeg"] = "png"
    extraction_prompt: str | None = Field(None, max_length=5000)
    wait_until: Literal["domcontentloaded", "load", "networkidle"] = "networkidle"
    stealth: bool = False

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: HttpUrl) -> HttpUrl:
        scheme = v.scheme.lower() if v.scheme else ""
        if scheme not in ("http", "https"):
            raise ValueError("Target URL scheme must be http or https")
        return v

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean:
            return None
        if v_clean not in ALLOWED_LLM_MODELS and not any(
            v_clean.startswith(prefix)
            for prefix in ("gpt-", "claude-", "gemini-", "o1", "o3")
        ):
            raise ValueError(
                f"LLM model '{v_clean}' is not supported. Must be a valid OpenAI, Anthropic, or Gemini model."
            )
        return v_clean

    @field_validator("json_schema")
    @classmethod
    def validate_json_schema_size(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        serialized = json.dumps(v)
        if len(serialized) > 50_000:
            raise ValueError("JSON schema size exceeds maximum limit of 50KB")
        return v


class FetchResponse(BaseModel):
    success: bool
    url: str
    status_code: int
    output_format: str
    content: str | dict
    session_id: str | None
    latency_ms: int
    retries_used: int
    error: str | None = None
    error_message: str | None = None
    screenshot: str | None = None
    timing: dict | None = None


class ProxyCreate(BaseModel):
    url: str


# ===== ONYX: Price Benchmarking Schemas =====


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=200)
    password: str = Field(..., min_length=8, max_length=100)
    department: str | None = Field(None, max_length=200)
    organization: str | None = Field(None, max_length=200)


class UserLogin(BaseModel):
    email: str
    password: str


class DemoLoginRequest(BaseModel):
    """One-click simulated officer profile, only honored while DEMO_MODE=true."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Shri R. K. Sharma",
                    "email": "r.sharma@mod.gov.in",
                    "department": "Ministry of Defence",
                }
            ]
        }
    )

    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=200)
    department: str | None = Field(None, max_length=200)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    department: str | None
    organization: str | None
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SearchQuery(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=500)
    query_type: Literal["make_model", "specifications"] = "make_model"
    category: str | None = Field(None, max_length=100)
    quantity: int = Field(1, ge=1, le=10000)


class SearchResultItem(BaseModel):
    source_name: str
    source_url: str
    product_name: str | None
    brand: str | None
    model_number: str | None
    price: float | None
    currency: str
    vendor_name: str | None
    availability: str | None
    confidence: str
    screenshot_url: str | None


class SearchResponse(BaseModel):
    search_id: str
    query: str
    status: str
    results: list[SearchResultItem]
    statistics: dict  # min, max, avg, median
    sources_checked: int
    results_found: int


class ReportRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "search_id": "a1b2c3d4-e5f6-4a5b-9c8d-1e2f3a4b5c6d",
                    "department_name": "Ministry of Defence",
                    "signatory_name": "Shri R. K. Sharma",
                    "include_screenshots": True,
                    "output_format": "html",
                }
            ]
        }
    )

    search_id: str
    department_name: str | None = None
    signatory_name: str | None = None
    include_screenshots: bool = True
    output_format: str = "html"


class ReportFromQueryRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "product_name": "Cisco Catalyst 9300 Switch",
                    "department_name": "Ministry of Defence",
                    "signatory_name": "Shri R. K. Sharma",
                    "estimated_value": 576000,
                    "delivery_location": "New Delhi",
                    "specs": {"Processor": "Intel Core i5-13th Gen"},
                    "output_format": "pdf",
                }
            ]
        }
    )

    product_name: str
    department_name: str | None = None
    signatory_name: str | None = None
    quantity: int = 1
    category: str | None = None
    estimated_value: float | None = None
    delivery_location: str | None = None
    specs: dict | None = None
    output_format: str = "html"


# ===== ONYX: Tier Waterfall Schemas =====


class RateResult(BaseModel):
    """Intermediate result from a single tier's lookup function.
    Used internally by tier services before conversion to TierResult."""

    source_name: str
    price: float | None = None
    price_range_low: float | None = None
    price_range_high: float | None = None
    currency: str = "INR"
    evidence_url: str | None = None
    rationale: str
    is_demo_data: bool = False
    raw_data: dict | None = None  # source-specific metadata

    def as_tier(self, tier_num: int, label: str) -> "TierResult":
        """Convert to a TierResult for the given tier."""
        return TierResult(
            tier=tier_num,
            tier_label=label,
            source_name=self.source_name,
            price=self.price,
            price_range_low=self.price_range_low,
            price_range_high=self.price_range_high,
            currency=self.currency,
            confidence="HIGH" if self.price else "LOW",
            reliability="MEDIUM",
            evidence_url=self.evidence_url,
            rationale=self.rationale,
            is_demo_data=self.is_demo_data,
        )


class TierResult(BaseModel):
    """Result from a single tier in the waterfall."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tier": 0,
                    "tier_label": "Notified Rate",
                    "source_name": "Notified Rate (DGS&D)",
                    "price": 235.0,
                    "price_range_low": None,
                    "price_range_high": None,
                    "currency": "INR",
                    "confidence": "HIGH",
                    "reliability": "HIGH",
                    "evidence_url": None,
                    "evidence_reference": "DGS&D/RC-2026/STN-001",
                    "rationale": "DGS&D/Ministry notified rate for 'A4 Paper 75gsm'. Contract: DGS&D/RC-2026/STN-001. Match score: 92%.",
                    "is_demo_data": True,
                }
            ]
        }
    )

    tier: int  # 0–4
    tier_label: str
    source_name: str
    price: float | None = None
    price_range_low: float | None = None
    price_range_high: float | None = None
    currency: str = "INR"
    confidence: str  # HIGH / MEDIUM / LOW (extraction completeness)
    reliability: str  # HIGH / MEDIUM / LOW (price reliability — outlier/cross-check)
    evidence_url: str | None = None
    evidence_reference: str | None = None  # human-readable evidence ref (contract/PO/estimate) when no URL
    rationale: str  # why this tier was used / what was found
    is_demo_data: bool = False


class BenchmarkQuery(BaseModel):
    """Main entry point query for the tier waterfall benchmark."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "product_name": "A4 Paper 75gsm",
                    "query_type": "make_model",
                    "query_mode": "product",
                    "category": "Stationery",
                    "quantity": 10,
                    "department": "Ministry of Defence",
                    "service_type": None,
                    "service_duration": None,
                    "service_scope": None,
                    "service_location": None,
                    "specs": {"brand": None, "model_number": None},
                },
                {
                    "product_name": "Annual Maintenance Contract - Desktop Computer",
                    "query_mode": "service",
                    "service_type": "AMC",
                    "service_duration": "12 months",
                    "service_location": "New Delhi",
                    "quantity": 1,
                },
            ]
        }
    )

    product_name: str = Field(..., min_length=2, max_length=500)
    query_type: Literal["make_model", "specifications"] = "make_model"
    query_mode: Literal["product", "service"] = "product"
    category: str | None = Field(None, max_length=100)
    quantity: int = Field(1, ge=1, le=10000)
    estimated_value: float | None = Field(
        None,
        ge=0,
        description=(
            "Estimated purchase value in INR. Enables the GFR 2017 "
            "procurement-threshold compliance check (Rule 161/162/163)."
        ),
    )
    delivery_location: str | None = Field(
        None,
        max_length=200,
        description=(
            "Delivery city / region. Triggers the demo-simulated freight and "
            "landed-cost estimate."
        ),
    )
    department: str | None = Field(None, max_length=200)
    # Service-specific fields
    service_type: str | None = Field(None, max_length=100)
    service_duration: str | None = Field(None, max_length=100)
    service_scope: str | None = Field(None, max_length=2000)
    service_location: str | None = Field(None, max_length=200)
    specs: dict | None = None


class FreightEstimate(BaseModel):
    """Demo-simulated freight / landed-cost estimate for the delivery location."""

    delivery_location: str
    region_label: str
    freight_pct: float
    freight_amount: float
    quantity: int
    goods_value: float
    landed_total: float
    is_demo_simulated: bool
    note: str


class BaseProductInfo(BaseModel):
    """Canonical base-product identity matched against prior purchase records."""

    canonical_name: str
    canonical_key: str
    match_score: float | None = None
    prior_records: int = 0
    prior_median_price: float | None = None
    prior_min: float | None = None
    prior_max: float | None = None
    prior_departments: list[str] = []


class ProcurementThreshold(BaseModel):
    """GFR procurement-threshold compliance verdict for the estimated value."""

    value: float
    mode: str  # direct_purchase | limited_tender | competitive_bidding
    mode_label: str
    rule: str  # e.g. "GFR 2017 Rule 161"
    min_quotes_required: int
    quotes_obtained: int
    compliant: bool
    evidence_required: str
    non_compliance: str | None = None


class BenchmarkResponse(BaseModel):
    """Full benchmark result with tier waterfall trace."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "search_id": "a1b2c3d4-e5f6-4a5b-9c8d-1e2f3a4b5c6d",
                    "query": "A4 Paper 75gsm",
                    "query_mode": "product",
                    "status": "completed",
                    "resolved_tier": 0,
                    "tier_label": "Notified Rate",
                    "primary_result": {
                        "tier": 0,
                        "tier_label": "Notified Rate",
                        "source_name": "Notified Rate (DGS&D)",
                        "price": 235.0,
                        "currency": "INR",
                        "confidence": "HIGH",
                        "reliability": "HIGH",
                        "evidence_url": None,
                        "evidence_reference": "DGS&D/RC-2026/STN-001",
                        "rationale": "DGS&D notified rate for 'A4 Paper 75gsm'.",
                        "is_demo_data": True,
                    },
                    "all_results": [],
                    "tier_trace": {
                        "tier_0": "Found: Notified Rate (DGS&D)",
                        "tier_1": "Skipped: resolved at earlier tier",
                    },
                    "statistics": {"min": 235.0, "max": 235.0, "avg": 235.0, "median": 235.0, "count": 1},
                    "sources_checked": 1,
                    "results_found": 1,
                    "any_demo_data": True,
                }
            ]
        }
    )

    search_id: str
    query: str
    query_mode: str
    status: str
    resolved_tier: int
    tier_label: str
    primary_result: TierResult
    all_results: list[TierResult] = []
    tier_trace: dict = {}  # {"tier_0": "skipped: no rate contract", ...}
    statistics: dict = {}  # min, max, avg, median
    sources_checked: int = 0
    results_found: int = 0
    any_demo_data: bool = False  # True if any result (primary or evidence) is demo data
    procurement_threshold: ProcurementThreshold | None = None
    specs: dict | None = None  # golden parameters the benchmark was configured against
    base_product: BaseProductInfo | None = None
    freight: FreightEstimate | None = None  # demo-simulated landed-cost estimate


class DepartmentUploadRequest(BaseModel):
    """Request metadata for department purchase history upload."""

    department: str = Field(..., min_length=2, max_length=200)


class DepartmentLPPRecord(BaseModel):
    """Single record from a department purchase history upload."""

    item_description: str
    unit_price: float
    quantity_purchased: int
    purchase_date: str  # ISO date string
    vendor_name: str | None = None
    specs: dict | None = None
    source_document: str | None = None


class NonStandardEstimateResponse(BaseModel):
    """Response from the Tier 4 non-standard item estimator."""

    method_used: str
    estimated_price: float | None = None
    price_range_low: float | None = None
    price_range_high: float | None = None
    comparable_items: list[dict] = []
    confidence_rationale: str
    spec_match_score: float | None = None
