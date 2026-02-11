"""
Image response processors (HTTP + WebSocket).
"""

import asyncio
import base64
import random
import time
from pathlib import Path
from typing import AsyncGenerator, AsyncIterable, List, Dict, Optional

import orjson
from curl_cffi.requests.errors import RequestsError

from app.core.config import get_config
from app.core.logger import logger
from app.core.storage import DATA_DIR
from app.core.exceptions import UpstreamException
from .base import (
    BaseProcessor,
    StreamIdleTimeoutError,
    _with_idle_timeout,
    _normalize_stream_line,
    _collect_image_urls,
    _is_http2_stream_error,
)


class ImageStreamProcessor(BaseProcessor):
    """HTTP image stream processor."""

    def __init__(
        self, model: str, token: str = "", n: int = 1, response_format: str = "b64_json"
    ):
        super().__init__(model, token)
        self.partial_index = 0
        self.n = n
        self.target_index = random.randint(0, 1) if n == 1 else None
        self.response_format = response_format
        if response_format == "url":
            self.response_field = "url"
        elif response_format == "base64":
            self.response_field = "base64"
        else:
            self.response_field = "b64_json"

    def _sse(self, event: str, data: dict) -> str:
        """Build SSE response."""
        return f"event: {event}\ndata: {orjson.dumps(data).decode()}\n\n"

    async def process(
        self, response: AsyncIterable[bytes]
    ) -> AsyncGenerator[str, None]:
        """Process stream response."""
        final_images = []
        idle_timeout = get_config("timeout.stream_idle_timeout")

        try:
            async for line in _with_idle_timeout(response, idle_timeout, self.model):
                line = _normalize_stream_line(line)
                if not line:
                    continue
                try:
                    data = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                resp = data.get("result", {}).get("response", {})

                # Image generation progress
                if img := resp.get("streamingImageGenerationResponse"):
                    image_index = img.get("imageIndex", 0)
                    progress = img.get("progress", 0)

                    if self.n == 1 and image_index != self.target_index:
                        continue

                    out_index = 0 if self.n == 1 else image_index

                    yield self._sse(
                        "image_generation.partial_image",
                        {
                            "type": "image_generation.partial_image",
                            self.response_field: "",
                            "index": out_index,
                            "progress": progress,
                        },
                    )
                    continue

                # modelResponse
                if mr := resp.get("modelResponse"):
                    if urls := _collect_image_urls(mr):
                        for url in urls:
                            if self.response_format == "url":
                                processed = await self.process_url(url, "image")
                                if processed:
                                    final_images.append(processed)
                                continue
                            try:
                                dl_service = self._get_dl()
                                base64_data = await dl_service.to_base64(
                                    url, self.token, "image"
                                )
                                if base64_data:
                                    if "," in base64_data:
                                        b64 = base64_data.split(",", 1)[1]
                                    else:
                                        b64 = base64_data
                                    final_images.append(b64)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to convert image to base64, falling back to URL: {e}"
                                )
                                processed = await self.process_url(url, "image")
                                if processed:
                                    final_images.append(processed)
                    continue

            for index, b64 in enumerate(final_images):
                if self.n == 1:
                    if index != self.target_index:
                        continue
                    out_index = 0
                else:
                    out_index = index

                yield self._sse(
                    "image_generation.completed",
                    {
                        "type": "image_generation.completed",
                        self.response_field: b64,
                        "index": out_index,
                        "usage": {
                            "total_tokens": 0,
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "input_tokens_details": {
                                "text_tokens": 0,
                                "image_tokens": 0,
                            },
                        },
                    },
                )
        except asyncio.CancelledError:
            logger.debug("Image stream cancelled by client")
        except StreamIdleTimeoutError as e:
            raise UpstreamException(
                message=f"Image stream idle timeout after {e.idle_seconds}s",
                status_code=504,
                details={
                    "error": str(e),
                    "type": "stream_idle_timeout",
                    "idle_seconds": e.idle_seconds,
                },
            )
        except RequestsError as e:
            if _is_http2_stream_error(e):
                logger.warning(f"HTTP/2 stream error in image: {e}")
                raise UpstreamException(
                    message="Upstream connection closed unexpectedly",
                    status_code=502,
                    details={"error": str(e), "type": "http2_stream_error"},
                )
            logger.error(f"Image stream request error: {e}")
            raise UpstreamException(
                message=f"Upstream request failed: {e}",
                status_code=502,
                details={"error": str(e)},
            )
        except Exception as e:
            logger.error(
                f"Image stream processing error: {e}",
                extra={"error_type": type(e).__name__},
            )
            raise
        finally:
            await self.close()


