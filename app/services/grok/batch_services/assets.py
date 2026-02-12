"""
Batch assets service.
"""

import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional, List

from curl_cffi.requests import AsyncSession

from app.core.config import get_config
from app.core.logger import logger
from app.services.reverse import AssetsListReverse, AssetsDeleteReverse
from app.services.grok.utils.locks import _get_assets_semaphore
from app.services.grok.utils.batch import run_in_batches


class BaseAssetsService:
    """Base assets service."""

    def __init__(self):
        self._session: Optional[AsyncSession] = None

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession()
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None


class ListService(BaseAssetsService):
    """Assets list service."""

    async def iter_assets(self, token: str):
        params = {
            "pageSize": 50,
            "orderBy": "ORDER_BY_LAST_USE_TIME",
            "source": "SOURCE_ANY",
            "isLatest": "true",
        }
        page_token = None
        seen_tokens = set()

        async with AsyncSession() as session:
            while True:
                if page_token:
                    if page_token in seen_tokens:
                        logger.warning("Pagination stopped: repeated page token")
                        break
                    seen_tokens.add(page_token)
                    params["pageToken"] = page_token
                else:
                    params.pop("pageToken", None)

                response = await AssetsListReverse.request(
                    session,
                    token,
                    params,
                )

                result = response.json()
                page_assets = result.get("assets", [])
                yield page_assets

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

    async def list(self, token: str) -> List[Dict]:
        assets = []
        async for page_assets in self.iter_assets(token):
            assets.extend(page_assets)
        logger.info(f"List success: {len(assets)} files")
        return assets

    async def count(self, token: str) -> int:
        total = 0
        async for page_assets in self.iter_assets(token):
            total += len(page_assets)
        logger.debug(f"Asset count: {total}")
        return total


class DeleteService(BaseAssetsService):
    """Assets delete service."""

    async def delete(self, token: str, asset_id: str) -> bool:
        async with _get_assets_semaphore():
            session = await self._get_session()
            await AssetsDeleteReverse.request(
                session,
                token,
                asset_id,
            )

            logger.debug(f"Deleted: {asset_id}")
            return True

    async def delete_all(self, token: str) -> Dict[str, int]:
        total = success = failed = 0
        list_service = ListService()

        try:
            async for assets in list_service.iter_assets(token):
                if not assets:
                    continue

                total += len(assets)
                batch_result = await self._delete_batch(token, assets)
                success += batch_result["success"]
                failed += batch_result["failed"]

            if total == 0:
                logger.info("No assets to delete")
                return {"total": 0, "success": 0, "failed": 0, "skipped": True}
        finally:
            await list_service.close()

        logger.info(f"Delete all: total={total}, success={success}, failed={failed}")
        return {"total": total, "success": success, "failed": failed}

    async def _delete_batch(self, token: str, assets: List[Dict]) -> Dict[str, int]:
        batch_size = max(1, int(get_config("performance.assets_delete_batch_size")))
        success = failed = 0

        for i in range(0, len(assets), batch_size):
            batch = assets[i : i + batch_size]
            results = await asyncio.gather(
                *[
                    self._delete_one(token, asset, idx)
                    for idx, asset in enumerate(batch)
                ],
                return_exceptions=True,
            )
            success += sum(1 for r in results if r is True)
            failed += sum(1 for r in results if r is not True)

        return {"success": success, "failed": failed}

    async def _delete_one(self, token: str, asset: Dict, index: int) -> bool:
        await asyncio.sleep(0.01 * index)
        asset_id = asset.get("assetId", "")
        if not asset_id:
            return False
        try:
            return await self.delete(token, asset_id)
        except Exception:
            return False


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
