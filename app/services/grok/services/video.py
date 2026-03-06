"""
Grok video generation service.
"""

import asyncio
import uuid
import re
from typing import Any, AsyncGenerator, AsyncIterable, Optional, Tuple, List, Dict

import orjson
from curl_cffi.requests.errors import RequestsError

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import (
    UpstreamException,
    AppException,
    ValidationException,
    ErrorType,
    StreamIdleTimeoutError,
)
from app.services.grok.services.model import ModelService
from app.services.token import get_token_manager, EffortType
from app.services.grok.utils.stream import wrap_stream_with_usage
from app.services.grok.utils.process import (
    BaseProcessor,
    _with_idle_timeout,
    _normalize_line,
    _is_http2_error,
)
from app.services.grok.utils.retry import rate_limited
from app.services.reverse.app_chat import AppChatReverse
from app.services.reverse.media_post import MediaPostReverse
from app.services.reverse.video_upscale import VideoUpscaleReverse
from app.services.reverse.utils.session import ResettableSession
from app.services.token.manager import BASIC_POOL_NAME

_VIDEO_SEMAPHORE = None
_VIDEO_SEM_VALUE = 0
_VIDEO_EXTENSION_EPS = 1.0 / 24.0


def _build_mode_flag(preset: str) -> str:
    mode_map = {
        "fun": "--mode=extremely-crazy",
        "normal": "--mode=normal",
        "spicy": "--mode=extremely-spicy-or-crazy",
        "custom": "--mode=custom",
    }
    return mode_map.get(preset, "--mode=custom")


def _build_message(prompt: str, preset: str) -> str:
    mode_flag = _build_mode_flag(preset)
    message = f"{prompt} {mode_flag}".strip()
    return message


def _build_base_config(
    parent_post_id: str,
    aspect_ratio: str,
    resolution_name: str,
    video_length: int,
) -> Dict[str, Any]:
    return {
        "modelMap": {
            "videoGenModelConfig": {
                "aspectRatio": aspect_ratio,
                "parentPostId": parent_post_id,
                "resolutionName": resolution_name,
                "videoLength": video_length,
            }
        }
    }


def _build_extension_config(
    *,
    parent_post_id: str,
    extend_post_id: str,
    original_post_id: str,
    original_prompt: str,
    aspect_ratio: str,
    resolution_name: str,
    video_length: int,
    start_time: float,
) -> Dict[str, Any]:
    return {
        "modelMap": {
            "videoGenModelConfig": {
                "isVideoExtension": True,
                "videoExtensionStartTime": start_time,
                "extendPostId": extend_post_id,
                "stitchWithExtendPostId": True,
                "originalPrompt": original_prompt,
                "originalPostId": original_post_id,
                "originalRefType": "ORIGINAL_REF_TYPE_VIDEO_EXTENSION",
                "mode": "custom",
                "aspectRatio": aspect_ratio,
                "videoLength": video_length,
                "resolutionName": resolution_name,
                "parentPostId": parent_post_id,
                "isVideoEdit": False,
            }
        }
    }


def _compute_extension_steps(target_length: int, *, is_super: bool) -> List[int]:
    if is_super:
        base = 10 if target_length >= 10 else 6
        chunk = 10
    else:
        base = 6
        chunk = 6

    steps = [base]
    remaining = max(0, target_length - base)
    full = remaining // chunk
    rem = remaining % chunk
    if full > 0:
        steps.extend([chunk] * full)
    if rem > 0:
        steps.append(rem)
    return steps


def _extract_post_id(resp: dict, video_resp: Optional[dict]) -> Optional[str]:
    post = resp.get("post")
    if isinstance(post, dict):
        value = post.get("id")
        if isinstance(value, str) and value:
            return value
    for key in ("postId", "post_id"):
        value = resp.get(key)
        if isinstance(value, str) and value:
            return value
    if isinstance(video_resp, dict):
        value = video_resp.get("postId")
        if isinstance(value, str) and value:
            return value
        post = video_resp.get("post")
        if isinstance(post, dict):
            value = post.get("id")
            if isinstance(value, str) and value:
                return value
    for key in ("parentPostId", "originalPostId"):
        value = resp.get(key)
        if isinstance(value, str) and value:
            return value
    return None