class ImageCollectProcessor(BaseProcessor):
    """HTTP image non-stream processor."""

    def __init__(self, model: str, token: str = "", response_format: str = "b64_json"):
        super().__init__(model, token)
        self.response_format = response_format

    async def process(self, response: AsyncIterable[bytes]) -> List[str]:
        """Process and collect images."""
        images = []
        idle_timeout = get_config("timeout.stream_idle_timeout")

        try:
            async for line in _with_idle_timeout(response, idle_timeout, self.model):
                line = _normalize_stream_line(line)
                if not line:
                    continue
                try:
                    data = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                resp = data.get("result", {}).get("response", {})

                if mr := resp.get("modelResponse"):
                    if urls := _collect_image_urls(mr):
                        for url in urls:
                            if self.response_format == "url":
                                processed = await self.process_url(url, "image")
                                if processed:
                                    images.append(processed)
                                continue
                            try:
                                dl_service = self._get_dl()
                                base64_data = await dl_service.to_base64(
                                    url, self.token, "image"
                                )
                                if base64_data:
                                    if "," in base64_data:
                                        b64 = base64_data.split(",", 1)[1]
                                    else:
                                        b64 = base64_data
                                    images.append(b64)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to convert image to base64, falling back to URL: {e}"
                                )
                                processed = await self.process_url(url, "image")
                                if processed:
                                    images.append(processed)

        except asyncio.CancelledError:
            logger.debug("Image collect cancelled by client")
        except StreamIdleTimeoutError as e:
            logger.warning(f"Image collect idle timeout: {e}")
        except RequestsError as e:
            if _is_http2_stream_error(e):
                logger.warning(f"HTTP/2 stream error in image collect: {e}")
            else:
                logger.error(f"Image collect request error: {e}")
        except Exception as e:
            logger.error(
                f"Image collect processing error: {e}",
                extra={"error_type": type(e).__name__},
            )
        finally:
            await self.close()

        return images


class ImageWSBaseProcessor(BaseProcessor):
    """WebSocket image processor base."""

    def __init__(self, model: str, token: str = "", response_format: str = "b64_json"):
        super().__init__(model, token)
        self.response_format = response_format
        if response_format == "url":
            self.response_field = "url"
        elif response_format == "base64":
            self.response_field = "base64"
        else:
            self.response_field = "b64_json"
        self._image_dir: Optional[Path] = None

    def _ensure_image_dir(self) -> Path:
        if self._image_dir is None:
            base_dir = DATA_DIR / "tmp" / "image"
            base_dir.mkdir(parents=True, exist_ok=True)
            self._image_dir = base_dir
        return self._image_dir

    def _strip_base64(self, blob: str) -> str:
        if not blob:
            return ""
        if "," in blob and "base64" in blob.split(",", 1)[0]:
            return blob.split(",", 1)[1]
        return blob

    def _filename(self, image_id: str, is_final: bool) -> str:
        ext = "jpg" if is_final else "png"
        return f"{image_id}.{ext}"

    def _build_file_url(self, filename: str) -> str:
        app_url = get_config("app.app_url")
        if app_url:
            return f"{app_url.rstrip('/')}/v1/files/image/{filename}"
        return f"/v1/files/image/{filename}"

    def _save_blob(self, image_id: str, blob: str, is_final: bool) -> str:
        data = self._strip_base64(blob)
        if not data:
            return ""
        image_dir = self._ensure_image_dir()
        filename = self._filename(image_id, is_final)
        filepath = image_dir / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(data))
        return self._build_file_url(filename)

    def _pick_best(self, existing: Optional[Dict], incoming: Dict) -> Dict:
        if not existing:
            return incoming
        if incoming.get("is_final") and not existing.get("is_final"):
            return incoming
        if existing.get("is_final") and not incoming.get("is_final"):
            return existing
        if incoming.get("blob_size", 0) > existing.get("blob_size", 0):
            return incoming
        return existing

    def _to_output(self, image_id: str, item: Dict) -> str:
        try:
            if self.response_format == "url":
                return self._save_blob(
                    image_id, item.get("blob", ""), item.get("is_final", False)
                )
            return self._strip_base64(item.get("blob", ""))
        except Exception as e:
            logger.warning(f"Image output failed: {e}")
            return ""


