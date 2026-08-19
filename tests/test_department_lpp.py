import pandas as pd
import pytest

from services.department_lpp import _normalize_columns, normalize_item_key, parse_upload


def test_normalize_item_key():
    assert (
        normalize_item_key("Cisco Catalyst 9300 Switch 48-Port")
        == "48-port 9300 catalyst cisco switch"
    )
    assert (
        normalize_item_key("The item for Apple MacBook Pro 16-inch")
        == "16-inch apple macbook pro"
    )


def test_normalize_columns():
    df = pd.DataFrame(
        {
            "Product Name": ["Laptop"],
            "Rate": [1000],
            "Qty": [5],
            "Order Date": ["2023-01-01"],
        }
    )

    normalized_df = _normalize_columns(df)

    assert "item_description" in normalized_df.columns
    assert "unit_price" in normalized_df.columns
    assert "quantity" in normalized_df.columns
    assert "purchase_date" in normalized_df.columns


@pytest.mark.asyncio
async def test_parse_upload_csv():
    csv_content = b"item,price,qty,date\nLaptop,1000,5,2023-01-01\n"

    result = await parse_upload(
        file_content=csv_content,
        filename="test.csv",
        department="IT",
        uploaded_by="user1",
    )

    assert len(result["errors"]) == 0
    assert result["total_rows"] == 1
    assert len(result["records"]) == 1

    record = result["records"][0]
    assert record.item_description == "Laptop"
    assert record.unit_price == 1000.0
    assert record.quantity_purchased == 5.0
    assert record.department == "IT"


def test_normalize_columns_nomenclature_alias():
    """DGS&D 'Nomenclature of Stores' columns must map to our canonical names."""
    df = pd.DataFrame(
        {
            "Nomenclature_of_Stores": ["Laptop"],
            "Rate": [1000],
            "Qty": [5],
            "PO Date": ["2023-01-01"],
        }
    )

    normalized_df = _normalize_columns(df)

    assert "item_description" in normalized_df.columns
    assert "unit_price" in normalized_df.columns
    assert "quantity" in normalized_df.columns
    assert "purchase_date" in normalized_df.columns


@pytest.mark.asyncio
async def test_parse_upload_compliance_flags_outlier():
    """Records outside the ±25% reasonableness band of their item cluster
    must surface a compliance warning (Rule 149(vii))."""
    csv_content = (
        b"item_description,unit_price,quantity,purchase_date,vendor_name\n"
        b"Desktop,50000,1,2023-01-01,Vendor A\n"
        b"Desktop,52000,1,2023-01-02,Vendor B\n"
        b"Desktop,54000,1,2023-01-03,Vendor C\n"
        b"Desktop,90000,1,2023-01-04,Vendor D\n"
    )

    result = await parse_upload(
        file_content=csv_content,
        filename="po.csv",
        department="IT",
        uploaded_by="user1",
    )

    assert len(result["records"]) == 4
    warnings = result["compliance_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["item_description"] == "Desktop"
    assert warnings[0]["direction"] == "above"
    assert warnings[0]["deviation_pct"] > 25
    assert warnings[0]["median"] == 53000.0


@pytest.mark.asyncio
async def test_parse_upload_compliance_no_warning_when_in_band():
    """A tight cluster within ±25% of median produces no warnings."""
    csv_content = (
        b"item_description,unit_price,quantity,purchase_date,vendor_name\n"
        b"Printer,40000,1,2023-01-01,Vendor A\n"
        b"Printer,42000,1,2023-01-02,Vendor B\n"
        b"Printer,43000,1,2023-01-03,Vendor C\n"
    )

    result = await parse_upload(
        file_content=csv_content,
        filename="po.csv",
        department="IT",
        uploaded_by="user1",
    )

    assert len(result["records"]) == 3
    assert result["compliance_warnings"] == []
