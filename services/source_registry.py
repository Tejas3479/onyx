# Source configuration for price scraping

SOURCES = [
    {
        "name": "GeM Portal",
        "url_template": "https://mkp.gem.gov.in/search?q={query}",
        "render_js": True,
        "requires_stealth": False,
        "enabled": True,
    },
    {
        "name": "Amazon India",
        "url_template": "https://www.amazon.in/s?k={query}",
        "render_js": True,
        "requires_stealth": True,
        "enabled": True,
    },
    {
        "name": "IndiaMART",
        "url_template": "https://dir.indiamart.com/search.mp?ss={query}",
        "render_js": False,
        "requires_stealth": False,
        "enabled": True,
    },
    {
        "name": "Flipkart",
        "url_template": "https://www.flipkart.com/search?q={query}",
        "render_js": True,
        "requires_stealth": True,
        "enabled": True,
    },
    {
        "name": "Google Shopping",
        "url_template": "https://www.google.com/search?tbm=shop&q={query}",
        "render_js": True,
        "requires_stealth": True,
        "enabled": True,
    },
]
