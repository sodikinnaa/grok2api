"""UI pages router."""

from fastapi import APIRouter

from app.api.pages.admin import router as admin_router
from app.api.pages.function import router as function_router

router = APIRouter()

router.include_router(function_router)
router.include_router(admin_router)

__all__ = ["router"]
