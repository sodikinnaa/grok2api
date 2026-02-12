"""
Batch usage service.
"""

import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional

from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import get_config
from app.services.reverse import RateLimitsReverse
from app.services.grok.utils.batch import run_in_batches

_USAGE_SEMAPHORE = asyncio.Semaphore(25)
_USAGE_SEM_VALUE = 25


class UsageService:
    """用量查询服务"""

    async def get(self, token: str) -> Dict:
        """
        获取速率限制信息

        Args:
            token: 认证 Token

        Returns:
            响应数据

        Raises:
            UpstreamException: 当获取失败且重试耗尽时
        """
        value = get_config("performance.usage_max_concurrent")
        try:
            value = int(value)
        except Exception:
            value = 25
        value = max(1, value)
        global _USAGE_SEMAPHORE, _USAGE_SEM_VALUE
        if value != _USAGE_SEM_VALUE:
            _USAGE_SEM_VALUE = value
            _USAGE_SEMAPHORE = asyncio.Semaphore(value)
        async with _USAGE_SEMAPHORE:
            try:
                async with AsyncSession() as session:
                    response = await RateLimitsReverse.request(session, token)
                data = response.json()
                remaining = data.get("remainingTokens", 0)
                logger.info(
                    f"Usage sync success: remaining={remaining}, token={token[:10]}..."
                )
                return data

            except Exception:
                # 最后一次失败已经被记录
                raise


class BatchUsageService:
    """Batch usage orchestration."""

    @staticmethod
    async def refresh(
        tokens: list[str],
        mgr,
        *,
        max_concurrent: int,
        batch_size: int,
        on_item: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        async def _refresh_one(t: str):
            return await mgr.sync_usage(t, consume_on_fail=False, is_usage=False)

        return await run_in_batches(
            tokens,
            _refresh_one,
            max_concurrent=max_concurrent,
            batch_size=batch_size,
            on_item=on_item,
            should_cancel=should_cancel,
        )


__all__ = ["BatchUsageService", "UsageService"]
