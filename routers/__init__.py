from .admin import router as admin_router
from .crawl import router as crawl_router
from .fetch import router as fetch_router
from .health import router as health_router

# Onyx routers (create empty placeholder files first)
# These will be uncommented as you build each feature:
# from .auth_routes import router as auth_router
# from .search import router as search_router
# from .reports import router as reports_router
# from .price_history import router as history_router

__all__ = [
    "admin_router",
    "crawl_router",
    "fetch_router",
    "health_router",
]
