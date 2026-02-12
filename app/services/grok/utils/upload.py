"""
Upload service.
"""

import base64
import re
from typing import Optional, Tuple
from urllib.parse import urlparse

from curl_cffi.requests import AsyncSession

from app.core.exceptions import AppException, UpstreamException, ValidationException
from app.core.logger import logger
from app.services.reverse import AssetsUploadReverse
from app.services.grok.utils.locks import _get_assets_semaphore


class UploadService:
    """Assets upload service."""

    def __init__(self):
        self._session: Optional[AsyncSession] = None

    async def create(self) -> AsyncSession:
        """Create or reuse a session."""
        if self._session is None:
            self._session = AsyncSession()
        return self._session

    async def close(self):
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None

    @staticmethod
    def _is_url(value: str) -> bool:
        """Check if the value is a URL."""
        try:
            parsed = urlparse(value)
            return bool(parsed.scheme and parsed.netloc and parsed.scheme in ["http", "https"])
        except Exception:
            return False

    @staticmethod
    async def parse_b64(url: str) -> Tuple[str, str, str]:
        """Fetch URL content and return (filename, base64, mime)."""
        try:
            async with AsyncSession() as session:
                response = await session.get(url, timeout=10)
                if response.status_code >= 400:
                    raise UpstreamException(
                        message=f"Failed to fetch: {response.status_code}",
                        details={"url": url, "status": response.status_code},
                    )

                filename = url.split("/")[-1].split("?")[0] or "download"
                content_type = response.headers.get(
                    "content-type", "application/octet-stream"
                ).split(";")[0]
                b64 = base64.b64encode(response.content).decode()

                logger.debug(f"Fetched: {url}")
                return filename, b64, content_type
        except Exception as e:
            if isinstance(e, AppException):
                raise
            logger.error(f"Fetch failed: {url} - {e}")
            raise UpstreamException(f"Fetch failed: {str(e)}", details={"url": url})

    @staticmethod
    def format_b64(data_uri: str) -> Tuple[str, str, str]:
        """Format data URI to (filename, base64, mime)."""
        if not data_uri.startswith("data:"):
            return "file.bin", data_uri, "application/octet-stream"

        try:
            header, b64 = data_uri.split(",", 1)
        except ValueError:
            return "file.bin", data_uri, "application/octet-stream"

        if ";base64" not in header:
            return "file.bin", data_uri, "application/octet-stream"

        mime = header[5:].split(";", 1)[0] or "application/octet-stream"
        b64 = re.sub(r"\s+", "", b64)
        ext = mime.split("/")[-1] if "/" in mime else "bin"
        return f"file.{ext}", b64, mime

    async def check_format(self, file_input: str) -> Tuple[str, str, str]:
        """Check file input format and return (filename, base64, mime)."""
        if not isinstance(file_input, str) or not file_input.strip():
            raise ValidationException("Invalid file input: empty content")

        if self._is_url(file_input):
            return await self.parse_b64(file_input)

        return self.format_b64(file_input)

    async def upload_file(self, file_input: str, token: str) -> Tuple[str, str]:
        """
        Upload file to Grok.

        Args:
            file_input: str, the file input.
            token: str, the SSO token.

        Returns:
            Tuple[str, str]: The file ID and URI.
        """
        async with _get_assets_semaphore():
            filename, b64, mime = await self.check_format(file_input)

            logger.debug(
                f"Upload prepare: filename={filename}, type={mime}, size={len(b64)}"
            )

            if not b64:
                raise ValidationException("Invalid file input: empty content")

            session = await self.create()
            response = await AssetsUploadReverse.request(
                session,
                token,
                filename,
                mime,
                b64,
            )

            result = response.json()
            file_id = result.get("fileMetadataId", "")
            file_uri = result.get("fileUri", "")
            logger.info(f"Upload success: {filename} -> {file_id}")
            return file_id, file_uri


__all__ = ["UploadService"]
