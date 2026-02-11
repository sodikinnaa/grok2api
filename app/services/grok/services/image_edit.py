"""
Grok image edit service.
"""

import asyncio
import random
import re
from dataclasses import dataclass
from typing import AsyncGenerator, List, Union, Any

from app.core.exceptions import AppException, ErrorType
from app.core.logger import logger
from app.services.grok.processors import ImageCollectProcessor, ImageStreamProcessor
from app.services.grok.services.assets import UploadService
from app.services.grok.services.chat import GrokChatService
from app.services.grok.services.video import VideoService
from app.services.grok.utils.stream import wrap_stream_with_usage


@dataclass
class ImageEditResult:
    stream: bool
    data: Union[AsyncGenerator[str, None], List[str]]


class ImageEditService:
    """Image edit orchestration service."""

    async def edit(
        self,
        *,
        token_mgr: Any,
        token: str,
        model_info: Any,
        prompt: str,
        images: List[str],
        n: int,
        response_format: str,
        stream: bool,
    ) -> ImageEditResult:
        image_urls = await self._upload_images(images, token)
        parent_post_id = await self._get_parent_post_id(token, image_urls)

        model_config_override = {
            "modelMap": {
                "imageEditModel": "imagine",
                "imageEditModelConfig": {
                    "imageReferences": image_urls,
                },
            }
        }
        if parent_post_id:
            model_config_override["modelMap"]["imageEditModelConfig"][
                "parentPostId"
            ] = parent_post_id

        tool_overrides = {"imageGen": True}

        if stream:
            response = await GrokChatService().chat(
                token=token,
                message=prompt,
                model=model_info.grok_model,
                mode=None,
                stream=True,
                tool_overrides=tool_overrides,
                model_config_override=model_config_override,
            )
            processor = ImageStreamProcessor(
                model_info.model_id,
                token,
                n=n,
                response_format=response_format,
            )
            return ImageEditResult(
                stream=True,
                data=wrap_stream_with_usage(
                    processor.process(response),
                    token_mgr,
                    token,
                    model_info.model_id,
                ),
            )

        images_out = await self._collect_images(
            token=token,
            prompt=prompt,
            model_info=model_info,
            n=n,
            response_format=response_format,
            tool_overrides=tool_overrides,
            model_config_override=model_config_override,
        )
        return ImageEditResult(stream=False, data=images_out)

    async def _upload_images(self, images: List[str], token: str) -> List[str]:
        image_urls: List[str] = []
        upload_service = UploadService()
        try:
            for image in images:
                _, file_uri = await upload_service.upload(image, token)
                if file_uri:
                    if file_uri.startswith("http"):
                        image_urls.append(file_uri)
                    else:
                        image_urls.append(
                            f"https://assets.grok.com/{file_uri.lstrip('/')}"
                        )
        finally:
            await upload_service.close()

        if not image_urls:
            raise AppException(
                message="Image upload failed",
                error_type=ErrorType.SERVER.value,
                code="upload_failed",
            )

        return image_urls

    async def _get_parent_post_id(self, token: str, image_urls: List[str]) -> str:
        parent_post_id = None
        try:
            media_service = VideoService()
            parent_post_id = await media_service.create_image_post(token, image_urls[0])
            logger.debug(f"Parent post ID: {parent_post_id}")
        except Exception as e:
            logger.warning(f"Create image post failed: {e}")

        if parent_post_id:
            return parent_post_id

        for url in image_urls:
            match = re.search(r"/generated/([a-f0-9-]+)/", url)
            if match:
                parent_post_id = match.group(1)
                logger.debug(f"Parent post ID: {parent_post_id}")
                break
            match = re.search(r"/users/[^/]+/([a-f0-9-]+)/content", url)
            if match:
                parent_post_id = match.group(1)
                logger.debug(f"Parent post ID: {parent_post_id}")
                break

        return parent_post_id or ""

    async def _collect_images(
        self,
        *,
        token: str,
        prompt: str,
        model_info: Any,
        n: int,
        response_format: str,
        tool_overrides: dict,
        model_config_override: dict,
    ) -> List[str]:
        calls_needed = (n + 1) // 2

        async def _call_edit():
            response = await GrokChatService().chat(
                token=token,
                message=prompt,
                model=model_info.grok_model,
                mode=None,
                stream=True,
                tool_overrides=tool_overrides,
                model_config_override=model_config_override,
            )
            processor = ImageCollectProcessor(
                model_info.model_id, token, response_format=response_format
            )
            return await processor.process(response)

        if calls_needed == 1:
            all_images = await _call_edit()
        else:
            tasks = [_call_edit() for _ in range(calls_needed)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_images: List[str] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Concurrent call failed: {result}")
                elif isinstance(result, list):
                    all_images.extend(result)

        if len(all_images) >= n:
            return random.sample(all_images, n)

        selected_images = all_images.copy()
        while len(selected_images) < n:
            selected_images.append("error")
        return selected_images


__all__ = ["ImageEditService", "ImageEditResult"]
