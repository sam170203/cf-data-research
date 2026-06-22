from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.research import router as research_router
from app.api.routes.research_ext import router as research_ext_router
from app.api.routes.stats import router as stats_router
from app.api.routes.users import router as users_router

router = APIRouter()

router.include_router(stats_router)
router.include_router(users_router)
router.include_router(jobs_router)
router.include_router(metrics_router)
router.include_router(dashboard_router)
router.include_router(research_router)
router.include_router(research_ext_router)
