
import pandas as pd
import pytest

from services.department_lpp import _normalize_columns, normalize_item_key, parse_upload


def test_normalize_item_key():
    assert normalize_item_key("Cisco Catalyst 9300 Switch 48-Port") == "48-port 9300 catalyst cisco switch"
    assert normalize_item_key("The item for Apple MacBook Pro 16-inch") == "16-inch apple macbook pro"

def test_normalize_columns():
    df = pd.DataFrame({
        "Product Name": ["Laptop"],
        "Rate": [1000],
        "Qty": [5],
        "Order Date": ["2023-01-01"]
    })
    
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
        uploaded_by="user1"
    )
    
    assert len(result["errors"]) == 0
    assert result["total_rows"] == 1
    assert len(result["records"]) == 1
    
    record = result["records"][0]
    assert record.item_description == "Laptop"
    assert record.unit_price == 1000.0
    assert record.quantity_purchased == 5.0
    assert record.department == "IT"
