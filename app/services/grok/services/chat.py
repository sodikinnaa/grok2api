"""
Grok Chat 服务
"""

from typing import Dict, List, Any
from dataclasses import dataclass

from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import (
    AppException,
    ValidationException,
    ErrorType,
    UpstreamException,
)
from app.services.grok.models.model import ModelService
from app.services.grok.utils.upload import UploadService
from app.services.grok.processors import StreamProcessor, CollectProcessor
from app.services.reverse import AppChatReverse
from app.services.grok.utils.stream import wrap_stream_with_usage
from app.services.token import get_token_manager, EffortType


@dataclass
class ChatRequest:
    """聊天请求数据"""

    model: str
    messages: List[Dict[str, Any]]
    stream: bool = None
    think: bool = None


class MessageExtractor:
    """消息内容提取器"""

    @staticmethod
    def extract(
        messages: List[Dict[str, Any]], is_video: bool = False
    ) -> tuple[str, List[tuple[str, str]]]:
        """从 OpenAI 消息格式提取内容，返回 (text, attachments)"""
        texts = []
        attachments = []
        extracted = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            parts = []

            if isinstance(content, str):
                if content.strip():
                    parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    item_type = item.get("type", "")

                    if item_type == "text":
                        if text := item.get("text", "").strip():
                            parts.append(text)

                    elif item_type == "image_url":
                        image_data = item.get("image_url", {})
                        url = (
                            image_data.get("url", "")
                            if isinstance(image_data, dict)
                            else str(image_data)
                        )
                        if url:
                            attachments.append(("image", url))

                    elif item_type == "input_audio":
                        if is_video:
                            raise ValueError("视频模型不支持 input_audio 类型")
                        audio_data = item.get("input_audio", {})
                        data = (
                            audio_data.get("data", "")
                            if isinstance(audio_data, dict)
                            else str(audio_data)
                        )
                        if data:
                            attachments.append(("audio", data))

                    elif item_type == "file":
                        if is_video:
                            raise ValueError("视频模型不支持 file 类型")
                        file_data = item.get("file", {})
                        url = file_data.get("url", "") or file_data.get("data", "")
                        if isinstance(file_data, str):
                            url = file_data
                        if url:
                            attachments.append(("file", url))

            if parts:
                extracted.append({"role": role, "text": "\n".join(parts)})

        # 找到最后一条 user 消息
        last_user_index = next(
            (
                i
                for i in range(len(extracted) - 1, -1, -1)
                if extracted[i]["role"] == "user"
            ),
            None,
        )

        for i, item in enumerate(extracted):
            role = item["role"] or "user"
            text = item["text"]
            texts.append(text if i == last_user_index else f"{role}: {text}")

        return "\n\n".join(texts), attachments


class ChatRequestBuilder:
    """请求构造器"""

    @staticmethod
    def build_payload(
        message: str,
        model: str,
        mode: str = None,
        file_attachments: List[str] = None,
        image_attachments: List[str] = None,
    ) -> Dict[str, Any]:
        """构造请求体"""
        return AppChatReverse.build_payload(
            message=message,
            model=model,
            mode=mode,
            file_attachments=file_attachments,
            image_attachments=image_attachments,
        )


class GrokChatService:
    """Grok API 调用服务"""

    def __init__(self):
        pass

    async def chat(
        self,
        token: str,
        message: str,
        model: str = "grok-3",
        mode: str = None,
        stream: bool = None,
        file_attachments: List[str] = None,
        image_attachments: List[str] = None,
        tool_overrides: Dict[str, Any] = None,
        model_config_override: Dict[str, Any] = None,
    ):
        """发送聊天请求"""
        if stream is None:
            stream = get_config("chat.stream")

        logger.debug(
            f"Chat request: model={model}, mode={mode}, stream={stream}, attachments={len(file_attachments or [])}"
        )

        browser = get_config("security.browser")
        session = AsyncSession(impersonate=browser)
        try:
            stream_response = await AppChatReverse.request(
                session,
                token,
                message=message,
                model=model,
                mode=mode,
                file_attachments=file_attachments,
                image_attachments=image_attachments,
                tool_overrides=tool_overrides,
                model_config_override=model_config_override,
            )
            logger.info(f"Chat connected: model={model}, stream={stream}")
        except Exception:
            await session.close()
            raise

        return stream_response

    async def chat_openai(self, token: str, request: ChatRequest):
        """OpenAI 兼容接口"""
        model_info = ModelService.get(request.model)
        if not model_info:
            raise ValidationException(f"Unknown model: {request.model}")

        grok_model = model_info.grok_model
        mode = model_info.model_mode
        is_video = model_info.is_video

        # 提取消息和附件
        try:
            message, attachments = MessageExtractor.extract(
                request.messages, is_video=is_video
            )
            logger.debug(
                f"Extracted message length={len(message)}, attachments={len(attachments)}"
            )
        except ValueError as e:
            raise ValidationException(str(e))

        # 上传附件
        file_ids = []
        if attachments:
            upload_service = UploadService()
            try:
                for attach_type, attach_data in attachments:
                    file_id, _ = await upload_service.upload_file(attach_data, token)
                    file_ids.append(file_id)
                    logger.debug(
                        f"Attachment uploaded: type={attach_type}, file_id={file_id}"
                    )
            finally:
                await upload_service.close()

        stream = (
            request.stream if request.stream is not None else get_config("chat.stream")
        )

        response = await self.chat(
            token,
            message,
            grok_model,
            mode,
            stream,
            file_attachments=file_ids,
            image_attachments=[],
        )

        return response, stream, request.model


