# Onyx Python Client

Official Python client for the Onyx Web Scraping Engine.

## Installation

```bash
pip install onyx-client
```

## Usage

```python
from onyx_client import OnyxClient

client = OnyxClient(api_key="YOUR_API_KEY", base_url="http://localhost:8000")

# Simple fetch
response = client.fetch("https://example.com", render_js=True)
print(response["content"])
```
