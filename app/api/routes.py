from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.internal import router as internal_router
from app.api.ui import router as ui_router

router = APIRouter()
router.include_router(health_router)
router.include_router(ui_router)
router.include_router(internal_router)

