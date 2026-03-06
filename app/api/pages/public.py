from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.core.auth import is_public_enabled

router = APIRouter()
STATIC_DIR = Path(__file__).resolve().parents[3] / "_public" / "static"


def _public_page_response(relative_path: str) -> FileResponse:
    file_path = STATIC_DIR / relative_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(file_path)


@router.get("/", include_in_schema=False)
async def root():
    if is_public_enabled():
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/admin/login")


@router.get("/login", include_in_schema=False)
async def public_login():
    if not is_public_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return _public_page_response("public/pages/login.html")


@router.get("/imagine", include_in_schema=False)
async def public_imagine():
    if not is_public_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return _public_page_response("public/pages/imagine.html")


@router.get("/voice", include_in_schema=False)
async def public_voice():
    if not is_public_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return _public_page_response("public/pages/voice.html")


@router.get("/video", include_in_schema=False)
async def public_video():
    if not is_public_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return _public_page_response("public/pages/video.html")


@router.get("/chat", include_in_schema=False)
async def public_chat():
    if not is_public_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return _public_page_response("public/pages/chat.html")
