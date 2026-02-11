"""
Batch NSFW service.
"""

from typing import Callable, Awaitable, Dict, Any, Optional

from app.services.grok.services.nsfw import NSFWService
from app.services.grok.utils.batch import run_in_batches


class BatchNSFWService:
    """Batch NSFW orchestration."""

    @staticmethod
    async def enable(
        tokens: list[str],
        mgr,
        *,
        max_concurrent: int,
        batch_size: int,
        on_item: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        nsfw_service = NSFWService()

        async def _enable(token: str):
            result = await nsfw_service.enable(token)
            if result.success:
                await mgr.add_tag(token, "nsfw")
            return {
                "success": result.success,
                "http_status": result.http_status,
                "grpc_status": result.grpc_status,
                "grpc_message": result.grpc_message,
                "error": result.error,
            }

        return await run_in_batches(
            tokens,
            _enable,
            max_concurrent=max_concurrent,
            batch_size=batch_size,
            on_item=on_item,
            should_cancel=should_cancel,
        )


__all__ = ["BatchNSFWService"]
