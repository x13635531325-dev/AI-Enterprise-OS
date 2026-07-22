import hashlib
import ipaddress
import re
from collections.abc import Callable
from email.message import Message
from pathlib import Path, PurePath
from typing import Any
from urllib.parse import unquote, urlparse

import anyio

from app.crawling.extractor import extract_page
from app.crawling.models import CrawledPage
from app.schemas.crawls import CreateCrawlRequest


def build_scrapling_spider(
    job_id: str,
    request: CreateCrawlRequest,
    item_handler: Callable[[CrawledPage], None],
    checkpoint_dir: Path,
):
    from scrapling.fetchers import (
        AsyncDynamicSession,
        AsyncStealthySession,
        FetcherSession,
    )
    from scrapling.spiders import Request, Spider

    allow_patterns = [re.compile(pattern) for pattern in request.allow_url_patterns]
    deny_patterns = [re.compile(pattern) for pattern in request.deny_url_patterns]
    adaptive_enabled = any(field.adaptive for field in request.fields)
    selector_config = {
        "adaptive": adaptive_enabled,
        "storage_args": {
            "storage_file": str(checkpoint_dir / "adaptive_elements.sqlite3")
        },
    }
    allowed_domains = set(request.allowed_domains)
    allowed_domains.update(
        urlparse(url).hostname.lower() for url in request.start_urls
    )
    asset_description_terms = _description_terms(
        request.asset_downloads.description
    )

    class ConfiguredScraplingSpider(Spider):
        name = f"enterprise_{_safe_name(request.name)}_{job_id[-8:]}"
        start_urls = request.start_urls
        concurrent_requests = request.concurrent_requests
        concurrent_requests_per_domain = request.concurrent_requests_per_domain
        download_delay = request.download_delay_seconds
        robots_txt_obey = request.robots_txt_obey

        def __init__(self):
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            super().__init__(crawldir=checkpoint_dir, interval=60.0)
            self.allowed_domains = allowed_domains
            self._scheduled_count = len(self.start_urls)
            self._asset_scheduled_count = 0
            self._scheduled_assets: set[str] = set()
            self.delivery_errors: list[str] = []

        def configure_sessions(self, manager):
            if request.fetch_mode == "http":
                session = FetcherSession(
                    impersonate="chrome",
                    stealthy_headers=True,
                    timeout=request.request_timeout_seconds,
                    retries=3,
                    retry_delay=1,
                    selector_config=selector_config,
                )
            elif request.fetch_mode == "dynamic":
                session = AsyncDynamicSession(
                    headless=request.headless,
                    network_idle=request.network_idle,
                    timeout=request.request_timeout_seconds * 1000,
                    max_pages=min(request.concurrent_requests, 8),
                    disable_resources=True,
                    retries=3,
                    retry_delay=1,
                    selector_config=selector_config,
                )
            else:
                session = AsyncStealthySession(
                    headless=request.headless,
                    network_idle=request.network_idle,
                    solve_cloudflare=request.solve_cloudflare,
                    timeout=request.request_timeout_seconds * 1000,
                    max_pages=min(request.concurrent_requests, 8),
                    disable_resources=True,
                    block_ads=True,
                    retries=3,
                    retry_delay=1,
                    selector_config=selector_config,
                )
            manager.add("default", session, default=True)

        async def start_requests(self):
            for url in self.start_urls:
                yield Request(url, sid="default", callback=self.parse)

        async def parse(self, response):
            page = extract_page(response, request)
            yield {
                "source_url": page.source_url,
                "status_code": page.status_code,
                "body": page.body,
                "content_type": page.content_type,
                "title": page.title,
                "records": page.records,
                "resource_type": page.resource_type,
                "filename": page.filename,
            }

            if request.asset_downloads.enabled:
                for raw_url, searchable_text in _asset_candidates(
                    response,
                    request.asset_downloads.selector,
                    request.asset_downloads.url_attributes,
                ):
                    if self._asset_scheduled_count >= request.asset_downloads.max_assets:
                        break
                    if asset_description_terms and not _asset_matches_description(
                        searchable_text,
                        asset_description_terms,
                    ):
                        continue
                    target_url = response.urljoin(str(raw_url).strip())
                    if not _asset_url_allowed(
                        target_url,
                        allowed_domains,
                        request.asset_downloads.extensions,
                    ):
                        continue
                    if target_url in self._scheduled_assets:
                        continue
                    self._scheduled_assets.add(target_url)
                    self._asset_scheduled_count += 1
                    yield Request(target_url, sid="default", callback=self.parse_asset)

            if not request.follow_selector:
                return
            for raw_url in response.css(request.follow_selector).getall():
                if self._scheduled_count >= request.max_pages:
                    break
                target_url = response.urljoin(str(raw_url).strip())
                if not _url_allowed(target_url, allow_patterns, deny_patterns):
                    continue
                self._scheduled_count += 1
                yield response.follow(target_url, sid="default", callback=self.parse)

        async def parse_asset(self, response):
            if int(response.status) >= 400:
                return
            body = response.body
            if isinstance(body, str):
                body = body.encode(getattr(response, "encoding", "utf-8"))
            body = bytes(body)
            if len(body) > request.asset_downloads.max_asset_bytes:
                return

            headers = getattr(response, "headers", {}) or {}
            content_type = (
                _header_value(headers, "content-type")
                or "application/octet-stream"
            )
            if content_type.split(";", 1)[0].strip().lower() == "text/html":
                return
            filename = _asset_filename(str(response.url), headers)
            yield {
                "source_url": str(response.url),
                "status_code": int(response.status),
                "body": body,
                "content_type": content_type,
                "title": filename,
                "records": [
                    {
                        "file_name": filename,
                        "file_url": str(response.url),
                        "content_type": content_type,
                        "size_bytes": len(body),
                    }
                ],
                "resource_type": "asset",
                "filename": filename,
            }

        async def on_scraped_item(self, item: dict[str, Any]):
            page = CrawledPage(**item)
            try:
                await anyio.to_thread.run_sync(item_handler, page)
            except Exception as exc:
                self.delivery_errors.append(f"{type(exc).__name__}: {exc}")
                raise
            return {
                "source_url": page.source_url,
                "status_code": page.status_code,
                "record_count": len(page.records),
            }

    return ConfiguredScraplingSpider()


