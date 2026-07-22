from fastapi.testclient import TestClient

from app.api.routes.crawls import crawl_service
from app.main import app
from app.storage.crawl_repository import CrawlRepository
from app.core.config import Settings


client = TestClient(app)


def test_crawl_capabilities_do_not_expose_credentials():
    response = client.get("/api/crawls/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scrapling_version"] == "0.4.11"
    assert "access_key" not in str(payload).lower()


def test_create_crawl_queues_background_job(monkeypatch, tmp_path):
    original_repository = crawl_service.repository
    original_settings = crawl_service.settings
    crawl_service.repository = CrawlRepository(str(tmp_path / "api-crawl.sqlite3"))
    crawl_service.settings = Settings(
        _env_file=None,
        mysql_host="db.example.com",
        mysql_user="crawler",
        mysql_password="test-only",
        mysql_database="crawler_test",
    )
    executed = []
    monkeypatch.setattr(crawl_service, "execute_job", executed.append)
    try:
        response = client.post(
            "/api/crawls",
            json={
                "name": "docs",
                "start_urls": ["https://example.com/docs"],
                "fields": [{"name": "title", "selector": "h1::text"}],
                "destinations": {
                    "oss": {"enabled": False},
                    "mysql": {"enabled": True},
                },
            },
        )
    finally:
        crawl_service.repository = original_repository
        crawl_service.settings = original_settings

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert executed == [response.json()["id"]]


def test_create_crawl_rejects_unconfigured_destination():
    original_settings = crawl_service.settings
    crawl_service.settings = Settings(_env_file=None)
    try:
        response = client.post(
            "/api/crawls",
            json={
                "name": "docs",
                "start_urls": ["https://example.com/docs"],
                "fields": [{"name": "title", "selector": "h1::text"}],
                "destinations": {
                    "local": {"enabled": False},
                    "oss": {"enabled": True},
                    "mysql": {"enabled": False},
                },
            },
        )
    finally:
        crawl_service.settings = original_settings

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_create_crawl_accepts_local_only_destination(monkeypatch, tmp_path):
    original_repository = crawl_service.repository
    original_settings = crawl_service.settings
    crawl_service.repository = CrawlRepository(str(tmp_path / "local-api.sqlite3"))
    crawl_service.settings = Settings(
        _env_file=None,
        crawl_local_storage_dir=tmp_path / "exports",
    )
    executed = []
    monkeypatch.setattr(crawl_service, "execute_job", executed.append)
    try:
        response = client.post(
            "/api/crawls",
            json={
                "name": "local-docs",
                "start_urls": ["https://example.com/docs"],
                "fields": [{"name": "title", "selector": "h1::text"}],
                "destinations": {
                    "local": {"enabled": True, "directory": "docs"},
                    "oss": {"enabled": False},
                    "mysql": {"enabled": False},
                },
            },
        )
    finally:
        crawl_service.repository = original_repository
        crawl_service.settings = original_settings

    assert response.status_code == 202
    assert response.json()["request"]["destinations"]["local"]["enabled"] is True
    assert executed == [response.json()["id"]]
