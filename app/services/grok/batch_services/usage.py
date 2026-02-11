"""
Batch usage service.
"""

from typing import Callable, Awaitable, Dict, Any, Optional

from app.services.grok.utils.batch import run_in_batches


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


__all__ = ["BatchUsageService"]
