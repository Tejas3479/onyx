from .admin import router as admin_router
from .benchmark import router as benchmark_router
from .crawl import router as crawl_router
from .fetch import router as fetch_router
from .health import router as health_router

# Onyx routers — uncomment as each feature is built:
# from .auth_routes import router as auth_router
# from .department_lpp import router as department_lpp_router
# from .reports import router as reports_router

__all__ = [
    "admin_router",
    "benchmark_router",
    "crawl_router",
    "fetch_router",
    "health_router",
]
