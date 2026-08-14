"""
Tier 2 — Department's Own Last Purchase Price.

Handles CSV/Excel upload of department purchase history and fuzzy matching
of new queries against uploaded records. This implements GFR Rule 149(vii)'s
second priority: checking the department's own purchase records before
falling back to market survey.
"""

import io
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from rapidfuzz import fuzz
from sqlalchemy import select

from database import DepartmentPurchaseRecord, async_session_maker

logger = logging.getLogger("onyx.department_lpp")

# Minimum fuzzy match score (0-100) to consider a record a match
MATCH_THRESHOLD = 70

# Stopwords to remove when normalizing item keys for matching
STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "for", "with", "in", "to",
    "no", "nos", "set", "type", "model", "make", "brand", "item",
    "unit", "units", "pcs", "pc", "ea", "each", "per", "qty",
})

# Required columns in uploaded CSV/Excel files
REQUIRED_COLUMNS = {"item_description", "unit_price", "quantity", "purchase_date"}

# Column aliases — maps common alternate names to our canonical names
COLUMN_ALIASES = {
    "item": "item_description",
    "description": "item_description",
    "product": "item_description",
    "product_name": "item_description",
    "item_name": "item_description",
    "price": "unit_price",
    "rate": "unit_price",
    "amount": "unit_price",
    "cost": "unit_price",
    "qty": "quantity",
    "quantity_purchased": "quantity",
    "date": "purchase_date",
    "po_date": "purchase_date",
    "order_date": "purchase_date",
    "vendor": "vendor_name",
    "supplier": "vendor_name",
    "seller": "vendor_name",
    "vendor_name": "vendor_name",
    "document": "source_document",
    "reference": "source_document",
    "po_number": "source_document",
    "source_document": "source_document",
}


