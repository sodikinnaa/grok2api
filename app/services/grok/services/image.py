"""
Grok image services.
"""

import asyncio
import math
import random
from dataclasses import dataclass
from typing import Any, AsyncGenerator, List, Optional, Union

from app.core.config import get_config
from app.core.logger import logger
from app.services.grok.processors import (
    ImageStreamProcessor,
    ImageCollectProcessor,
    ImageWSStreamProcessor,
    ImageWSCollectProcessor,
)
from app.services.grok.services.chat import GrokChatService
from app.services.grok.utils.stream import wrap_stream_with_usage
from app.services.token import EffortType
from app.services.reverse.ws_imagine import ImagineWebSocketReverse


ImageService = ImagineWebSocketReverse
image_service = ImagineWebSocketReverse()


@dataclass
class ImageGenerationResult:
    stream: bool
    data: Union[AsyncGenerator[str, None], List[str]]
    usage_override: Optional[dict] = None


class ImageGenerationService:
    """Image generation orchestration service."""

    async def generate(
        self,
        *,
        token_mgr: Any,
        token: str,
        model_info: Any,
        prompt: str,
        n: int,
        response_format: str,
        size: str,
        aspect_ratio: str,
        stream: bool,
        use_ws: bool,
    ) -> ImageGenerationResult:
        if stream:
            if use_ws:
                return await self._stream_ws(
                    token_mgr=token_mgr,
                    token=token,
                    model_info=model_info,
                    prompt=prompt,
                    n=n,
                    response_format=response_format,
                    size=size,
                    aspect_ratio=aspect_ratio,
                )
            return await self._stream_http(
                token_mgr=token_mgr,
                token=token,
                model_info=model_info,
                prompt=prompt,
                n=n,
                response_format=response_format,
            )

        if use_ws:
            return await self._collect_ws(
                token_mgr=token_mgr,
                token=token,
                model_info=model_info,
                prompt=prompt,
                n=n,
                response_format=response_format,
                aspect_ratio=aspect_ratio,
            )

        return await self._collect_http(
            token_mgr=token_mgr,
            token=token,
            model_info=model_info,
            prompt=prompt,
            n=n,
            response_format=response_format,
        )

    async def _stream_ws(
        self,
        *,
        token_mgr: Any,
        token: str,
        model_info: Any,
        prompt: str,
        n: int,
        response_format: str,
        size: str,
        aspect_ratio: str,
    ) -> ImageGenerationResult:
        enable_nsfw = bool(get_config("image.image_ws_nsfw"))
        upstream = image_service.stream(
            token=token,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            n=n,
            enable_nsfw=enable_nsfw,
        )
        processor = ImageWSStreamProcessor(
            model_info.model_id,
            token,
            n=n,
            response_format=response_format,
            size=size,
        )
        stream = wrap_stream_with_usage(
            processor.process(upstream),
            token_mgr,
            token,
            model_info.model_id,
        )
        return ImageGenerationResult(stream=True, data=stream)

    async def _stream_http(
        self,
        *,
        token_mgr: Any,
        token: str,
        model_info: Any,
        prompt: str,
        n: int,
        response_format: str,
    ) -> ImageGenerationResult:
        response = await GrokChatService().chat(
            token=token,
            message=f"Image Generation: {prompt}",
            model=model_info.grok_model,
            mode=model_info.model_mode,
            stream=True,
        )
        processor = ImageStreamProcessor(
            model_info.model_id,
            token,
            n=n,
            response_format=response_format,
        )
        stream = wrap_stream_with_usage(
            processor.process(response),
            token_mgr,
            token,
            model_info.model_id,
        )
        return ImageGenerationResult(stream=True, data=stream)

    async def _collect_ws(
        self,
        *,
        token_mgr: Any,
        token: str,
        model_info: Any,
        prompt: str,
        n: int,
        response_format: str,
        aspect_ratio: str,
    ) -> ImageGenerationResult:
        enable_nsfw = bool(get_config("image.image_ws_nsfw"))
        all_images: List[str] = []
        seen = set()
        expected_per_call = 6
        calls_needed = max(1, int(math.ceil(n / expected_per_call)))
        calls_needed = min(calls_needed, n)

        async def _fetch_batch(call_target: int):
            upstream = image_service.stream(
                token=token,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                n=call_target,
                enable_nsfw=enable_nsfw,
            )
            processor = ImageWSCollectProcessor(
                model_info.model_id,
                token,
                n=call_target,
                response_format=response_format,
            )
            return await processor.process(upstream)

        tasks = []
        for i in range(calls_needed):
            remaining = n - (i * expected_per_call)
            call_target = min(expected_per_call, remaining)
            tasks.append(_fetch_batch(call_target))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for batch in results:
            if isinstance(batch, Exception):
                logger.warning(f"WS batch failed: {batch}")
                continue
            for img in batch:
                if img not in seen:
                    seen.add(img)
                    all_images.append(img)
                if len(all_images) >= n:
                    break
            if len(all_images) >= n:
                break

        try:
            await token_mgr.consume(token, self._get_effort(model_info))
        except Exception as e:
            logger.warning(f"Failed to consume token: {e}")

        selected = self._select_images(all_images, n)
        usage_override = {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "input_tokens_details": {"text_tokens": 0, "image_tokens": 0},
        }
        return ImageGenerationResult(
            stream=False, data=selected, usage_override=usage_override
        )

    async def _collect_http(
        self,
        *,
        token_mgr: Any,
        token: str,
        model_info: Any,
        prompt: str,
        n: int,
        response_format: str,
    ) -> ImageGenerationResult:
        calls_needed = (n + 1) // 2

        async def _call_grok():
            success = False
            try:
                response = await GrokChatService().chat(
                    token=token,
                    message=f"Image Generation: {prompt}",
                    model=model_info.grok_model,
                    mode=model_info.model_mode,
                    stream=True,
                )
                processor = ImageCollectProcessor(
                    model_info.model_id, token, response_format=response_format
                )
                images = await processor.process(response)
                success = True
                return images
            except Exception as e:
                logger.error(f"Grok image call failed: {e}")
                return []
            finally:
                if success:
                    try:
                        await token_mgr.consume(token, self._get_effort(model_info))
                    except Exception as e:
                        logger.warning(f"Failed to consume token: {e}")

        if calls_needed == 1:
            all_images = await _call_grok()
        else:
            tasks = [_call_grok() for _ in range(calls_needed)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_images: List[str] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Concurrent call failed: {result}")
                elif isinstance(result, list):
                    all_images.extend(result)

        selected = self._select_images(all_images, n)
        return ImageGenerationResult(stream=False, data=selected)

    @staticmethod
    def _get_effort(model_info: Any) -> EffortType:
        return (
            EffortType.HIGH
            if (model_info and model_info.cost.value == "high")
            else EffortType.LOW
        )

    @staticmethod
    def _select_images(images: List[str], n: int) -> List[str]:
        if len(images) >= n:
            return random.sample(images, n)
        selected = images.copy()
        while len(selected) < n:
            selected.append("error")
        return selected


__all__ = [
    "image_service",
    "ImageService",
    "ImageGenerationService",
    "ImageGenerationResult",
]
