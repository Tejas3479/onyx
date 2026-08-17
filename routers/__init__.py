from .admin import router as admin_router
from .auth_routes import router as auth_router
from .benchmark import router as benchmark_router
from .department_lpp import router as department_lpp_router
from .fetch import router as fetch_router
from .health import router as health_router
from .reports import router as reports_router

__all__ = [
    "admin_router",
    "auth_router",
    "benchmark_router",
    "department_lpp_router",
    "fetch_router",
    "health_router",
    "reports_router",
]
