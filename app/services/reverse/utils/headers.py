"""Shared header builders for reverse interfaces."""

import uuid
import orjson
from urllib.parse import urlparse
from typing import Dict, Optional

from app.core.config import get_config
from app.core.logger import logger
from app.services.reverse.utils.statsig import StatsigGenerator


def _build_sso_cookie(sso_token: str) -> str:
    """
    Build SSO Cookie string.
    """
    # Remove "sso=" prefix if present
    sso_token = sso_token[4:] if sso_token.startswith("sso=") else sso_token

    # SSO Cookie
    cookie = f"sso={sso_token}; sso-rw={sso_token}"

    # CF Clearance
    cf_clearance = get_config("security.cf_clearance")
    if cf_clearance:
        cookie += f";cf_clearance={cf_clearance}"

    return cookie


def build_headers(
    cookie_token: str,
    content_type: Optional[str] = None,
    origin: Optional[str] = None,
    referer: Optional[str] = None,
) -> Dict[str, str]:
    """
    Build headers for reverse interfaces.

    Args:
        cookie_token: The SSO token.
        content_type: Optional Content-Type value.
        origin: Optional Origin value. Defaults to "https://grok.com" if not provided.
        referer: Optional Referer value. Defaults to "https://grok.com/" if not provided.

    Returns:
        Dict[str, str]: The headers dictionary.
    """
    headers = {
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Baggage": "sentry-environment=production,sentry-release=d6add6fb0460641fd482d767a335ef72b9b6abb8,sentry-public_key=b311e0f2690c81f25e2c4cf6d4f7ce1c",
        "Origin": origin or "https://grok.com",
        "Priority": "u=1, i",
        "Referer": referer or "https://grok.com/",
        "Sec-Ch-Ua": '"Google Chrome";v="136", "Chromium";v="136", "Not(A:Brand";v="24"',
        "Sec-Ch-Ua-Arch": "arm",
        "Sec-Ch-Ua-Bitness": "64",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Model": "",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Mode": "cors",
        "User-Agent": get_config("security.user_agent"),
    }

    # Cookie
    headers["Cookie"] = _build_sso_cookie(cookie_token)

    # Content-Type and Accept/Sec-Fetch-Dest
    if content_type and content_type == "application/json":
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "*/*"
        headers["Sec-Fetch-Dest"] = "empty"
    elif content_type in ["image/jpeg", "image/png", "video/mp4", "video/webm"]:
        headers["Content-Type"] = content_type
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        headers["Sec-Fetch-Dest"] = "document"
    else:
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "*/*"
        headers["Sec-Fetch-Dest"] = "empty"

    # Sec-Fetch-Site
    origin_domain = urlparse(headers.get("Origin", "")).hostname
    referer_domain = urlparse(headers.get("Referer", "")).hostname
    if origin_domain and referer_domain and origin_domain == referer_domain:
        headers["Sec-Fetch-Site"] = "same-origin"
    else:
        headers["Sec-Fetch-Site"] = "same-site"

    # X-Statsig-ID and X-XAI-Request-ID
    headers["x-statsig-id"] = StatsigGenerator.gen_id()
    headers["x-xai-request-id"] = str(uuid.uuid4())

    # Print headers without Cookie
    safe_headers = dict(headers)
    if "Cookie" in safe_headers:
        safe_headers["Cookie"] = "<redacted>"
    logger.debug(f"Built headers: {orjson.dumps(safe_headers, indent=2)}")

    return headers


__all__ = ["build_headers"]