def normalize_item_key(description: str) -> str:
    """
    Normalize an item description for fuzzy matching.

    Lowercases, removes stopwords, sorts remaining tokens for
    order-independent matching. E.g.:
      "Cisco Catalyst 9300 Switch 48-Port" -> "9300 48-port catalyst cisco switch"
    """
    tokens = description.lower().split()
    filtered = [t for t in tokens if t not in STOPWORDS]
    return " ".join(sorted(filtered))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map column names to canonical names using aliases."""
    rename_map = {}
    for col in df.columns:
        col_lower = col.strip().lower().replace(" ", "_")
        if col_lower in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[col_lower]
        elif col_lower in REQUIRED_COLUMNS or col_lower in {"vendor_name", "source_document", "specs"}:
            rename_map[col] = col_lower
    return df.rename(columns=rename_map)


async def parse_upload(
    file_content: bytes,
    filename: str,
    department: str,
    uploaded_by: str | None = None,
) -> dict[str, Any]:
    """
    Parse a CSV or Excel file of department purchase records.

    Returns:
        dict with keys:
          - records: list[DepartmentPurchaseRecord] ready for DB insert
          - errors: list[str] of validation errors
          - preview: list[dict] of first 10 parsed records for UI preview
          - total_rows: int
    """
    errors: list[str] = []

    # Read file into DataFrame
    try:
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_content), engine="openpyxl")
        elif filename.endswith(".csv"):
            # Try UTF-8 first, fall back to latin-1
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(file_content), encoding="latin-1")
        else:
            return {"records": [], "errors": ["Unsupported file format. Use CSV or Excel (.xlsx)."], "preview": [], "total_rows": 0}
    except Exception as e:
        return {"records": [], "errors": [f"Failed to read file: {e!s}"], "preview": [], "total_rows": 0}

    if df.empty:
        return {"records": [], "errors": ["File is empty."], "preview": [], "total_rows": 0}

    # Normalize column names
    df = _normalize_columns(df)

    # Check for required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return {
            "records": [],
            "errors": [(
                f"Missing required columns: {', '.join(sorted(missing))}. "
                f"Found columns: {', '.join(df.columns.tolist())}"
            )],
            "preview": [],
            "total_rows": len(df),
        }

    # Parse and validate rows
    records: list[DepartmentPurchaseRecord] = []
    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 for 1-indexed + header row

        # Validate item_description
        item_desc = str(row.get("item_description", "")).strip()
        if not item_desc or item_desc == "nan":
            errors.append(f"Row {row_num}: Missing item description")
            continue

        # Validate unit_price
        try:
            price = float(row["unit_price"])
            if price <= 0:
                errors.append(f"Row {row_num}: Price must be positive (got {price})")
                continue
        except (ValueError, TypeError):
            errors.append(f"Row {row_num}: Invalid price '{row['unit_price']}'")
            continue

        # Validate quantity
        try:
            qty = int(float(row["quantity"]))
            if qty <= 0:
                qty = 1
        except (ValueError, TypeError):
            qty = 1

        # Parse purchase_date
        try:
            pd_val = row["purchase_date"]
            if isinstance(pd_val, datetime):
                purchase_dt = pd_val.date()
            elif isinstance(pd_val, date):
                purchase_dt = pd_val
            else:
                # Try common date formats
                date_str = str(pd_val).strip()
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
                    try:
                        purchase_dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc).date()
                        break
                    except ValueError:
                        continue
                else:
                    errors.append(f"Row {row_num}: Cannot parse date '{pd_val}'")
                    continue
        except Exception:
            errors.append(f"Row {row_num}: Invalid date '{row['purchase_date']}'")
            continue

        # Optional fields
        vendor = str(row.get("vendor_name", "")).strip()
        vendor = vendor if vendor and vendor != "nan" else None
        source_doc = str(row.get("source_document", "")).strip()
        source_doc = source_doc if source_doc and source_doc != "nan" else None

        # Build specs dict from any extra columns
        specs: dict[str, Any] = {}
        extra_cols = set(df.columns) - REQUIRED_COLUMNS - {"vendor_name", "source_document"}
        for col in extra_cols:
            val = row.get(col)
            if val is not None and str(val).strip() != "nan":
                specs[col] = str(val).strip()

        record = DepartmentPurchaseRecord(
            id=str(uuid.uuid4()),
            department=department,
            item_description=item_desc,
            normalized_item_key=normalize_item_key(item_desc),
            specs=specs,
            unit_price=price,
            quantity_purchased=qty,
            purchase_date=purchase_dt,
            vendor_name=vendor,
            source_document=source_doc,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
        )
        records.append(record)

    # Build preview (first 10 records)
    preview = [
        {
            "item_description": r.item_description,
            "unit_price": r.unit_price,
            "quantity": r.quantity_purchased,
            "purchase_date": r.purchase_date.isoformat(),
            "vendor_name": r.vendor_name,
        }
        for r in records[:10]
    ]

    return {
        "records": records,
        "errors": errors,
        "preview": preview,
        "total_rows": len(df),
    }


async def save_records(records: list[DepartmentPurchaseRecord]) -> int:
    """Save parsed records to the database. Returns count of records saved."""
    if not records:
        return 0

    async with async_session_maker() as session:
        for record in records:
            session.add(record)
        await session.commit()

    logger.info("Saved %d department purchase records", len(records))
    return len(records)


async def check_department_lpp(
    query: str,
    specs: dict | None = None,
    department: str | None = None,
) -> dict[str, Any] | None:
    """
    Fuzzy-match a query against DepartmentPurchaseRecord entries.

    Uses rapidfuzz token_set_ratio for flexible matching regardless of
    word order. Returns the best match above MATCH_THRESHOLD, adjusted
    with a staleness note for older purchases.

    Returns None if no match found.
    """
    normalized_query = normalize_item_key(query)
    logger.debug("Checking department LPP: query='%s', normalized='%s', dept=%s",
                 query, normalized_query, department)

    async with async_session_maker() as session:
        # Build query
        stmt = select(DepartmentPurchaseRecord)
        if department:
            stmt = stmt.where(DepartmentPurchaseRecord.department == department)
        stmt = stmt.order_by(DepartmentPurchaseRecord.purchase_date.desc())  # type: ignore[union-attr]

        result = await session.execute(stmt)
        records = result.scalars().all()

    if not records:
        logger.debug("No department records found for dept=%s", department)
        return None

    # Score each record using fuzzy matching
    best_match: DepartmentPurchaseRecord | None = None
    best_score: float = 0.0

    for record in records:
        # Primary match: token_set_ratio on normalized keys
        score = fuzz.token_set_ratio(normalized_query, record.normalized_item_key)

        # Bonus for spec overlap if specs provided
        if specs and record.specs:
            spec_overlap = len(set(specs.keys()) & set(record.specs.keys()))
            if spec_overlap > 0:
                score = min(100, score + spec_overlap * 3)

        if score > best_score:
            best_score = score
            best_match = record

    if best_match is None or best_score < MATCH_THRESHOLD:
        logger.debug("No match above threshold (best score: %.1f)", best_score)
        return None

    # Calculate age of the purchase
    days_ago = (datetime.now(timezone.utc).date() - best_match.purchase_date).days
    months_ago = days_ago // 30

    # Build rationale with staleness note
    if months_ago <= 6:
        staleness = "recent"
        staleness_note = f"Purchased {months_ago} month(s) ago — price likely current."
    elif months_ago <= 12:
        staleness = "moderate"
        staleness_note = (
            f"Purchased {months_ago} month(s) ago — verify price is still current. "
            f"Consider ~5-7% annual inflation adjustment."
        )
    else:
        staleness = "old"
        staleness_note = (
            f"Purchased {months_ago} month(s) ago — price may be outdated. "
            f"Recommend verification. Approximate inflation-adjusted: "
            f"₹{best_match.unit_price * (1 + 0.06 * months_ago / 12):,.2f}"
        )

    return {
        "source_name": f"Department LPP ({best_match.department})",
        "price": best_match.unit_price,
        "currency": "INR",
        "evidence_url": None,
        "rationale": (
            f"Matched '{best_match.item_description}' (score: {best_score:.0f}%). "
            f"Vendor: {best_match.vendor_name or 'N/A'}. Qty: {best_match.quantity_purchased}. "
            f"{staleness_note}"
        ),
        "is_demo_data": False,
        "confidence": "HIGH" if best_score >= 85 else "MEDIUM",
        "reliability": "HIGH" if staleness == "recent" else ("MEDIUM" if staleness == "moderate" else "LOW"),
        "match_score": best_score,
        "purchase_date": best_match.purchase_date.isoformat(),
        "original_record": {
            "item_description": best_match.item_description,
            "unit_price": best_match.unit_price,
            "quantity": best_match.quantity_purchased,
            "vendor_name": best_match.vendor_name,
            "purchase_date": best_match.purchase_date.isoformat(),
        },
    }


async def list_department_records(
    department: str | None = None,
    search_term: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List department purchase records with optional filtering."""
    async with async_session_maker() as session:
        stmt = select(DepartmentPurchaseRecord)
        if department:
            stmt = stmt.where(DepartmentPurchaseRecord.department == department)
        stmt = stmt.order_by(DepartmentPurchaseRecord.purchase_date.desc())  # type: ignore[union-attr]
        stmt = stmt.offset(offset).limit(limit)

        result = await session.execute(stmt)
        records = result.scalars().all()

    # If search_term provided, filter in-memory with fuzzy matching
    if search_term and records:
        normalized_search = normalize_item_key(search_term)
        scored = [
            (r, fuzz.token_set_ratio(normalized_search, r.normalized_item_key))
            for r in records
        ]
        records = [r for r, score in scored if score >= 50]
        records.sort(key=lambda r: fuzz.token_set_ratio(
            normalized_search, r.normalized_item_key
        ), reverse=True)

    return {
        "records": [
            {
                "id": r.id,
                "department": r.department,
                "item_description": r.item_description,
                "unit_price": r.unit_price,
                "quantity": r.quantity_purchased,
                "purchase_date": r.purchase_date.isoformat(),
                "vendor_name": r.vendor_name,
                "source_document": r.source_document,
            }
            for r in records
        ],
        "total": len(records),
    }