def _url_allowed(
    url: str,
    allow_patterns: list[re.Pattern],
    deny_patterns: list[re.Pattern],
) -> bool:
    if any(pattern.search(url) for pattern in deny_patterns):
        return False
    return not allow_patterns or any(pattern.search(url) for pattern in allow_patterns)


def _asset_url_allowed(
    url: str,
    allowed_domains: set[str],
    extensions: list[str],
) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname not in allowed_domains:
        return False
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and not address.is_global:
        return False
    extension = PurePath(unquote(parsed.path)).suffix.lower().lstrip(".")
    return extension in extensions


def _asset_candidates(
    response: Any,
    selector: str,
    url_attributes: list[str],
) -> list[tuple[str, str]]:
    selected = response.css(selector)
    candidates = []
    for node in selected:
        urls = []
        for attribute in url_attributes:
            urls.extend(
                str(value).strip()
                for value in node.css(f"::attr({attribute})").getall()
                if str(value).strip()
            )
        if not urls:
            continue
        text_parts = [
            str(value).strip()
            for value in node.css("::text").getall()
            if str(value).strip()
        ]
        for attribute in ("alt", "title", "aria-label"):
            text_parts.extend(
                str(value).strip()
                for value in node.css(f"::attr({attribute})").getall()
                if str(value).strip()
            )
        searchable_text = " ".join([*text_parts, *urls])
        candidates.extend((url, searchable_text) for url in urls)

    if candidates:
        return candidates
    return [
        (str(value).strip(), str(value).strip())
        for value in selected.getall()
        if str(value).strip()
    ]


def _description_terms(description: str | None) -> list[str]:
    if not description:
        return []
    text = unquote(description).lower()
    text = re.sub(
        r"(?:请|帮我|我想要|需要|只要|仅|只)(?:爬取|爬|抓取|下载|采集)?",
        " ",
        text,
    )
    text = re.sub(r"(?:爬取|抓取|下载|采集)", " ", text)
    text = re.sub(r"(?:网页|网站|文件|资料|内容|相关)", " ", text)
    segments = [
        segment
        for segment in re.split(r"[\s,，、;；。的和与及且]+", text)
        if segment
    ]

    nouns = ("试卷", "通知", "报告", "名单", "教材", "课件", "答案", "图片", "照片")
    terms = []
    for segment in segments:
        remainder = segment
        for noun in nouns:
            if noun in remainder:
                terms.append(noun)
                remainder = remainder.replace(noun, " ")
        terms.extend(part for part in remainder.split() if len(part) >= 2)
    return list(dict.fromkeys(terms))


def _asset_matches_description(searchable_text: str, terms: list[str]) -> bool:
    normalized = unquote(searchable_text).lower()
    return all(term in normalized for term in terms)


def _asset_filename(url: str, headers: Any) -> str:
    disposition = _header_value(headers, "content-disposition")
    filename = None
    if disposition:
        message = Message()
        message["content-disposition"] = disposition
        filename = message.get_filename()
    if not filename:
        filename = PurePath(unquote(urlparse(url).path)).name
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename or "").strip(" .")
    if not filename:
        filename = f"asset-{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}"
    return filename[:180]


def _header_value(headers: Any, name: str) -> str | None:
    for key, value in dict(headers).items():
        key_text = key.decode("latin-1") if isinstance(key, bytes) else str(key)
        if key_text.lower() == name:
            if isinstance(value, bytes):
                return value.decode("latin-1")
            return str(value)
    return None


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()
    return normalized[:40] or "crawl"
