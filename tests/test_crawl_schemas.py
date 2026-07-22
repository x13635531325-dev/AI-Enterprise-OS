import pytest
from pydantic import ValidationError

from app.schemas.crawls import CreateCrawlRequest


def valid_request(**overrides):
    values = {
        "name": "docs-crawl",
        "start_urls": ["https://example.com/docs"],
        "fields": [{"name": "title", "selector": "h1::text"}],
        "destinations": {
            "oss": {"enabled": True},
            "mysql": {"enabled": True},
        },
    }
    values.update(overrides)
    return CreateCrawlRequest(**values)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1/private",
        "http://10.0.0.2/internal",
        "file:///etc/passwd",
    ],
)
def test_crawl_request_rejects_unsafe_start_urls(url):
    with pytest.raises(ValidationError):
        valid_request(start_urls=[url])


def test_crawl_request_requires_at_least_one_destination():
    with pytest.raises(ValidationError):
        valid_request(
            destinations={
                "local": {"enabled": False},
                "oss": {"enabled": False},
                "mysql": {"enabled": False},
            }
        )


@pytest.mark.parametrize("directory", ["../outside", "crawls/../../outside", "C:/temp"])
def test_crawl_request_rejects_unsafe_local_directory(directory):
    with pytest.raises(ValidationError):
        valid_request(
            destinations={
                "local": {"enabled": True, "directory": directory},
                "oss": {"enabled": False},
                "mysql": {"enabled": False},
            }
        )


def test_crawl_request_accepts_local_only_destination():
    request = valid_request(
        destinations={
            "local": {"enabled": True, "directory": "customer-a/docs"},
            "oss": {"enabled": False},
            "mysql": {"enabled": False},
        }
    )

    assert request.destinations.local.directory == "customer-a/docs"


def test_crawl_request_accepts_asset_download_without_extraction_fields():
    request = CreateCrawlRequest(
        name="download-files",
        start_urls=["https://example.com/resources"],
        fields=[],
        asset_downloads={
            "enabled": True,
            "extensions": ["PDF", ".docx", "pdf"],
        },
        destinations={
            "local": {"enabled": True},
            "oss": {"enabled": False},
            "mysql": {"enabled": False},
        },
    )

    assert request.asset_downloads.extensions == ["pdf", "docx"]


def test_crawl_request_requires_fields_when_asset_download_is_disabled():
    with pytest.raises(ValidationError):
        CreateCrawlRequest(
            name="empty-crawl",
            start_urls=["https://example.com"],
            fields=[],
            destinations={
                "local": {"enabled": True},
                "oss": {"enabled": False},
                "mysql": {"enabled": False},
            },
        )


def test_cloudflare_solver_requires_stealth_mode():
    with pytest.raises(ValidationError):
        valid_request(fetch_mode="http", solve_cloudflare=True)


def test_crawl_request_rejects_unsafe_mysql_table_name():
    with pytest.raises(ValidationError):
        valid_request(
            destinations={
                "oss": {"enabled": False},
                "mysql": {"enabled": True, "table": "records; DROP TABLE users"},
            }
        )