class ChatService:
    """Chat 业务服务"""

    @staticmethod
    async def completions(
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool = None,
        thinking: str = None,
    ):
        """Chat Completions 入口"""
        # 获取 token
        token_mgr = await get_token_manager()
        await token_mgr.reload_if_stale()

        # 解析参数（只需解析一次）
        think = {"enabled": True, "disabled": False}.get(thinking)
        is_stream = stream if stream is not None else get_config("chat.stream")

        # 构造请求（只需构造一次）
        chat_request = ChatRequest(
            model=model, messages=messages, stream=is_stream, think=think
        )

        # 跨 Token 重试循环
        tried_tokens = set()
        max_token_retries = int(get_config("retry.max_retry"))
        last_error = None

        for attempt in range(max_token_retries):
            # 选择 token（排除已失败的）
            token = None
            for pool_name in ModelService.pool_candidates_for_model(model):
                token = token_mgr.get_token(pool_name, exclude=tried_tokens)
                if token:
                    break

            if not token and not tried_tokens:
                # 首次就无 token，尝试刷新
                logger.info("No available tokens, attempting to refresh cooling tokens...")
                result = await token_mgr.refresh_cooling_tokens()
                if result.get("recovered", 0) > 0:
                    for pool_name in ModelService.pool_candidates_for_model(model):
                        token = token_mgr.get_token(pool_name)
                        if token:
                            break

            if not token:
                if last_error:
                    raise last_error
                raise AppException(
                    message="No available tokens. Please try again later.",
                    error_type=ErrorType.RATE_LIMIT.value,
                    code="rate_limit_exceeded",
                    status_code=429,
                )

            tried_tokens.add(token)

            try:
                # 请求 Grok
                service = GrokChatService()
                response, _, model_name = await service.chat_openai(token, chat_request)

                # 处理响应
                if is_stream:
                    logger.debug(f"Processing stream response: model={model}")
                    processor = StreamProcessor(model_name, token, think)
                    return wrap_stream_with_usage(
                        processor.process(response), token_mgr, token, model
                    )

                # 非流式
                logger.debug(f"Processing non-stream response: model={model}")
                result = await CollectProcessor(model_name, token).process(response)
                try:
                    model_info = ModelService.get(model)
                    effort = (
                        EffortType.HIGH
                        if (model_info and model_info.cost.value == "high")
                        else EffortType.LOW
                    )
                    await token_mgr.consume(token, effort)
                    logger.info(f"Chat completed: model={model}, effort={effort.value}")
                except Exception as e:
                    logger.warning(f"Failed to record usage: {e}")
                return result

            except UpstreamException as e:
                status_code = e.details.get("status") if e.details else None
                last_error = e

                if status_code == 429:
                    # 配额不足，标记 token 为 cooling 并换 token 重试
                    await token_mgr.mark_rate_limited(token)
                    logger.warning(
                        f"Token {token[:10]}... rate limited (429), "
                        f"trying next token (attempt {attempt + 1}/{max_token_retries})"
                    )
                    continue

                # 非 429 错误，不换 token，直接抛出
                raise

        # 所有 token 都 429，抛出最后的错误
        if last_error:
            raise last_error
        raise AppException(
            message="No available tokens. Please try again later.",
            error_type=ErrorType.RATE_LIMIT.value,
            code="rate_limit_exceeded",
            status_code=429,
        )


__all__ = [
    "GrokChatService",
    "ChatRequest",
    "ChatRequestBuilder",
    "MessageExtractor",
    "ChatService",
]
