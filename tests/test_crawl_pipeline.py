from app.core.config import Settings
from app.crawling.models import ArtifactLocation, CrawledPage
from app.crawling.pipeline import CrawlOutputPipeline
from app.crawling.sinks.aliyun_oss import AliyunOssSink
from app.schemas.crawls import CreateCrawlRequest
from app.storage.crawl_repository import CrawlRepository


class FakeOssSink:
    def __init__(self):
        self.calls = []

    def put_bytes(self, object_key, data, content_type):
        self.calls.append((object_key, data, content_type))
        return ArtifactLocation(
            uri=f"oss://test-bucket/{object_key}",
            public_url=f"https://cdn.example/{object_key}",
            etag="etag-1",
        )


class FakeMysqlSink:
    def __init__(self):
        self.calls = []

    def write_records(self, **kwargs):
        self.calls.append(kwargs)
        return len(kwargs["records"])


def make_request():
    return CreateCrawlRequest(
        name="docs-crawl",
        start_urls=["https://example.com/docs"],
        fields=[{"name": "title", "selector": "h1::text"}],
        destinations={
            "oss": {
                "enabled": True,
                "bucket_alias": "default",
                "upload_html": True,
                "upload_json": True,
            },
            "mysql": {"enabled": True, "table": "ai_crawl_records"},
        },
    )


def test_pipeline_delivers_to_oss_and_mysql_idempotently(tmp_path):
    repository = CrawlRepository(str(tmp_path / "crawl.sqlite3"))
    request = make_request()
    job = repository.create_job(request)
    oss_sink = FakeOssSink()
    mysql_sink = FakeMysqlSink()
    pipeline = CrawlOutputPipeline(
        settings=Settings(_env_file=None),
        repository=repository,
        request=request,
        oss_sink=oss_sink,
        mysql_sink=mysql_sink,
    )
    page = CrawledPage(
        source_url="https://example.com/docs",
        status_code=200,
        body=b"<html><h1>Docs</h1></html>",
        content_type="text/html; charset=utf-8",
        title="Docs",
        records=[{"title": "Docs"}],
    )

    pipeline.process_page(job.id, page)
    pipeline.process_page(job.id, page)

    saved = repository.get_job(job.id)
    assert saved.pages_crawled == 1
    assert saved.artifacts_uploaded == 2
    assert saved.records_written == 1
    assert len(oss_sink.calls) == 2
    assert len(mysql_sink.calls) == 1
    assert mysql_sink.calls[0]["artifact_uri"].startswith("https://cdn.example/")


def test_pipeline_saves_local_artifacts_idempotently(tmp_path):
    repository = CrawlRepository(str(tmp_path / "crawl.sqlite3"))
    request = CreateCrawlRequest(
        name="local-docs",
        start_urls=["https://example.com/docs"],
        fields=[{"name": "title", "selector": "h1::text"}],
        destinations={
            "local": {"enabled": True, "directory": "exports/docs"},
            "oss": {"enabled": False},
            "mysql": {"enabled": False},
        },
    )
    job = repository.create_job(request)
    storage_root = tmp_path / "local-storage"
    pipeline = CrawlOutputPipeline(
        settings=Settings(
            _env_file=None,
            crawl_local_storage_dir=storage_root,
        ),
        repository=repository,
        request=request,
    )
    page = CrawledPage(
        source_url="https://example.com/docs",
        status_code=200,
        body=b"<html><h1>Docs</h1></html>",
        content_type="text/html; charset=utf-8",
        title="Docs",
        records=[{"title": "Docs"}],
    )

    pipeline.process_page(job.id, page)
    pipeline.process_page(job.id, page)

    saved = repository.get_job(job.id)
    files = sorted(path.name for path in storage_root.rglob("*") if path.is_file())
    assert saved.pages_crawled == 1
    assert saved.artifacts_uploaded == 2
    assert saved.records_written == 0
    assert files == ["data.json", "raw.html"]


def test_pipeline_preserves_downloaded_asset_filename(tmp_path):
    repository = CrawlRepository(str(tmp_path / "crawl.sqlite3"))
    request = CreateCrawlRequest(
        name="file-download",
        start_urls=["https://example.com/resources"],
        fields=[],
        asset_downloads={"enabled": True, "extensions": ["pdf"]},
        destinations={
            "local": {"enabled": True, "directory": "files"},
            "oss": {"enabled": False},
            "mysql": {"enabled": False},
        },
    )
    job = repository.create_job(request)
    storage_root = tmp_path / "storage"
    pipeline = CrawlOutputPipeline(
        settings=Settings(_env_file=None, crawl_local_storage_dir=storage_root),
        repository=repository,
        request=request,
    )

    pipeline.process_page(
        job.id,
        CrawledPage(
            source_url="https://example.com/files/guide.pdf",
            status_code=200,
            body=b"%PDF-test",
            content_type="application/pdf",
            title="guide.pdf",
            records=[{"file_name": "guide.pdf"}],
            resource_type="asset",
            filename="guide.pdf",
        ),
    )

    files = sorted(path.name for path in storage_root.rglob("*") if path.is_file())
    assert files == ["data.json", "guide.pdf"]


def test_repository_can_requeue_failed_job(tmp_path):
    repository = CrawlRepository(str(tmp_path / "crawl.sqlite3"))
    job = repository.create_job(make_request())
    repository.mark_failed(job.id, "network timeout")

    requeued = repository.requeue(job.id)

    assert requeued.status == "queued"
    assert requeued.error is None


def test_aliyun_oss_sink_builds_v2_put_object_request():
    requests = []

    class FakeClient:
        def put_object(self, request):
            requests.append(request)
            return type("Result", (), {"etag": "etag"})()

    sink = AliyunOssSink(
        settings=Settings(
            _env_file=None,
            oss_default_public_base_url="https://cdn.example",
        ),
        bucket_alias="default",
        client=FakeClient(),
        request_factory=lambda **values: values,
    )

    location = sink.put_bytes("crawl/path/data.json", b"{}", "application/json")

    assert requests == [
        {
            "bucket": "xuefangedufile",
            "key": "crawl/path/data.json",
            "body": b"{}",
            "content_type": "application/json",
        }
    ]
    assert location.uri == "oss://xuefangedufile/crawl/path/data.json"
    assert location.public_url == "https://cdn.example/crawl/path/data.json"