class ImageWSStreamProcessor(ImageWSBaseProcessor):
    """WebSocket image stream processor."""

    def __init__(
        self,
        model: str,
        token: str = "",
        n: int = 1,
        response_format: str = "b64_json",
        size: str = "1024x1024",
    ):
        super().__init__(model, token, "b64_json")
        self.n = n
        self.size = size
        self._target_id: Optional[str] = None
        self._index_map: Dict[str, int] = {}
        self._partial_map: Dict[str, int] = {}

    def _assign_index(self, image_id: str) -> Optional[int]:
        if image_id in self._index_map:
            return self._index_map[image_id]
        if len(self._index_map) >= self.n:
            return None
        self._index_map[image_id] = len(self._index_map)
        return self._index_map[image_id]

    def _sse(self, event: str, data: dict) -> str:
        return f"event: {event}\ndata: {orjson.dumps(data).decode()}\n\n"

    async def process(self, response: AsyncIterable[dict]) -> AsyncGenerator[str, None]:
        images: Dict[str, Dict] = {}

        async for item in response:
            if item.get("type") == "error":
                message = item.get("error") or "Upstream error"
                code = item.get("error_code") or "upstream_error"
                yield self._sse(
                    "error",
                    {
                        "error": {
                            "message": message,
                            "type": "server_error",
                            "code": code,
                        }
                    },
                )
                return
            if item.get("type") != "image":
                continue

            image_id = item.get("image_id")
            if not image_id:
                continue

            if self.n == 1:
                if self._target_id is None:
                    self._target_id = image_id
                index = 0 if image_id == self._target_id else None
            else:
                index = self._assign_index(image_id)

            images[image_id] = self._pick_best(images.get(image_id), item)

            if index is None:
                continue

            if item.get("stage") != "final":
                partial_b64 = self._strip_base64(item.get("blob", ""))
                if not partial_b64:
                    continue
                partial_index = self._partial_map.get(image_id, 0)
                if item.get("stage") == "medium":
                    partial_index = max(partial_index, 1)
                self._partial_map[image_id] = partial_index
                yield self._sse(
                    "image_generation.partial_image",
                    {
                        "type": "image_generation.partial_image",
                        "b64_json": partial_b64,
                        "created_at": int(time.time()),
                        "size": self.size,
                        "index": index,
                        "partial_image_index": partial_index,
                    },
                )

        if self.n == 1:
            if self._target_id and self._target_id in images:
                selected = [(self._target_id, images[self._target_id])]
            else:
                selected = (
                    [
                        max(
                            images.items(),
                            key=lambda x: (
                                x[1].get("is_final", False),
                                x[1].get("blob_size", 0),
                            ),
                        )
                    ]
                    if images
                    else []
                )
        else:
            selected = [
                (image_id, images[image_id])
                for image_id in self._index_map
                if image_id in images
            ]

        for image_id, item in selected:
            output = self._strip_base64(item.get("blob", ""))
            if not output:
                continue

            if self.n == 1:
                index = 0
            else:
                index = self._index_map.get(image_id, 0)
            yield self._sse(
                "image_generation.completed",
                {
                    "type": "image_generation.completed",
                    "b64_json": output,
                    "created_at": int(time.time()),
                    "size": self.size,
                    "index": index,
                    "usage": {
                        "total_tokens": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "input_tokens_details": {"text_tokens": 0, "image_tokens": 0},
                    },
                },
            )


class ImageWSCollectProcessor(ImageWSBaseProcessor):
    """WebSocket image non-stream processor."""

    def __init__(
        self, model: str, token: str = "", n: int = 1, response_format: str = "b64_json"
    ):
        super().__init__(model, token, response_format)
        self.n = n

    async def process(self, response: AsyncIterable[dict]) -> List[str]:
        images: Dict[str, Dict] = {}

        async for item in response:
            if item.get("type") == "error":
                message = item.get("error") or "Upstream error"
                raise UpstreamException(message, details=item)
            if item.get("type") != "image":
                continue
            image_id = item.get("image_id")
            if not image_id:
                continue
            images[image_id] = self._pick_best(images.get(image_id), item)

        selected = sorted(
            images.values(),
            key=lambda x: (x.get("is_final", False), x.get("blob_size", 0)),
            reverse=True,
        )
        if self.n:
            selected = selected[: self.n]

        results: List[str] = []
        for item in selected:
            output = self._to_output(item.get("image_id", ""), item)
            if output:
                results.append(output)

        return results


__all__ = [
    "ImageStreamProcessor",
    "ImageCollectProcessor",
    "ImageWSStreamProcessor",
    "ImageWSCollectProcessor",
]
