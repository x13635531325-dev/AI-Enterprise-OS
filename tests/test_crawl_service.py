from app.core.config import Settings
from app.schemas.crawls import CreateCrawlRequest
from app.services import crawl_service as crawl_service_module
from app.services.crawl_service import CrawlService
from app.storage.crawl_repository import CrawlRepository


def test_capabilities_include_ready_local_storage(tmp_path):
    service = CrawlService(
        repository=CrawlRepository(str(tmp_path / "crawl.sqlite3")),
        app_settings=Settings(
            _env_file=None,
            crawl_local_storage_dir=tmp_path / "exports",
        ),
    )

    local = next(
        item for item in service.capabilities().destinations if item.name == "local"
    )

    assert local.configured is True
    assert local.detail == "Local file storage is ready."


def test_delivery_error_marks_crawl_job_failed(monkeypatch, tmp_path):
    repository = CrawlRepository(str(tmp_path / "crawl.sqlite3"))
    settings = Settings(
        _env_file=None,
        mysql_host="db.example.com",
        mysql_user="crawler",
        mysql_password="test-only",
        mysql_database="crawler_test",
        crawl_checkpoint_dir=tmp_path / "checkpoints",
    )
    service = CrawlService(repository=repository, app_settings=settings)
    request = CreateCrawlRequest(
        name="docs",
        start_urls=["https://example.com/docs"],
        fields=[{"name": "title", "selector": "h1::text"}],
        destinations={
            "oss": {"enabled": False},
            "mysql": {"enabled": True},
        },
    )
    job = service.create_job(request)

    class FakeSpider:
        delivery_errors = ["CrawlDeliveryError: MySQL unavailable"]

        def start(self):
            return type("Result", (), {})()

    monkeypatch.setattr(
        crawl_service_module,
        "build_scrapling_spider",
        lambda **_kwargs: FakeSpider(),
    )

    service.execute_job(job.id)

    failed = repository.get_job(job.id)
    assert failed.status == "failed"
    assert "MySQL unavailable" in failed.error


def test_recover_interrupted_jobs_marks_them_paused(tmp_path):
    repository = CrawlRepository(str(tmp_path / "crawl.sqlite3"))
    request = CreateCrawlRequest(
        name="docs",
        start_urls=["https://example.com/docs"],
        fields=[{"name": "title", "selector": "h1::text"}],
        destinations={
            "oss": {"enabled": False},
            "mysql": {"enabled": True},
        },
    )
    job = repository.create_job(request)
    repository.mark_running(job.id)

    count = repository.recover_interrupted_jobs()

    recovered = repository.get_job(job.id)
    assert count == 1
    assert recovered.status == "paused"
    assert "Retry to resume" in recovered.error
