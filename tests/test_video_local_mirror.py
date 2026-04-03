import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.services.grok.services.video import VideoRoundResult, VideoService
from app.services.grok.utils.download import DownloadService
from main import create_app


def test_download_service_render_video_mirrors_assets_url(monkeypatch):
    calls = []

    async def fake_download_file(self, file_path: str, token: str, media_type: str = "image"):
        calls.append((file_path, token, media_type))
        return None, "video/mp4"

    async def fake_resolve_url(self, path_or_url: str, token: str, media_type: str = "image"):
        return f"https://example.test/{media_type}"

    monkeypatch.setattr(DownloadService, "download_file", fake_download_file)
    monkeypatch.setattr(DownloadService, "resolve_url", fake_resolve_url)
    monkeypatch.setattr(
        "app.services.grok.utils.download.get_config",
        lambda key, default=None: "url" if key == "app.video_format" else default,
    )

    async def _run():
        service = DownloadService()
        try:
            rendered = await service.render_video(
                "https://assets.grok.com/generated/test-video.mp4?sig=abc",
                "secret-token",
            )
        finally:
            await service.close()
        assert rendered == "/v1/files/video/generated-test-video.mp4\n"

    asyncio.run(_run())
    assert calls == [
        ("https://assets.grok.com/generated/test-video.mp4?sig=abc", "secret-token", "video")
    ]


def test_download_service_render_video_mirrors_assets_url_with_explicit_port(monkeypatch):
    calls = []

    async def fake_download_file(self, file_path: str, token: str, media_type: str = "image"):
        calls.append((file_path, token, media_type))
        return None, "video/mp4"

    async def fake_resolve_url(self, path_or_url: str, token: str, media_type: str = "image"):
        return f"https://example.test/{media_type}"

    monkeypatch.setattr(DownloadService, "download_file", fake_download_file)
    monkeypatch.setattr(DownloadService, "resolve_url", fake_resolve_url)
    monkeypatch.setattr(
        "app.services.grok.utils.download.get_config",
        lambda key, default=None: "url" if key == "app.video_format" else default,
    )

    async def _run():
        service = DownloadService()
        try:
            rendered = await service.render_video(
                "https://ASSETS.GROK.COM:443/generated/test-video.mp4?sig=abc",
                "secret-token",
            )
        finally:
            await service.close()
        assert rendered == "/v1/files/video/generated-test-video.mp4\n"

    asyncio.run(_run())
    assert calls == [
        ("https://ASSETS.GROK.COM:443/generated/test-video.mp4?sig=abc", "secret-token", "video")
    ]


def test_download_service_resolve_url_mirrors_assets_url_with_explicit_port(monkeypatch):
    calls = []

    async def fake_download_file(self, file_path: str, token: str, media_type: str = "image"):
        calls.append((file_path, token, media_type))
        return None, "video/mp4"

    monkeypatch.setattr(DownloadService, "download_file", fake_download_file)
    monkeypatch.setattr(
        "app.services.grok.utils.download.get_config",
        lambda key, default=None: "http://localhost:8000" if key == "app.app_url" else default,
    )

    async def _run():
        service = DownloadService()
        try:
            resolved = await service.resolve_url(
                "https://ASSETS.GROK.COM:443/generated/test-video.mp4?sig=abc",
                "secret-token",
                "video",
            )
        finally:
            await service.close()
        assert resolved == "http://localhost:8000/v1/files/video/generated/test-video.mp4"

    asyncio.run(_run())
    assert calls == [
        ("https://ASSETS.GROK.COM:443/generated/test-video.mp4?sig=abc", "secret-token", "video")
    ]