async def _collect_video_metadata(
    response: AsyncIterable[bytes],
    *,
    model: str,
) -> Tuple[str, str, Optional[str]]:
    """Collect video metadata without downloading assets."""
    video_url = ""
    thumbnail_url = ""
    post_id: Optional[str] = None
    idle_timeout = get_config("video.stream_timeout")

    iterator = None
    try:
        iterator = _with_idle_timeout(response, idle_timeout, model)
        async for line in iterator:
            line = _normalize_line(line)
            if not line:
                continue
            try:
                data = orjson.loads(line)
            except orjson.JSONDecodeError:
                continue

            resp = data.get("result", {}).get("response", {})
            video_resp = resp.get("streamingVideoGenerationResponse")
            if post_id is None:
                post_id = _extract_post_id(resp, video_resp)

            if isinstance(video_resp, dict) and video_resp.get("progress") == 100:
                video_url = video_resp.get("videoUrl", "") or ""
                thumbnail_url = video_resp.get("thumbnailImageUrl", "") or ""
                break
    finally:
        if iterator is not None:
            aclose = getattr(iterator, "aclose", None)
            if callable(aclose):
                try:
                    await aclose()
                except Exception:
                    pass
        aclose = getattr(response, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                pass
        close = getattr(response, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    return video_url, thumbnail_url, post_id

def _get_video_semaphore() -> asyncio.Semaphore:
    """Reverse 接口并发控制（video 服务）。"""
    global _VIDEO_SEMAPHORE, _VIDEO_SEM_VALUE
    value = max(1, int(get_config("video.concurrent")))
    if value != _VIDEO_SEM_VALUE:
        _VIDEO_SEM_VALUE = value
        _VIDEO_SEMAPHORE = asyncio.Semaphore(value)
    return _VIDEO_SEMAPHORE


def _new_session() -> ResettableSession:
    browser = get_config("proxy.browser")
    if browser:
        return ResettableSession(impersonate=browser)
    return ResettableSession()


class VideoService:
    """Video generation service."""

    def __init__(self):
        self.timeout = None

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

            prompt_value = prompt if media_type == "MEDIA_POST_TYPE_VIDEO" else ""
            media_value = media_url or ""

            async with _new_session() as session:
                async with _get_video_semaphore():
                    response = await MediaPostReverse.request(
                        session,
                        token,
                        media_type,
                        media_value,
                        prompt=prompt_value,
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
        post_id = await self.create_post(token, prompt)
        message = _build_message(prompt, preset)
        model_config_override = _build_base_config(
            post_id, aspect_ratio, resolution_name, video_length
        )

        async def _stream():
            session = _new_session()
            try:
                async with _get_video_semaphore():
                    stream_response = await AppChatReverse.request(
                        session,
                        token,
                        message=message,
                        model="grok-3",
                        tool_overrides={"videoGen": True},
                        model_config_override=model_config_override,
                    )
                    logger.info(f"Video generation started: post_id={post_id}")
                    async for line in stream_response:
                        yield line
            except Exception as e:
                try:
                    await session.close()
                except Exception:
                    pass
                logger.error(f"Video generation error: {e}")
                if isinstance(e, AppException):
                    raise
                raise UpstreamException(f"Video generation error: {str(e)}")
            finally:
                try:
                    await session.close()
                except Exception:
                    pass

        return _stream()

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
        post_id = await self.create_image_post(token, image_url)
        message = _build_message(prompt, preset)
        model_config_override = _build_base_config(
            post_id, aspect_ratio, resolution, video_length
        )

        async def _stream():
            session = _new_session()
            try:
                async with _get_video_semaphore():
                    stream_response = await AppChatReverse.request(
                        session,
                        token,
                        message=message,
                        model="grok-3",
                        tool_overrides={"videoGen": True},
                        model_config_override=model_config_override,
                    )
                    logger.info(f"Video generation started: post_id={post_id}")
                    async for line in stream_response:
                        yield line
            except Exception as e:
                try:
                    await session.close()
                except Exception:
                    pass
                logger.error(f"Video generation error: {e}")
                if isinstance(e, AppException):
                    raise
                raise UpstreamException(f"Video generation error: {str(e)}")
            finally:
                try:
                    await session.close()
                except Exception:
                    pass

        return _stream()

    @staticmethod
    async def completions(
        model: str,
        messages: list,
        stream: bool = None,
        reasoning_effort: str | None = None,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution: str = "480p",
        preset: str = "normal",
    ):
        """Video generation entrypoint."""
        # Get token via intelligent routing.
        token_mgr = await get_token_manager()
        await token_mgr.reload_if_stale()

        max_token_retries = int(get_config("retry.max_retry"))
        last_error: Exception | None = None

        if reasoning_effort is None:
            show_think = get_config("app.thinking")
        else:
            show_think = reasoning_effort != "none"
        is_stream = stream if stream is not None else get_config("app.stream")

        # Extract content.
        from app.services.grok.services.chat import MessageExtractor
        from app.services.grok.utils.upload import UploadService

        prompt, file_attachments, image_attachments = MessageExtractor.extract(messages)

        for attempt in range(max_token_retries):
            # Select token based on video requirements and pool candidates.
            pool_candidates = ModelService.pool_candidates_for_model(model)
            token_info = token_mgr.get_token_for_video(
                resolution=resolution,
                video_length=video_length,
                pool_candidates=pool_candidates,
            )

            if not token_info:
                if last_error:
                    raise last_error
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
            pool_name = token_mgr.get_pool_name_for_token(token)
            requested_resolution = resolution
            should_upscale = requested_resolution == "720p" and pool_name == BASIC_POOL_NAME
            generation_resolution = (
                "480p" if should_upscale else requested_resolution
            )
            steps = _compute_extension_steps(
                int(video_length or 6), is_super=pool_name != BASIC_POOL_NAME
            )

            try:
                # Handle image attachments.
                image_url = None
                if image_attachments:
                    upload_service = UploadService()
                    try:
                        if len(image_attachments) > 1:
                            logger.info(
                                "Video generation supports a single reference image; using the first one."
                            )
                        attach_data = image_attachments[0]
                        _, file_uri = await upload_service.upload_file(
                            attach_data, token
                        )
                        image_url = f"https://assets.grok.com/{file_uri}"
                        logger.info(f"Image uploaded for video: {image_url}")
                    finally:
                        await upload_service.close()

                # Generate video.
                service = VideoService()
                message = _build_message(prompt, preset)
                model_info = ModelService.get(model)
                effort = (
                    EffortType.HIGH
                    if (model_info and model_info.cost.value == "high")
                    else EffortType.LOW
                )

                if len(steps) == 1:
                    if image_url:
                        response = await service.generate_from_image(
                            token,
                            prompt,
                            image_url,
                            aspect_ratio,
                            steps[0],
                            generation_resolution,
                            preset,
                        )
                    else:
                        response = await service.generate(
                            token,
                            prompt,
                            aspect_ratio,
                            steps[0],
                            generation_resolution,
                            preset,
                        )

                    # Process response.
                    if is_stream:
                        processor = VideoStreamProcessor(
                            model,
                            token,
                            show_think,
                            upscale_on_finish=should_upscale,
                        )
                        return wrap_stream_with_usage(
                            processor.process(response), token_mgr, token, model
                        )

                    result = await VideoCollectProcessor(
                        model, token, upscale_on_finish=should_upscale
                    ).process(response)
                    try:
                        await token_mgr.consume(token, effort)
                        logger.debug(
                            f"Video completed, recorded usage (effort={effort.value})"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to record video usage: {e}")
                    return result

                # Multi-step extension flow (avoid intermediate downloads).
                if image_url:
                    parent_post_id = await service.create_image_post(token, image_url)
                else:
                    parent_post_id = await service.create_post(token, prompt)

                original_post_id = parent_post_id
                extend_post_id = parent_post_id
                current_length = 0

                async def _request_stream(model_config_override: Dict[str, Any]) -> AsyncGenerator[bytes, None]:
                    async def _stream():
                        session = _new_session()
                        try:
                            async with _get_video_semaphore():
                                stream_response = await AppChatReverse.request(
                                    session,
                                    token,
                                    message=message,
                                    model="grok-3",
                                    tool_overrides={"videoGen": True},
                                    model_config_override=model_config_override,
                                )
                                async for line in stream_response:
                                    yield line
                        finally:
                            try:
                                await session.close()
                            except Exception:
                                pass

                    return _stream()

                # Run intermediate steps (collect metadata only).
                for idx, step_length in enumerate(steps[:-1]):
                    if idx == 0:
                        model_config_override = _build_base_config(
                            parent_post_id,
                            aspect_ratio,
                            generation_resolution,
                            step_length,
                        )
                    else:
                        start_time = float(current_length) + _VIDEO_EXTENSION_EPS
                        model_config_override = _build_extension_config(
                            parent_post_id=parent_post_id,
                            extend_post_id=extend_post_id,
                            original_post_id=original_post_id,
                            original_prompt=prompt,
                            aspect_ratio=aspect_ratio,
                            resolution_name=generation_resolution,
                            video_length=step_length,
                            start_time=start_time,
                        )

                    async with _new_session() as session:
                        async with _get_video_semaphore():
                            response = await AppChatReverse.request(
                                session,
                                token,
                                message=message,
                                model="grok-3",
                                tool_overrides={"videoGen": True},
                                model_config_override=model_config_override,
                            )
                            video_url, _, post_id = await _collect_video_metadata(
                                response, model=model
                            )
                    if post_id:
                        extend_post_id = post_id
                    current_length += step_length

                    try:
                        await token_mgr.consume(token, effort)
                        logger.debug(
                            f"Video step completed, recorded usage (effort={effort.value})"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to record video usage: {e}")

                    if not video_url:
                        raise UpstreamException("Video extension step did not return url")

                # Final step (render only once).
                final_length = steps[-1]
                if len(steps) == 1:
                    final_config = _build_base_config(
                        parent_post_id,
                        aspect_ratio,
                        generation_resolution,
                        final_length,
                    )
                else:
                    start_time = float(current_length) + _VIDEO_EXTENSION_EPS
                    final_config = _build_extension_config(
                        parent_post_id=parent_post_id,
                        extend_post_id=extend_post_id,
                        original_post_id=original_post_id,
                        original_prompt=prompt,
                        aspect_ratio=aspect_ratio,
                        resolution_name=generation_resolution,
                        video_length=final_length,
                        start_time=start_time,
                    )

                final_response = await _request_stream(final_config)

                if is_stream:
                    processor = VideoStreamProcessor(
                        model,
                        token,
                        show_think,
                        upscale_on_finish=should_upscale,
                    )
                    return wrap_stream_with_usage(
                        processor.process(final_response), token_mgr, token, model
                    )

                result = await VideoCollectProcessor(
                    model, token, upscale_on_finish=should_upscale
                ).process(final_response)
                try:
                    await token_mgr.consume(token, effort)
                    logger.debug(
                        f"Video completed, recorded usage (effort={effort.value})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to record video usage: {e}")
                return result

            except UpstreamException as e:
                last_error = e
                if rate_limited(e):
                    await token_mgr.mark_rate_limited(token)
                    logger.warning(
                        f"Token {token[:10]}... rate limited (429), "
                        f"trying next token (attempt {attempt + 1}/{max_token_retries})"
                    )
                    continue
                raise

        if last_error:
            raise last_error
        raise AppException(
            message="No available tokens. Please try again later.",
            error_type=ErrorType.RATE_LIMIT.value,
            code="rate_limit_exceeded",
            status_code=429,
        )


class VideoStreamProcessor(BaseProcessor):
    """Video stream response processor."""

    def __init__(
        self,
        model: str,
        token: str = "",
        show_think: bool = None,
        upscale_on_finish: bool = False,
    ):
        super().__init__(model, token)
        self.response_id: Optional[str] = None
        self.think_opened: bool = False
        self.think_closed_once: bool = False
        self.role_sent: bool = False

        self.show_think = bool(show_think)
        self.upscale_on_finish = bool(upscale_on_finish)

    @staticmethod
    def _extract_video_id(video_url: str) -> str:
        if not video_url:
            return ""
        match = re.search(r"/generated/([0-9a-fA-F-]{32,36})/", video_url)
        if match:
            return match.group(1)
        match = re.search(r"/([0-9a-fA-F-]{32,36})/generated_video", video_url)
        if match:
            return match.group(1)
        return ""

    async def _upscale_video_url(self, video_url: str) -> str:
        if not video_url or not self.upscale_on_finish:
            return video_url
        video_id = self._extract_video_id(video_url)
        if not video_id:
            logger.warning("Video upscale skipped: unable to extract video id")
            return video_url
        try:
            async with _new_session() as session:
                response = await VideoUpscaleReverse.request(
                    session, self.token, video_id
                )
            payload = response.json() if response is not None else {}
            hd_url = payload.get("hdMediaUrl") if isinstance(payload, dict) else None
            if hd_url:
                logger.info(f"Video upscale completed: {hd_url}")
                return hd_url
        except Exception as e:
            logger.warning(f"Video upscale failed: {e}")
        return video_url

    def _sse(self, content: str = "", role: str = None, finish: str = None) -> str:
        """Build SSE response."""
        delta = {}
        if role:
            delta["role"] = role
            delta["content"] = ""
        elif content:
            delta["content"] = content

        chunk = {
            "id": self.response_id or f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [
                {"index": 0, "delta": delta, "logprobs": None, "finish_reason": finish}
            ],
        }
        return f"data: {orjson.dumps(chunk).decode()}\n\n"

    async def process(
        self, response: AsyncIterable[bytes]
    ) -> AsyncGenerator[str, None]:
        """Process video stream response."""
        idle_timeout = get_config("video.stream_timeout")

        try:
            async for line in _with_idle_timeout(response, idle_timeout, self.model):
                line = _normalize_line(line)
                if not line:
                    continue
                try:
                    data = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                resp = data.get("result", {}).get("response", {})
                is_thinking = bool(resp.get("isThinking"))

                if rid := resp.get("responseId"):
                    self.response_id = rid

                if not self.role_sent:
                    yield self._sse(role="assistant")
                    self.role_sent = True

                if token := resp.get("token"):
                    if is_thinking and self.think_closed_once:
                        continue
                    if is_thinking:
                        if not self.show_think:
                            continue
                        if not self.think_opened:
                            yield self._sse("<think>\n")
                            self.think_opened = True
                    else:
                        if self.think_opened:
                            yield self._sse("\n</think>\n")
                            self.think_opened = False
                            self.think_closed_once = True
                    yield self._sse(token)
                    continue

                if video_resp := resp.get("streamingVideoGenerationResponse"):
                    progress = video_resp.get("progress", 0)
                    if is_thinking and self.think_closed_once:
                        continue

                    if is_thinking:
                        if not self.show_think:
                            continue
                        if not self.think_opened:
                            yield self._sse("<think>\n")
                            self.think_opened = True
                    else:
                        if self.think_opened:
                            yield self._sse("\n</think>\n")
                            self.think_opened = False
                            self.think_closed_once = True
                    if self.show_think:
                        yield self._sse(f"正在生成视频中，当前进度{progress}%\n")

                    if progress == 100:
                        video_url = video_resp.get("videoUrl", "")
                        thumbnail_url = video_resp.get("thumbnailImageUrl", "")

                        if self.think_opened:
                            yield self._sse("\n</think>\n")
                            self.think_opened = False
                            self.think_closed_once = True

                        if video_url:
                            if self.upscale_on_finish:
                                yield self._sse("正在对视频进行超分辨率\n")
                                video_url = await self._upscale_video_url(video_url)
                            dl_service = self._get_dl()
                            rendered = await dl_service.render_video(
                                video_url, self.token, thumbnail_url
                            )
                            yield self._sse(rendered)

                            logger.info(f"Video generated: {video_url}")
                    continue

            if self.think_opened:
                yield self._sse("</think>\n")
                self.think_closed_once = True
            yield self._sse(finish="stop")
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.debug(
                "Video stream cancelled by client", extra={"model": self.model}
            )
        except StreamIdleTimeoutError as e:
            raise UpstreamException(
                message=f"Video stream idle timeout after {e.idle_seconds}s",
                status_code=504,
                details={
                    "error": str(e),
                    "type": "stream_idle_timeout",
                    "idle_seconds": e.idle_seconds,
                },
            )
        except RequestsError as e:
            if _is_http2_error(e):
                logger.warning(
                    f"HTTP/2 stream error in video: {e}", extra={"model": self.model}
                )
                raise UpstreamException(
                    message="Upstream connection closed unexpectedly",
                    status_code=502,
                    details={"error": str(e), "type": "http2_stream_error"},
                )
            logger.error(
                f"Video stream request error: {e}", extra={"model": self.model}
            )
            raise UpstreamException(
                message=f"Upstream request failed: {e}",
                status_code=502,
                details={"error": str(e)},
            )
        except Exception as e:
            logger.error(
                f"Video stream processing error: {e}",
                extra={"model": self.model, "error_type": type(e).__name__},
            )
        finally:
            await self.close()


class VideoCollectProcessor(BaseProcessor):
    """Video non-stream response processor."""

    def __init__(self, model: str, token: str = "", upscale_on_finish: bool = False):
        super().__init__(model, token)
        self.upscale_on_finish = bool(upscale_on_finish)

    @staticmethod
    def _extract_video_id(video_url: str) -> str:
        if not video_url:
            return ""
        match = re.search(r"/generated/([0-9a-fA-F-]{32,36})/", video_url)
        if match:
            return match.group(1)
        match = re.search(r"/([0-9a-fA-F-]{32,36})/generated_video", video_url)
        if match:
            return match.group(1)
        return ""

    async def _upscale_video_url(self, video_url: str) -> str:
        if not video_url or not self.upscale_on_finish:
            return video_url
        video_id = self._extract_video_id(video_url)
        if not video_id:
            logger.warning("Video upscale skipped: unable to extract video id")
            return video_url
        try:
            async with _new_session() as session:
                response = await VideoUpscaleReverse.request(
                    session, self.token, video_id
                )
            payload = response.json() if response is not None else {}
            hd_url = payload.get("hdMediaUrl") if isinstance(payload, dict) else None
            if hd_url:
                logger.info(f"Video upscale completed: {hd_url}")
                return hd_url
        except Exception as e:
            logger.warning(f"Video upscale failed: {e}")
        return video_url

    async def process(self, response: AsyncIterable[bytes]) -> dict[str, Any]:
        """Process and collect video response."""
        response_id = ""
        content = ""
        idle_timeout = get_config("video.stream_timeout")

        try:
            async for line in _with_idle_timeout(response, idle_timeout, self.model):
                line = _normalize_line(line)
                if not line:
                    continue
                try:
                    data = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                resp = data.get("result", {}).get("response", {})

                if video_resp := resp.get("streamingVideoGenerationResponse"):
                    if video_resp.get("progress") == 100:
                        response_id = resp.get("responseId", "")
                        video_url = video_resp.get("videoUrl", "")
                        thumbnail_url = video_resp.get("thumbnailImageUrl", "")

                        if video_url:
                            if self.upscale_on_finish:
                                video_url = await self._upscale_video_url(video_url)
                            dl_service = self._get_dl()
                            content = await dl_service.render_video(
                                video_url, self.token, thumbnail_url
                            )
                            logger.info(f"Video generated: {video_url}")

        except asyncio.CancelledError:
            logger.debug(
                "Video collect cancelled by client", extra={"model": self.model}
            )
        except StreamIdleTimeoutError as e:
            logger.warning(
                f"Video collect idle timeout: {e}", extra={"model": self.model}
            )
        except RequestsError as e:
            if _is_http2_error(e):
                logger.warning(
                    f"HTTP/2 stream error in video collect: {e}",
                    extra={"model": self.model},
                )
            else:
                logger.error(
                    f"Video collect request error: {e}", extra={"model": self.model}
                )
        except Exception as e:
            logger.error(
                f"Video collect processing error: {e}",
                extra={"model": self.model, "error_type": type(e).__name__},
            )
        finally:
            await self.close()

        return {
            "id": response_id,
            "object": "chat.completion",
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "refusal": None,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


__all__ = ["VideoService"]
