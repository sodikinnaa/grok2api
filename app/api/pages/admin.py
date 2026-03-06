from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/admin", include_in_schema=False)
async def admin_root():
    return RedirectResponse(url="/admin/login")


@router.get("/admin/login", include_in_schema=False)
async def admin_login():
    return RedirectResponse(url="/static/admin/pages/login.html")


@router.get("/admin/config", include_in_schema=False)
async def admin_config():
    return RedirectResponse(url="/static/admin/pages/config.html")


@router.get("/admin/cache", include_in_schema=False)
async def admin_cache():
    return RedirectResponse(url="/static/admin/pages/cache.html")


@router.get("/admin/token", include_in_schema=False)
async def admin_token():
    return RedirectResponse(url="/static/admin/pages/token.html")
