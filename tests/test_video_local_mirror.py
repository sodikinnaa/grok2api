import asyncio

from fastapi.testclient import TestClient

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


def test_videos_endpoint_returns_absolute_local_file_url(monkeypatch):
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
