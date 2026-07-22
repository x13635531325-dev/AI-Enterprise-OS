import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from app.core.config import Settings
from app.crawling.models import CrawledPage
from app.crawling.sinks.aliyun_oss import AliyunOssSink
from app.crawling.sinks.local import LocalFileSink
from app.crawling.sinks.mysql import MysqlRecordSink
from app.schemas.crawls import CreateCrawlRequest
from app.storage.crawl_repository import CrawlRepository


class CrawlDeliveryError(RuntimeError):
    pass


class CrawlOutputPipeline:
    def __init__(
        self,
        settings: Settings,
        repository: CrawlRepository,
        request: CreateCrawlRequest,
        local_sink: LocalFileSink | None = None,
        oss_sink: AliyunOssSink | None = None,
        mysql_sink: MysqlRecordSink | None = None,
    ):
        self.settings = settings
        self.repository = repository
        self.request = request
        self.local_sink = local_sink
        self.oss_sink = oss_sink
        self.mysql_sink = mysql_sink

    def process_page(self, job_id: str, page: CrawledPage) -> None:
        content_hash = hashlib.sha256(page.body).hexdigest()
        page_id, _ = self.repository.save_page(
            job_id=job_id,
            source_url=page.source_url,
            status_code=page.status_code,
            content_hash=content_hash,
            records=page.records,
        )
        artifact_uri = self._deliver_local(job_id, page_id, content_hash, page)
        oss_artifact_uri = self._deliver_oss(job_id, page_id, content_hash, page)
        artifact_uri = oss_artifact_uri or artifact_uri
        if artifact_uri:
            self.repository.update_page_artifact_uri(page_id, artifact_uri)
        self._deliver_mysql(
            job_id,
            page_id,
            content_hash,
            page,
            artifact_uri,
        )

    def _deliver_local(
        self,
        job_id: str,
        page_id: str,
        content_hash: str,
        page: CrawledPage,
    ) -> str | None:
        destination = self.request.destinations.local
        if not destination.enabled:
            return None
        sink = self.local_sink or LocalFileSink(self.settings, destination.directory)
        base_key = _local_base_key(job_id, content_hash)
        locations = []
        failures = []
        existing_artifact_uri = self.repository.get_page_artifact_uri(page_id)

        artifacts = []
        if destination.save_html:
            artifacts.append(
                (
                    "local:raw",
                    f"{base_key}/{_raw_artifact_name(page)}",
                    page.body,
                    page.content_type,
                )
            )
        if destination.save_json:
            artifacts.append(
                (
                    "local:json",
                    f"{base_key}/data.json",
                    _page_json(page, content_hash),
                    "application/json; charset=utf-8",
                )
            )

        for delivery_name, object_key, data, content_type in artifacts:
            if self.repository.delivery_succeeded(page_id, delivery_name):
                continue
            try:
                location = _with_retry(
                    lambda object_key=object_key, data=data, content_type=content_type: (
                        sink.put_bytes(object_key, data, content_type)
                    )
                )
                self.repository.record_delivery(
                    job_id,
                    page_id,
                    delivery_name,
                    "completed",
                    item_count=1,
                    uri=location.uri,
                )
                self.repository.update_page_artifact_uri(page_id, location.uri)
                locations.append(location)
            except Exception as exc:
                self.repository.record_delivery(
                    job_id,
                    page_id,
                    delivery_name,
                    "failed",
                    error=str(exc),
                )
                failures.append(exc)

        if failures and destination.required:
            raise CrawlDeliveryError(
                f"Required local delivery failed: {failures[-1]}"
            )
        return locations[0].uri if locations else existing_artifact_uri

    def _deliver_oss(
        self,
        job_id: str,
        page_id: str,
        content_hash: str,
        page: CrawledPage,
    ) -> str | None:
        destination = self.request.destinations.oss
        if not destination.enabled:
            return None
        sink = self.oss_sink or AliyunOssSink(
            self.settings,
            destination.bucket_alias,
        )
        base_key = _object_base_key(
            destination.prefix,
            job_id,
            content_hash,
        )
        locations = []
        failures = []
        existing_artifact_uri = self.repository.get_page_artifact_uri(page_id)

        if destination.upload_html:
            delivery_name = "oss:raw"
            if not self.repository.delivery_succeeded(page_id, delivery_name):
                try:
                    location = _with_retry(
                        lambda: sink.put_bytes(
                            f"{base_key}/{_raw_artifact_name(page)}",
                            page.body,
                            page.content_type,
                        )
                    )
                    self.repository.record_delivery(
                        job_id,
                        page_id,
                        delivery_name,
                        "completed",
                        item_count=1,
                        uri=location.uri,
                    )
                    self.repository.update_page_artifact_uri(
                        page_id,
                        location.public_url or location.uri,
                    )
                    locations.append(location)
                except Exception as exc:
                    self.repository.record_delivery(
                        job_id,
                        page_id,
                        delivery_name,
                        "failed",
                        error=str(exc),
                    )
                    failures.append(exc)

        if destination.upload_json:
            delivery_name = "oss:json"
            if not self.repository.delivery_succeeded(page_id, delivery_name):
                payload = _page_json(page, content_hash)
                try:
                    location = _with_retry(
                        lambda: sink.put_bytes(
                            f"{base_key}/data.json",
                            payload,
                            "application/json; charset=utf-8",
                        )
                    )
                    self.repository.record_delivery(
                        job_id,
                        page_id,
                        delivery_name,
                        "completed",
                        item_count=1,
                        uri=location.uri,
                    )
                    self.repository.update_page_artifact_uri(
                        page_id,
                        location.public_url or location.uri,
                    )
                    locations.append(location)
                except Exception as exc:
                    self.repository.record_delivery(
                        job_id,
                        page_id,
                        delivery_name,
                        "failed",
                        error=str(exc),
                    )
                    failures.append(exc)

        if failures and destination.required:
            raise CrawlDeliveryError(f"Required OSS delivery failed: {failures[-1]}")
        if not locations:
            return existing_artifact_uri
        preferred = next(
            (location.public_url for location in locations if location.public_url),
            None,
        )
        return preferred or locations[0].uri

    def _deliver_mysql(
        self,
        job_id: str,
        page_id: str,
        content_hash: str,
        page: CrawledPage,
        artifact_uri: str | None,
    ) -> None:
        destination = self.request.destinations.mysql
        if not destination.enabled:
            return
        delivery_name = "mysql"
        if self.repository.delivery_succeeded(page_id, delivery_name):
            return
        sink = self.mysql_sink or MysqlRecordSink(
            self.settings,
            destination.table,
        )
        try:
            count = _with_retry(
                lambda: sink.write_records(
                    job_id=job_id,
                    page_id=page_id,
                    source_url=page.source_url,
                    page_content_hash=content_hash,
                    records=page.records,
                    artifact_uri=artifact_uri,
                )
            )
            self.repository.record_delivery(
                job_id,
                page_id,
                delivery_name,
                "completed",
                item_count=count,
            )
        except Exception as exc:
            self.repository.record_delivery(
                job_id,
                page_id,
                delivery_name,
                "failed",
                error=str(exc),
            )
            if destination.required:
                raise CrawlDeliveryError(f"Required MySQL delivery failed: {exc}") from exc


