import os
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import JSON, Column, Field, SQLModel, String

# Retrieve DATABASE_URL from env, default to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/onyx.db")

# PostgreSQL gets production-grade connection pool settings;
# SQLite uses StaticPool internally and does not support these options.
_engine_kwargs: dict[str, Any] = {"echo": False}
if "sqlite" not in DATABASE_URL:
    _engine_kwargs.update(
        {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    )

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.split(":///")[-1]
        if ("/" in db_path or "\\" in db_path) and not db_path.startswith(":memory:"):
            dir_name = os.path.dirname(db_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Lightweight additive migrations for pre-existing SQLite databases
    # (create_all only adds tables, never new columns on existing ones).
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.split(":///")[-1]
        if db_path and not db_path.startswith(":memory:"):
            await _sqlite_ensure_column(
                "pricesearch", "any_demo_data", "BOOLEAN NOT NULL DEFAULT 0"
            )
            for col, ddl in (
                ("estimated_value", "REAL"),
                ("delivery_location", "VARCHAR(200)"),
                ("specs", "TEXT"),
                ("statistics", "TEXT"),
                ("procurement_threshold", "TEXT"),
                ("base_product", "TEXT"),
                ("freight", "TEXT"),
            ):
                await _sqlite_ensure_column("pricesearch", col, ddl)
            await _sqlite_ensure_column(
                "departmentpurchaserecord",
                "is_demo_data",
                "BOOLEAN NOT NULL DEFAULT 0",
            )


async def _sqlite_ensure_column(table: str, column: str, ddl: str) -> None:
    """Add a column to an existing SQLite table if it is missing."""
    import aiosqlite

    try:
        async with aiosqlite.connect(
            DATABASE_URL.split(":///")[-1]
        ) as conn:
            cursor = await conn.execute(f"PRAGMA table_info({table})")
            rows = await cursor.fetchall()
            if column not in {r[1] for r in rows}:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
                await conn.commit()
    except Exception as e:  # pragma: no cover - defensive
        import logging

        logging.getLogger("onyx.database").warning(
            "Could not ensure column %s.%s: %s", table, column, e
        )


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


class ApiKey(SQLModel, table=True):  # type: ignore[call-arg]
    key: str = Field(primary_key=True)
    name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Proxy(SQLModel, table=True):  # type: ignore[call-arg]
    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(sa_column=Column("url", String, unique=True))
    is_active: bool = Field(default=True)
    fail_count: int = Field(default=0)
    last_used_at: datetime | None = None


# ===== ONYX: Tier Waterfall Tables =====


class NotifiedRate(SQLModel, table=True):  # type: ignore[call-arg]
    """Tier 0 — DGS&D rate contracts / ministry-notified fixed rates."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    item_category: str  # "Stationery", "IT Equipment", "AMC Services"
    item_description: str  # "A4 Paper 75gsm", "Desktop Computer i5"
    rate: float
    unit: str  # "per ream", "per unit", "per month"
    currency: str = Field(default="INR")
    authority: str  # "DGS&D", "Ministry of Finance"
    contract_number: str | None = None
    valid_from: date
    valid_until: date | None = None
    is_active: bool = Field(default=True)
    is_demo_data: bool = Field(
        default=True
    )  # seeded rates are demo until verified real
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GemLPPCache(SQLModel, table=True):  # type: ignore[call-arg]
    """Tier 1 — Cached GeM catalog prices or BA reference prices."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    query_matched: str  # the search query this was found for
    product_name: str
    gem_product_id: str | None = None
    catalog_price: float | None = None
    lpp_price: float | None = None  # Last Purchase Price if available
    source_label: str  # "GeM Catalog Price" or "GeM LPP (demo)"
    source_url: str | None = None
    seller_name: str | None = None
    specifications: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_demo_data: bool = Field(default=True)  # explicit flag for seeded data


class DepartmentPurchaseRecord(SQLModel, table=True):  # type: ignore[call-arg]
    """Tier 2 — Department's own purchase history, uploaded via CSV."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    department: str
    item_description: str
    normalized_item_key: str  # lowercased, stopwords removed, for matching
    specs: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    unit_price: float
    quantity_purchased: int
    purchase_date: date
    vendor_name: str | None = None
    source_document: str | None = None  # filename of uploaded PO/invoice
    uploaded_by: str | None = None  # user_id
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_demo_data: bool = Field(default=False)  # True for pre-seeded sample records


class NonStandardEstimate(SQLModel, table=True):  # type: ignore[call-arg]
    """Tier 4 — Spec-similarity / should-cost model outputs."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    search_id: str  # FK to PriceSearch
    method_used: str  # "spec_similarity", "price_per_spec_unit", "insufficient_data"
    comparable_items: list[dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    estimated_price: float | None = None
    price_range_low: float | None = None
    price_range_high: float | None = None
    confidence_rationale: str  # human-readable explanation
    spec_match_score: float | None = None  # 0.0–1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelegationRecord(SQLModel, table=True):  # type: ignore[call-arg]
    """Cross-officer delegation of a benchmark for review/approval (Q15)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    search_id: str  # FK to PriceSearch
    delegated_by_name: str | None = None
    delegated_by_email: str | None = None
    delegate_to_name: str
    delegate_to_email: str | None = None
    note: str | None = None
    status: str = "open"  # open | completed
    decision: str | None = None  # approved | rejected
    decision_note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class BenchmarkAuditLog(SQLModel, table=True):  # type: ignore[call-arg]
    """Append-only action trail per benchmark run."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    search_id: str  # FK to PriceSearch
    action: str
    actor_name: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ===== ONYX: Price Benchmarking Tables =====


class User(SQLModel, table=True):  # type: ignore[call-arg]
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    email: str = Field(sa_column=Column("email", String, unique=True))
    hashed_password: str
    department: str | None = None
    organization: str | None = None
    role: str = Field(default="user")  # "admin" or "user"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PriceSearch(SQLModel, table=True):  # type: ignore[call-arg]
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str  # FK to User
    query: str  # "Cisco Catalyst 9300"
    query_type: str = "make_model"  # "make_model" or "specifications"
    category: str | None = None  # "Networking", "Computing", etc.
    quantity: int = Field(default=1)
    status: str = Field(default="pending")  # pending, searching, completed, failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    sources_checked: int = Field(default=0)
    results_found: int = Field(default=0)

    # Tier waterfall tracking
    resolved_tier: int | None = None  # 0–4, which tier produced the result
    tier_label: str | None = None  # "Notified Rate" / "GeM BA" / etc.
    tier_skip_reasons: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    query_mode: str = Field(default="product")  # "product" or "service"
    service_type: str | None = None  # AMC, manpower, consulting (if service mode)
    service_duration: str | None = None
    service_scope: str | None = None
    service_location: str | None = None  # location for service queries

    # True when the resolved benchmark used any demo/seeded source data.
    any_demo_data: bool = Field(default=False)

    # Compliance snapshot persisted at run time (Round-5+). Stored as JSON so
    # past runs keep their full reasonability story in reports + dashboard.
    estimated_value: float | None = None  # GFR threshold input (₹)
    delivery_location: str | None = None  # freight/landed-cost input
    specs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    statistics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    procurement_threshold: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    base_product: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    freight: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class PriceResult(SQLModel, table=True):  # type: ignore[call-arg]
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    search_id: str  # FK to PriceSearch
    source_name: str  # "Amazon India", "GeM Portal", etc.
    source_url: str
    product_name: str | None = None
    brand: str | None = None
    model_number: str | None = None
    price: float | None = None
    currency: str = Field(default="INR")
    price_includes_gst: bool | None = None
    vendor_name: str | None = None
    availability: str | None = None  # "In Stock", "Out of Stock", "Contact for Price"
    specifications: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    confidence: str = Field(default="LOW")  # HIGH, MEDIUM, LOW
    screenshot_path: str | None = None
    raw_content: str | None = None  # Stored markdown for reference
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PriceHistory(SQLModel, table=True):  # type: ignore[call-arg]
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    product_query: str
    source_name: str
    source_url: str
    price: float
    currency: str = Field(default="INR")
    vendor_name: str | None = None
    confidence: str = Field(default="LOW")
    screenshot_path: str | None = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PriceAlert(SQLModel, table=True):  # type: ignore[call-arg]
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str  # FK to User
    product_query: str
    target_price: float
    condition: str = "below"  # "below" or "above"
    is_active: bool = Field(default=True)
    last_triggered: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Report(SQLModel, table=True):  # type: ignore[call-arg]
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str  # FK to User
    search_id: str  # FK to PriceSearch
    title: str
    file_path: str | None = None  # Path to generated PDF
    department_name: str | None = None
    signatory_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProxyManager:
    @staticmethod
    async def get_proxy() -> str | None:
        async with async_session_maker() as session:
            # Get the least recently used, active proxy
            result = await session.execute(
                select(Proxy)
                .where(Proxy.is_active == True)
                .order_by(Proxy.last_used_at.asc().nullsfirst())  # type: ignore[union-attr]
                .limit(1)
            )
            proxy = result.scalars().first()
            if not proxy:
                return None

            # Update last used
            proxy.last_used_at = datetime.now(timezone.utc)
            session.add(proxy)
            await session.commit()

            return proxy.url

    @staticmethod
    async def report_failure(url: str):
        async with async_session_maker() as session:
            result = await session.execute(select(Proxy).where(Proxy.url == url))
            proxy = result.scalars().first()
            if proxy:
                proxy.fail_count += 1
                if proxy.fail_count >= 3:
                    proxy.is_active = False
                session.add(proxy)
                await session.commit()

    @staticmethod
    async def report_success(url: str):
        async with async_session_maker() as session:
            result = await session.execute(select(Proxy).where(Proxy.url == url))
            proxy = result.scalars().first()
            if proxy and proxy.fail_count > 0:
                proxy.fail_count = 0
                session.add(proxy)
                await session.commit()