def test_videos_endpoint_prefers_direct_local_file_url(monkeypatch):
    async def fake_completions(**kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "video_url": "/v1/files/video/generated-test-video.mp4",
                        "content": "[video](https://upstream.example/ignored.mp4)",
                    }
                }
            ]
        }

    monkeypatch.setattr(
        "app.api.v1.video.VideoService.completions",
        fake_completions,
    )

    client = TestClient(create_app())
    response = client.post(
        "/v1/videos",
        json={
            "model": "grok-imagine-1.0-video",
            "prompt": "seekor kucing sedang jogging",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "id": payload["id"],
        "object": "video",
        "created_at": payload["created_at"],
        "completed_at": payload["completed_at"],
        "status": "completed",
        "model": "grok-imagine-1.0-video",
        "prompt": "seekor kucing sedang jogging",
        "size": "1792x1024",
        "seconds": "6",
        "quality": "standard",
        "url": "http://testserver/v1/files/video/generated-test-video.mp4",
    }


def test_videos_endpoint_falls_back_to_content_when_direct_url_missing(monkeypatch):
    async def fake_completions(**kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": "[video](/v1/files/video/generated-test-video.mp4)"
                    }
                }
            ]
        }

    monkeypatch.setattr(
        "app.api.v1.video.VideoService.completions",
        fake_completions,
    )

    client = TestClient(create_app())
    response = client.post(
        "/v1/videos",
        json={
            "model": "grok-imagine-1.0-video",
            "prompt": "seekor kucing sedang jogging",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "http://testserver/v1/files/video/generated-test-video.mp4"


def test_videos_endpoint_falls_back_to_upstream_url_when_not_local(monkeypatch):
    upstream_url = "https://example.test/video.mp4"

    async def fake_completions(**kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": f"[video]({upstream_url})"
                    }
                }
            ]
        }

    monkeypatch.setattr(
        "app.api.v1.video.VideoService.completions",
        fake_completions,
    )

    client = TestClient(create_app())
    response = client.post(
        "/v1/videos",
        json={
            "model": "grok-imagine-1.0-video",
            "prompt": "seekor kucing sedang jogging",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == upstream_url


def test_download_service_resolve_video_output_mirrors_public_video_url(monkeypatch):
    calls = []

    async def fake_download_file(self, file_path: str, token: str, media_type: str = "image"):
        calls.append((file_path, token, media_type))
        return Path("/tmp/data/tmp/video/generated-test-video.mp4"), "video/mp4"

    async def fake_resolve_url(self, path_or_url: str, token: str, media_type: str = "image"):
        return path_or_url

    monkeypatch.setattr(DownloadService, "download_file", fake_download_file)
    monkeypatch.setattr(DownloadService, "resolve_url", fake_resolve_url)

    async def _run():
        service = DownloadService()
        try:
            video_url, thumb_url = await service.resolve_video_output(
                "https://imagine-public.x.ai/share/generated/test-video.mp4?cache=1",
                "secret-token",
            )
        finally:
            await service.close()
        assert video_url == "/v1/files/video/share-generated-test-video.mp4"
        assert thumb_url == ""

    asyncio.run(_run())
    assert calls == [
        (
            "https://imagine-public.x.ai/share/generated/test-video.mp4?cache=1",
            "secret-token",
            "video",
        )
    ]


def test_video_service_completions_non_stream_returns_local_video_url(monkeypatch):
    class DummyTokenInfo:
        token = "secret-token"

    class DummyTokenManager:
        async def reload_if_stale(self):
            return None

        def get_token_for_video(self, **kwargs):
            return DummyTokenInfo()

        def get_pool_name_for_token(self, token):
            return "basic"

        async def consume(self, token, effort):
            return None

    async def fake_create_post(self, token: str, prompt: str, media_type: str = "MEDIA_POST_TYPE_VIDEO", media_url: str = None):
        return "seed-post-id"

    async def fake_request_round_stream(**kwargs):
        async def _empty():
            if False:
                yield b""
        return _empty()

    async def fake_collect_round_result(response, *, model: str, source: str):
        return VideoRoundResult(
            response_id="resp-123",
            post_id="post-123",
            video_url="https://imagine-public.x.ai/share/generated/test-video.mp4?cache=1",
            thumbnail_url="",
            saw_video_event=True,
        )

    async def fake_resolve_video_output(self, video_url: str, token: str, thumbnail_url: str = ""):
        assert video_url == "https://imagine-public.x.ai/share/generated/test-video.mp4?cache=1"
        return "/v1/files/video/share-generated-test-video.mp4", ""

    async def fake_render_video(self, video_url: str, token: str, thumbnail_url: str = ""):
        return f"[video]({video_url})"

    async def fake_get_token_manager():
        return DummyTokenManager()

    monkeypatch.setattr("app.services.grok.services.video.get_token_manager", fake_get_token_manager)
    monkeypatch.setattr("app.services.grok.services.video.ModelService.pool_candidates_for_model", lambda model: ["dummy-pool"])
    monkeypatch.setattr("app.services.grok.services.video.ModelService.get", lambda model: None)
    monkeypatch.setattr("app.services.grok.services.video.VideoService.create_post", fake_create_post)
    monkeypatch.setattr("app.services.grok.services.video._request_round_stream", fake_request_round_stream)
    monkeypatch.setattr("app.services.grok.services.video._collect_round_result", fake_collect_round_result)
    monkeypatch.setattr(DownloadService, "resolve_video_output", fake_resolve_video_output)
    monkeypatch.setattr(DownloadService, "render_video", fake_render_video)
    monkeypatch.setattr(
        "app.services.grok.services.video.get_config",
        lambda key, default=None: {
            "app.stream": False,
            "app.thinking": False,
            "retry.max_retry": 1,
            "video.upscale_timing": "complete",
            "video.enable_public_asset": False,
        }.get(key, default),
    )

    result = asyncio.run(
        VideoService.completions(
            model="grok-imagine-1.0-video",
            messages=[{"role": "user", "content": "seekor kucing sedang jogging"}],
            stream=False,
            aspect_ratio="3:2",
            video_length=6,
            resolution="480p",
            preset="custom",
        )
    )

    message = result["choices"][0]["message"]
    assert message["video_url"] == "/v1/files/video/share-generated-test-video.mp4"
    assert message["content"] == "[video](/v1/files/video/share-generated-test-video.mp4)"