def _object_base_key(prefix: str, job_id: str, content_hash: str) -> str:
    date_path = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    return str(
        PurePosixPath(prefix)
        / date_path
        / job_id
        / content_hash[:2]
        / content_hash
    )


def _local_base_key(job_id: str, content_hash: str) -> str:
    date_path = datetime.now(timezone.utc).strftime("%Y%m%d")
    return str(PurePosixPath(date_path) / job_id / content_hash[:32])


def _page_json(page: CrawledPage, content_hash: str) -> bytes:
    return json.dumps(
        {
            "source_url": page.source_url,
            "status_code": page.status_code,
            "title": page.title,
            "content_hash": content_hash,
            "resource_type": page.resource_type,
            "file_name": page.filename,
            "records": page.records,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def _extension_for_content_type(content_type: str) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return {
        "text/html": ".html",
        "application/xhtml+xml": ".html",
        "application/json": ".json",
        "text/plain": ".txt",
        "application/pdf": ".pdf",
    }.get(media_type, ".bin")


def _raw_artifact_name(page: CrawledPage) -> str:
    if page.resource_type == "asset" and page.filename:
        filename = re.sub(r'[^A-Za-z0-9._()\-\u4e00-\u9fff]+', "_", page.filename)
        filename = filename.strip(" .")[:180]
        if filename:
            return filename
    return f"raw{_extension_for_content_type(page.content_type)}"


def _with_retry(operation: Any, attempts: int = 3) -> Any:
    last_error = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.25 * (2**attempt))
    raise last_error
