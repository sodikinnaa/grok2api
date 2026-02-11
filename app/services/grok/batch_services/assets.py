"""
Batch assets service.
"""

from typing import Callable, Awaitable, Dict, Any, Optional

from app.services.grok.services.assets import ListService, DeleteService
from app.services.grok.utils.batch import run_in_batches


class BatchAssetsService:
    """Batch assets orchestration."""

    @staticmethod
    async def fetch_details(
        tokens: list[str],
        account_map: Dict[str, Dict[str, Any]],
        *,
        max_concurrent: int,
        batch_size: int,
        include_ok: bool = False,
        on_item: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        account_map = account_map or {}

        async def _fetch_detail(token: str):
            account = account_map.get(token)
            list_service = ListService()
            try:
                count = await list_service.count(token)
                detail = {
                    "token": token,
                    "token_masked": account["token_masked"] if account else token,
                    "count": count,
                    "status": "ok",
                    "last_asset_clear_at": account["last_asset_clear_at"]
                    if account
                    else None,
                }
                if include_ok:
                    return {"ok": True, "detail": detail, "count": count}
                return {"detail": detail, "count": count}
            except Exception as e:
                detail = {
                    "token": token,
                    "token_masked": account["token_masked"] if account else token,
                    "count": 0,
                    "status": f"error: {str(e)}",
                    "last_asset_clear_at": account["last_asset_clear_at"]
                    if account
                    else None,
                }
                if include_ok:
                    return {"ok": False, "detail": detail, "count": 0}
                return {"detail": detail, "count": 0}
            finally:
                await list_service.close()

        return await run_in_batches(
            tokens,
            _fetch_detail,
            max_concurrent=max_concurrent,
            batch_size=batch_size,
            on_item=on_item,
            should_cancel=should_cancel,
        )

    @staticmethod
    async def clear_online(
        tokens: list[str],
        mgr,
        *,
        max_concurrent: int,
        batch_size: int,
        include_ok: bool = False,
        on_item: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        delete_service = DeleteService()

        async def _clear_one(token: str):
            try:
                result = await delete_service.delete_all(token)
                await mgr.mark_asset_clear(token)
                if include_ok:
                    return {"ok": True, "result": result}
                return {"status": "success", "result": result}
            except Exception as e:
                if include_ok:
                    return {"ok": False, "error": str(e)}
                return {"status": "error", "error": str(e)}

        try:
            return await run_in_batches(
                tokens,
                _clear_one,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
                on_item=on_item,
                should_cancel=should_cancel,
            )
        finally:
            await delete_service.close()


__all__ = ["BatchAssetsService"]
