import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class MysqlRecordSink:
    def __init__(
        self,
        settings: Settings,
        table: str,
        connection_factory: Callable[[], Any] | None = None,
    ):
        if not _SAFE_IDENTIFIER.fullmatch(table):
            raise ValueError("Unsafe MySQL table name.")
        self.settings = settings
        self.table = table
        self._connection_factory = connection_factory

    def write_records(
        self,
        job_id: str,
        page_id: str,
        source_url: str,
        page_content_hash: str,
        records: list[dict[str, Any]],
        artifact_uri: str | None,
    ) -> int:
        if not records:
            return 0
        connection = self._connect()
        try:
            self._ensure_schema(connection)
            scraped_at = datetime.now(timezone.utc).replace(tzinfo=None)
            rows = []
            for index, record in enumerate(records):
                data_json = json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                record_hash = hashlib.sha256(
                    f"{source_url}\0{data_json}".encode("utf-8")
                ).hexdigest()
                rows.append(
                    (
                        f"crawlrec_{record_hash[:24]}",
                        job_id,
                        page_id,
                        source_url,
                        index,
                        page_content_hash,
                        record_hash,
                        data_json,
                        artifact_uri,
                        scraped_at,
                    )
                )

            with connection.cursor() as cursor:
                cursor.executemany(
                    f"""
                    INSERT INTO `{self.table}` (
                        id, crawl_job_id, page_id, source_url, record_index,
                        page_content_hash, record_hash, data_json,
                        artifact_uri, scraped_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        data_json = VALUES(data_json),
                        artifact_uri = VALUES(artifact_uri),
                        scraped_at = VALUES(scraped_at),
                        updated_at = CURRENT_TIMESTAMP(6)
                    """,
                    rows,
                )
            connection.commit()
            return len(rows)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_schema(self, connection: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{self.table}` (
                    id VARCHAR(40) PRIMARY KEY,
                    crawl_job_id VARCHAR(40) NOT NULL,
                    page_id VARCHAR(40) NOT NULL,
                    source_url TEXT NOT NULL,
                    record_index INT NOT NULL,
                    page_content_hash CHAR(64) NOT NULL,
                    record_hash CHAR(64) NOT NULL,
                    data_json JSON NOT NULL,
                    artifact_uri TEXT NULL,
                    scraped_at DATETIME(6) NOT NULL,
                    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                        ON UPDATE CURRENT_TIMESTAMP(6),
                    UNIQUE KEY uq_crawl_job_record (crawl_job_id, record_hash),
                    KEY idx_crawl_job_id (crawl_job_id),
                    KEY idx_page_id (page_id),
                    KEY idx_page_content_hash (page_content_hash)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self.settings.mysql_is_configured:
            raise RuntimeError("MySQL destination is not configured.")

        import pymysql

        ssl = None
        if self.settings.mysql_ssl_ca:
            ssl = {"ca": str(self.settings.mysql_ssl_ca)}
        return pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password.get_secret_value(),
            database=self.settings.mysql_database,
            charset="utf8mb4",
            connect_timeout=self.settings.mysql_connect_timeout_seconds,
            autocommit=False,
            ssl=ssl,
        )
