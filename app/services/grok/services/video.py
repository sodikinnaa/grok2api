"""
Grok video generation service.
"""

import asyncio
from typing import AsyncGenerator
from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import (
    UpstreamException,
    AppException,
    ValidationException,
    ErrorType,
)
from app.services.grok.models.model import ModelService
from app.services.token import get_token_manager, EffortType
from app.services.grok.processors import VideoStreamProcessor, VideoCollectProcessor
from app.services.grok.utils.stream import wrap_stream_with_usage
from app.services.reverse import AppChatReverse, MediaPostReverse

_MEDIA_SEMAPHORE = None
_MEDIA_SEM_VALUE = 0


def _get_semaphore() -> asyncio.Semaphore:
    """Get or refresh the semaphore."""
    global _MEDIA_SEMAPHORE, _MEDIA_SEM_VALUE
    value = max(1, int(get_config("performance.media_max_concurrent")))
    if value != _MEDIA_SEM_VALUE:
        _MEDIA_SEM_VALUE = value
        _MEDIA_SEMAPHORE = asyncio.Semaphore(value)
    return _MEDIA_SEMAPHORE


class VideoService:
    """Video generation service."""

    def __init__(self):
        self.timeout = get_config("network.timeout")

    async def create_post(
        self,
        token: str,
        prompt: str,
        media_type: str = "MEDIA_POST_TYPE_VIDEO",
        media_url: str = None,
    ) -> str:
        """Create media post and return post ID."""
        try:
            if media_type == "MEDIA_POST_TYPE_IMAGE" and not media_url:
                raise ValidationException("media_url is required for image posts")

            async with AsyncSession() as session:
                response = await MediaPostReverse.request(
                    session,
                    token,
                    media_type,
                    media_url or "",
                )

            post_id = response.json().get("post", {}).get("id", "")
            if not post_id:
                raise UpstreamException("No post ID in response")

            logger.info(f"Media post created: {post_id} (type={media_type})")
            return post_id

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Create post error: {e}")
            raise UpstreamException(f"Create post error: {str(e)}")

    async def create_image_post(self, token: str, image_url: str) -> str:
        """Create image post and return post ID."""
        return await self.create_post(
            token, prompt="", media_type="MEDIA_POST_TYPE_IMAGE", media_url=image_url
        )

    def _build_payload(
        self,
        prompt: str,
        post_id: str,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution_name: str = "480p",
        preset: str = "normal",
    ) -> dict:
        """Build video generation payload."""
        mode_map = {
            "fun": "--mode=extremely-crazy",
            "normal": "--mode=normal",
            "spicy": "--mode=extremely-spicy-or-crazy",
        }
        mode_flag = mode_map.get(preset, "--mode=custom")

        payload = {
            "temporary": True,
            "modelName": "grok-3",
            "message": f"{prompt} {mode_flag}",
            "toolOverrides": {"videoGen": True},
            "enableSideBySide": True,
            "deviceEnvInfo": {
                "darkModeEnabled": False,
                "devicePixelRatio": 2,
                "screenWidth": 1920,
                "screenHeight": 1080,
                "viewportWidth": 1920,
                "viewportHeight": 1080,
            },
            "responseMetadata": {
                "experiments": [],
                "modelConfigOverride": {
                    "modelMap": {
                        "videoGenModelConfig": {
                            "aspectRatio": aspect_ratio,
                            "parentPostId": post_id,
                            "resolutionName": resolution_name,
                            "videoLength": video_length,
                        }
                    }
                },
            },
        }

        logger.debug(f"Video generation payload: {payload}")

        return payload

    async def _generate_internal(
        self,
        token: str,
        post_id: str,
        prompt: str,
        aspect_ratio: str,
        video_length: int,
        resolution_name: str,
        preset: str,
    ) -> AsyncGenerator[bytes, None]:
        """Internal generation logic."""
        session = None
        try:
            payload = self._build_payload(
                prompt, post_id, aspect_ratio, video_length, resolution_name, preset
            )

            session = AsyncSession()
            stream_response = await AppChatReverse.request(
                session,
                token,
                message=payload.get("message"),
                model=payload.get("modelName"),
                tool_overrides=payload.get("toolOverrides"),
                model_config_override=(
                    (payload.get("responseMetadata") or {}).get("modelConfigOverride")
                ),
            )

            logger.info(f"Video generation started: post_id={post_id}")

            return stream_response

        except Exception as e:
            if session:
                try:
                    await session.close()
                except Exception:
                    pass
            logger.error(f"Video generation error: {e}")
            if isinstance(e, AppException):
                raise
            raise UpstreamException(f"Video generation error: {str(e)}")

    async def generate(
        self,
        token: str,
        prompt: str,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution_name: str = "480p",
        preset: str = "normal",
    ) -> AsyncGenerator[bytes, None]:
        """Generate video."""
        logger.info(
            f"Video generation: prompt='{prompt[:50]}...', ratio={aspect_ratio}, length={video_length}s, preset={preset}"
        )
        async with _get_semaphore():
            post_id = await self.create_post(token, prompt)
            return await self._generate_internal(
                token,
                post_id,
                prompt,
                aspect_ratio,
                video_length,
                resolution_name,
                preset,
            )

    async def generate_from_image(
        self,
        token: str,
        prompt: str,
        image_url: str,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution: str = "480p",
        preset: str = "normal",
    ) -> AsyncGenerator[bytes, None]:
        """Generate video from image."""
        logger.info(
            f"Image to video: prompt='{prompt[:50]}...', image={image_url[:80]}"
        )
        async with _get_semaphore():
            post_id = await self.create_image_post(token, image_url)
            return await self._generate_internal(
                token, post_id, prompt, aspect_ratio, video_length, resolution, preset
            )

    @staticmethod
    async def completions(
        model: str,
        messages: list,
        stream: bool = None,
        thinking: str = None,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution: str = "480p",
        preset: str = "normal",
    ):
        """Video generation entrypoint."""
        # Get token via intelligent routing.
        token_mgr = await get_token_manager()
        await token_mgr.reload_if_stale()

        # Select token based on video requirements and pool candidates.
        pool_candidates = ModelService.pool_candidates_for_model(model)
        token_info = token_mgr.get_token_for_video(
            resolution=resolution,
            video_length=video_length,
            pool_candidates=pool_candidates,
        )

        if not token_info:
            raise AppException(
                message="No available tokens. Please try again later.",
                error_type=ErrorType.RATE_LIMIT.value,
                code="rate_limit_exceeded",
                status_code=429,
            )

        # Extract token string from TokenInfo.
        token = token_info.token
        if token.startswith("sso="):
            token = token[4:]

        think = {"enabled": True, "disabled": False}.get(thinking)
        is_stream = stream if stream is not None else get_config("chat.stream")

        # Extract content.
        from app.services.grok.services.chat import MessageExtractor
        from app.services.grok.utils.upload import UploadService

        try:
            prompt, attachments = MessageExtractor.extract(messages, is_video=True)
        except ValueError as e:
            raise ValidationException(str(e))

        # Handle image attachments.
        image_url = None
        if attachments:
            upload_service = UploadService()
            try:
                for attach_type, attach_data in attachments:
                    if attach_type == "image":
                        _, file_uri = await upload_service.upload_file(attach_data, token)
                        image_url = f"https://assets.grok.com/{file_uri}"
                        logger.info(f"Image uploaded for video: {image_url}")
                        break
            finally:
                await upload_service.close()

        # Generate video.
        service = VideoService()
        if image_url:
            response = await service.generate_from_image(
                token, prompt, image_url, aspect_ratio, video_length, resolution, preset
            )
        else:
            response = await service.generate(
                token, prompt, aspect_ratio, video_length, resolution, preset
            )

        # Process response.
        if is_stream:
            processor = VideoStreamProcessor(model, token, think)
            return wrap_stream_with_usage(
                processor.process(response), token_mgr, token, model
            )

        result = await VideoCollectProcessor(model, token).process(response)
        try:
            model_info = ModelService.get(model)
            effort = (
                EffortType.HIGH
                if (model_info and model_info.cost.value == "high")
                else EffortType.LOW
            )
            await token_mgr.consume(token, effort)
            logger.debug(f"Video completed, recorded usage (effort={effort.value})")
        except Exception as e:
            logger.warning(f"Failed to record video usage: {e}")
        return result


__all__ = ["VideoService"]
