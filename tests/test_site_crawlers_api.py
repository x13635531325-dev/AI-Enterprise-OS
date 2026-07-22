from fastapi.testclient import TestClient

from app.api.routes.site_crawlers import site_crawler_service
from app.core.config import Settings
from app.main import app
from app.site_crawlers.registry import SiteCrawlerRegistry
from app.storage.site_crawler_repository import SiteCrawlerRepository


client = TestClient(app)


def test_site_crawler_list_does_not_expose_credentials():
    response = client.get("/api/site-crawlers")

    assert response.status_code == 200
    payload = response.json()
    serialized = str(payload).lower()
    assert "api_key" not in serialized
    assert "password" not in serialized
    assert "secret" not in serialized


def test_create_site_crawler_task_queues_registered_adapter(
    monkeypatch,
    tmp_path,
):
    crawler_root = tmp_path / "zxxk"
    executable = crawler_root / ".venv" / "Scripts" / "zxxk-scrapling.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test")
    settings = Settings(
        _env_file=None,
        zxxk_crawler_root=crawler_root,
        site_crawler_manifest_dir=tmp_path / "manifests",
    )
    original_repository = site_crawler_service.repository
    original_registry = site_crawler_service.registry
    original_settings = site_crawler_service.settings
    site_crawler_service.repository = SiteCrawlerRepository(
        str(tmp_path / "site-crawlers.sqlite3")
    )
    site_crawler_service.registry = SiteCrawlerRegistry(settings)
    site_crawler_service.settings = settings
    executed = []
    monkeypatch.setattr(site_crawler_service, "execute_task", executed.append)
    try:
        response = client.post(
            "/api/site-crawler-tasks",
            json={
                "adapter_id": "zxxk",
                "action": "download",
                "limit": 1,
                "max_pages": 2,
                "max_attempts": 2,
            },
        )
    finally:
        site_crawler_service.repository = original_repository
        site_crawler_service.registry = original_registry
        site_crawler_service.settings = original_settings

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert executed == [response.json()["id"]]
