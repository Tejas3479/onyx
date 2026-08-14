"""Onyx Department LPP API — upload and search department purchase history."""

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

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
    department: str = Form(...),
):
    """
    Upload a CSV or Excel file of department purchase history.

    Required columns: item_description, unit_price, quantity, purchase_date
    Optional columns: vendor_name, source_document, specs (any extra columns
    become specs automatically)

    Column names are flexible — common aliases like 'price', 'item', 'qty',
    'date', 'vendor' are automatically mapped.
    """
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
            detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE // (1024*1024)}MB",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Parse the upload
    result = await parse_upload(
        file_content=content,
        filename=file.filename,
        department=department.strip(),
        uploaded_by=None,  # TODO: get from auth when login is implemented
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
        saved_count, department, file.filename,
    )

    return {
        "status": "success",
        "message": f"Uploaded {saved_count} purchase records for {department}",
        "saved_count": saved_count,
        "total_rows": result["total_rows"],
        "errors": result["errors"][:20] if result["errors"] else [],
        "preview": result["preview"],
    }


@router.get("")
async def get_department_records(
    department: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List department purchase records with optional filtering.

    Query params:
      - department: filter by department name
      - search: fuzzy search by item description
      - limit: max records to return (default 50)
      - offset: pagination offset
    """
    limit = min(limit, 200)

    result = await list_department_records(
        department=department,
        search_term=search,
        limit=limit,
        offset=offset,
    )

    return result
