from .admin import router as admin_router
from .auth_routes import router as auth_router
from .benchmark import router as benchmark_router
from .delegation import router as delegation_router
from .department_lpp import router as department_lpp_router
from .fetch import router as fetch_router
from .health import router as health_router
from .price_history import router as price_history_router
from .reports import router as reports_router
from .search import router as search_router

__all__ = [
    "admin_router",
    "auth_router",
    "benchmark_router",
    "delegation_router",
    "department_lpp_router",
    "fetch_router",
    "health_router",
    "price_history_router",
    "reports_router",
    "search_router",
]
