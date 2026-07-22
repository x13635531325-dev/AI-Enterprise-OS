import ipaddress
import re
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


CrawlStatus = Literal["queued", "running", "completed", "paused", "failed"]
FetchMode = Literal["http", "dynamic", "stealth"]
SelectorType = Literal["css", "xpath"]
BucketAlias = Literal["default", "content", "review"]

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class ExtractionField(BaseModel):
    name: str
    selector: str = Field(min_length=1, max_length=500)
    selector_type: SelectorType = "css"
    multiple: bool = False
    required: bool = False
    default: str | list[str] | None = None
    adaptive: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError(
                "Field names must start with a letter and contain only letters, "
                "numbers, and underscores."
            )
        return value


class AssetDownloadConfig(BaseModel):
    enabled: bool = False
    selector: str = Field(default="a[href]", min_length=1, max_length=500)
    url_attributes: list[Literal["href", "src", "data-src"]] = Field(
        default_factory=lambda: ["href"],
        min_length=1,
        max_length=3,
    )
    description: str | None = Field(default=None, max_length=500)
    extensions: list[str] = Field(
        default_factory=lambda: [
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "csv",
            "ppt",
            "pptx",
            "zip",
            "rar",
            "7z",
            "txt",
        ],
        min_length=1,
        max_length=50,
    )
    max_assets: int = Field(default=200, ge=1, le=5_000)
    max_asset_bytes: int = Field(default=100 * 1024 * 1024, ge=1, le=1024**3)

    @field_validator("extensions")
    @classmethod
    def validate_extensions(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            extension = value.strip().lower().lstrip(".")
            if not re.fullmatch(r"[a-z0-9]{1,10}", extension):
                raise ValueError(f"Invalid asset extension: {value}")
            normalized.append(extension)
        return list(dict.fromkeys(normalized))

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None


class OssDestination(BaseModel):
    enabled: bool = True
    required: bool = True
    bucket_alias: BucketAlias = "default"
    prefix: str = Field(default="ai-enterprise-os/crawls", max_length=512)
    upload_html: bool = True
    upload_json: bool = True

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        normalized = value.strip().strip("/")
        if ".." in normalized.split("/"):
            raise ValueError("OSS prefix cannot contain parent-directory segments.")
        return normalized

    @model_validator(mode="after")
    def require_an_artifact_type(self):
        if self.enabled and not (self.upload_html or self.upload_json):
            raise ValueError("An enabled OSS destination must upload HTML or JSON.")
        return self


class MysqlDestination(BaseModel):
    enabled: bool = True
    required: bool = True
    table: str = "ai_crawl_records"

    @field_validator("table")
    @classmethod
    def validate_table(cls, value: str) -> str:
        if not _IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("MySQL table must be a safe SQL identifier.")
        return value


class LocalDestination(BaseModel):
    enabled: bool = False
    required: bool = True
    directory: str = Field(default="crawls", max_length=512)
    save_html: bool = True
    save_json: bool = True

    @field_validator("directory")
    @classmethod
    def validate_directory(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/").strip("/")
        path = PurePosixPath(normalized)
        if ":" in normalized or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError(
                "Local directory must be a safe relative path below the configured root."
            )
        return normalized

    @model_validator(mode="after")
    def require_an_artifact_type(self):
        if self.enabled and not (self.save_html or self.save_json):
            raise ValueError("An enabled local destination must save HTML or JSON.")
        return self


class CrawlDestinations(BaseModel):
    local: LocalDestination = Field(default_factory=LocalDestination)
    oss: OssDestination = Field(default_factory=OssDestination)
    mysql: MysqlDestination = Field(default_factory=MysqlDestination)

    @model_validator(mode="after")
    def require_enabled_destination(self):
        if not self.local.enabled and not self.oss.enabled and not self.mysql.enabled:
            raise ValueError("At least one crawl destination must be enabled.")
        return self


class CreateCrawlRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_urls: list[str] = Field(min_length=1, max_length=100)
    allowed_domains: list[str] = Field(default_factory=list, max_length=100)
    item_selector: str | None = Field(default=None, max_length=500)
    item_selector_type: SelectorType = "css"
    fields: list[ExtractionField] = Field(default_factory=list, max_length=100)
    follow_selector: str | None = Field(default=None, max_length=500)
    allow_url_patterns: list[str] = Field(default_factory=list, max_length=50)
    deny_url_patterns: list[str] = Field(default_factory=list, max_length=50)
    fetch_mode: FetchMode = "http"
    max_pages: int = Field(default=100, ge=1, le=10_000)
    concurrent_requests: int = Field(default=4, ge=1, le=64)
    concurrent_requests_per_domain: int = Field(default=2, ge=1, le=32)
    download_delay_seconds: float = Field(default=0.5, ge=0, le=60)
    request_timeout_seconds: int = Field(default=30, ge=5, le=300)
    robots_txt_obey: bool = True
    headless: bool = True
    network_idle: bool = False
    solve_cloudflare: bool = False
    asset_downloads: AssetDownloadConfig = Field(default_factory=AssetDownloadConfig)
    destinations: CrawlDestinations = Field(default_factory=CrawlDestinations)

    @field_validator("start_urls")
    @classmethod
    def validate_start_urls(cls, values: list[str]) -> list[str]:
        return [_validate_public_http_url(value) for value in values]

    @field_validator("allowed_domains")
    @classmethod
    def validate_allowed_domains(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            domain = value.strip().lower().rstrip(".")
            if not domain or "/" in domain or ":" in domain:
                raise ValueError(f"Invalid allowed domain: {value}")
            normalized.append(domain)
        return list(dict.fromkeys(normalized))

    @field_validator("allow_url_patterns", "deny_url_patterns")
    @classmethod
    def validate_url_patterns(cls, values: list[str]) -> list[str]:
        for value in values:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(f"Invalid URL regex '{value}': {exc}") from exc
        return values

    @model_validator(mode="after")
    def validate_fields_and_mode(self):
        field_names = [field.name for field in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("Extraction field names must be unique.")
        if self.solve_cloudflare and self.fetch_mode != "stealth":
            raise ValueError("Cloudflare solving requires stealth fetch mode.")
        if len(self.start_urls) > self.max_pages:
            raise ValueError("max_pages cannot be smaller than the number of start URLs.")
        if not self.fields and not self.asset_downloads.enabled:
            raise ValueError(
                "At least one extraction field or asset download must be enabled."
            )
        return self


class CrawlJobResponse(BaseModel):
    id: str
    name: str
    status: CrawlStatus
    request: CreateCrawlRequest
    pages_crawled: int = 0
    records_written: int = 0
    artifacts_uploaded: int = 0
    stats: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class CrawlDestinationStatus(BaseModel):
    name: Literal["local", "oss", "mysql"]
    configured: bool
    detail: str


class CrawlCapabilitiesResponse(BaseModel):
    scrapling_version: str
    destinations: list[CrawlDestinationStatus]
    fetch_modes: list[FetchMode]
    bucket_aliases: dict[str, str]


def _validate_public_http_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Crawl URLs must use http or https.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials are not allowed in crawl URLs.")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Localhost crawl targets are disabled.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("Private, loopback, and link-local crawl targets are disabled.")
    return normalized
