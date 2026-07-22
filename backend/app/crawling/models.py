from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CrawledPage:
    source_url: str
    status_code: int
    body: bytes
    content_type: str
    title: str
    records: list[dict[str, Any]] = field(default_factory=list)
    resource_type: str = "page"
    filename: str | None = None


@dataclass(slots=True)
class ArtifactLocation:
    uri: str
    public_url: str | None = None
    etag: str | None = None
