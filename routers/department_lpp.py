"""Onyx Department LPP API — upload and search department purchase history."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from routers.auth_routes import require_current_user
from services.base_product import count_base_products
from services.department_lpp import (
    list_department_records,
    parse_upload,
    save_records,
)

logger = logging.getLogger("onyx.department_lpp_router")

router = APIRouter(prefix="/api/v1/department-lpp", tags=["department-lpp"])

# Max upload size: 10MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def upload_purchase_history(
    file: UploadFile = File(...),
    department: str | None = Form(...),
    user=Depends(require_current_user),
):
    """
    Upload a CSV or Excel file of department purchase history.

    Required columns: item_description, unit_price, quantity, purchase_date
    Optional columns: vendor_name, source_document, specs (any extra columns
    become specs automatically)

    Column names are flexible — common aliases like 'price', 'item', 'qty',
    'date', 'vendor' are automatically mapped.

    Row-level isolation: non-admin officers can only ingest for their own
    department.
    """
    # Non-admins can only upload for their own department.
    if user is not None and getattr(user, "role", "user") != "admin":
        if user.department and (department or "").strip() != user.department:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Cannot upload for '{(department or '').strip()}' — you are "
                    f"scoped to '{user.department}'."
                ),
            )
        if not user.department:
            department = None

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Use: {', '.join(allowed_extensions)}",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Parse the upload
    result = await parse_upload(
        file_content=content,
        filename=file.filename,
        department=department.strip() if department else None,
        uploaded_by=(user.email if user else None),
    )

    if result["errors"] and not result["records"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "No valid records found",
                "errors": result["errors"][:20],  # Cap error list
            },
        )

    # Save valid records to database
    saved_count = await save_records(result["records"])

    logger.info(
        "Uploaded %d records for department '%s' from '%s'",
        saved_count,
        department,
        file.filename,
    )

    return {
        "status": "success",
        "message": f"Uploaded {saved_count} purchase records for {department or 'your department'}",
        "saved_count": saved_count,
        "total_rows": result["total_rows"],
        "errors": result["errors"][:20] if result["errors"] else [],
        "preview": result["preview"],
        "compliance_warnings": result.get("compliance_warnings", []),
    }


@router.get("")
async def get_department_records(
    department: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user=Depends(require_current_user),
):
    """
    List department purchase records with optional filtering.

    Row-level isolation: non-admin officers only ever see their own
    department's records; admins may pass an explicit department filter.

    Query params:
      - department: filter by department name (admin only)
      - search: fuzzy search by item description
      - limit: max records to return (default 50)
      - offset: pagination offset
    """
    limit = min(limit, 200)

    if user is not None and getattr(user, "role", "user") != "admin":
        # Hard-scope non-admins to their own department.
        if user.department:
            department = user.department
        else:
            # No department on the profile — only their own uploads qualify.
            department = None

    result = await list_department_records(
        department=department,
        search_term=search,
        limit=limit,
        offset=offset,
    )

    if (
        user is not None
        and getattr(user, "role", "user") != "admin"
        and not user.department
    ):
        result["records"] = [
            r for r in result["records"] if r.get("department") is None
        ]
        result["total"] = len(result["records"])

    result["base_products"] = count_base_products(result["records"])

    return result
