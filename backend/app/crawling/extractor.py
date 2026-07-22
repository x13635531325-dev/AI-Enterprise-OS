from typing import Any

from app.crawling.models import CrawledPage
from app.schemas.crawls import CreateCrawlRequest, ExtractionField


def extract_page(response: Any, request: CreateCrawlRequest) -> CrawledPage:
    records = []
    if request.fields:
        roots = _select(response, request.item_selector, request.item_selector_type)
        if not roots:
            roots = [response]

        for root in roots:
            record = _extract_record(root, request.fields)
            if record is not None:
                records.append(record)

    body = response.body
    if isinstance(body, str):
        body = body.encode(getattr(response, "encoding", "utf-8"))

    headers = getattr(response, "headers", {}) or {}
    content_type = _header_value(headers, "content-type") or "text/html; charset=utf-8"
    title_nodes = response.css("title::text")
    title = str(title_nodes.get()).strip() if title_nodes else ""

    return CrawledPage(
        source_url=str(response.url),
        status_code=int(response.status),
        body=bytes(body),
        content_type=content_type,
        title=title,
        records=records,
    )


def _extract_record(root: Any, fields: list[ExtractionField]) -> dict[str, Any] | None:
    record: dict[str, Any] = {}
    for field in fields:
        values = _extract_field(root, field)
        if not values:
            if field.required:
                return None
            record[field.name] = field.default
        elif field.multiple:
            record[field.name] = values
        else:
            record[field.name] = values[0]
    return record


def _extract_field(root: Any, field: ExtractionField) -> list[str]:
    kwargs = {}
    if field.selector_type == "css" and field.adaptive:
        kwargs = {
            "identifier": f"{getattr(root, 'url', '')}:{field.name}",
            "adaptive": True,
            "auto_save": True,
        }
    nodes = (
        root.css(field.selector, **kwargs)
        if field.selector_type == "css"
        else root.xpath(field.selector)
    )
    return [str(value).strip() for value in nodes.getall() if str(value).strip()]


def _select(root: Any, selector: str | None, selector_type: str) -> list[Any]:
    if not selector:
        return [root]
    selected = root.css(selector) if selector_type == "css" else root.xpath(selector)
    return list(selected)


def _header_value(headers: Any, name: str) -> str | None:
    for key, value in dict(headers).items():
        key_text = key.decode("latin-1") if isinstance(key, bytes) else str(key)
        if key_text.lower() == name:
            if isinstance(value, bytes):
                return value.decode("latin-1")
            return str(value)
    return None
