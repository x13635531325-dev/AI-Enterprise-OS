import json
import sqlite3
from pathlib import Path
from typing import Any

from app.schemas.crawls import CreateCrawlRequest, CrawlJobResponse
from app.schemas.runs import new_id
from app.storage.database import default_db_path, utc_now_iso


class CrawlRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or default_db_path()
        self._ensure_schema()

    def create_job(self, request: CreateCrawlRequest) -> CrawlJobResponse:
        job_id = new_id("crawl")
        created_at = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO crawl_jobs (
                    id, name, status, request_json, stats_json, created_at
                )
                VALUES (?, ?, 'queued', ?, '{}', ?)
                """,
                (
                    job_id,
                    request.name,
                    request.model_dump_json(),
                    created_at,
                ),
            )
            connection.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> CrawlJobResponse | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM crawl_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return self._build_job(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[CrawlJobResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM crawl_jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._build_job(row) for row in rows]

    def mark_running(self, job_id: str) -> None:
        self._update_job(
            job_id,
            status="running",
            started_at=utc_now_iso(),
            completed_at=None,
            error=None,
        )

    def mark_completed(self, job_id: str, stats: dict[str, Any]) -> None:
        self._update_job(
            job_id,
            status="completed",
            stats_json=json.dumps(stats, ensure_ascii=False),
            completed_at=utc_now_iso(),
            error=None,
        )

    def mark_paused(self, job_id: str, stats: dict[str, Any]) -> None:
        self._update_job(
            job_id,
            status="paused",
            stats_json=json.dumps(stats, ensure_ascii=False),
            completed_at=utc_now_iso(),
        )

    def mark_failed(self, job_id: str, error: str) -> None:
        self._update_job(
            job_id,
            status="failed",
            error=error[:4000],
            completed_at=utc_now_iso(),
        )

    def requeue(self, job_id: str) -> CrawlJobResponse | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE crawl_jobs
                SET status = 'queued', error = NULL, completed_at = NULL
                WHERE id = ? AND status IN ('failed', 'paused')
                """,
                (job_id,),
            )
            connection.commit()
        return self.get_job(job_id)

    def recover_interrupted_jobs(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE crawl_jobs
                SET
                    status = 'paused',
                    error = 'Backend restarted while this crawl was running. Retry to resume from its Scrapling checkpoint.',
                    completed_at = ?
                WHERE status = 'running'
                """,
                (utc_now_iso(),),
            )
            connection.commit()
        return cursor.rowcount

    def save_page(
        self,
        job_id: str,
        source_url: str,
        status_code: int,
        content_hash: str,
        records: list[dict[str, Any]],
    ) -> tuple[str, bool]:
        page_id = new_id("page")
        created_at = utc_now_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO crawl_pages (
                    id, job_id, source_url, status_code, content_hash,
                    records_json, record_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page_id,
                    job_id,
                    source_url,
                    status_code,
                    content_hash,
                    json.dumps(records, ensure_ascii=False),
                    len(records),
                    created_at,
                ),
            )
            created = cursor.rowcount == 1
            if created:
                connection.execute(
                    """
                    UPDATE crawl_jobs
                    SET pages_crawled = pages_crawled + 1
                    WHERE id = ?
                    """,
                    (job_id,),
                )
            else:
                row = connection.execute(
                    """
                    SELECT id FROM crawl_pages
                    WHERE job_id = ? AND source_url = ? AND content_hash = ?
                    """,
                    (job_id, source_url, content_hash),
                ).fetchone()
                page_id = row["id"]
            connection.commit()
        return page_id, created

    def delivery_succeeded(self, page_id: str, destination: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status FROM crawl_deliveries
                WHERE page_id = ? AND destination = ?
                """,
                (page_id, destination),
            ).fetchone()
        return bool(row and row["status"] == "completed")

    def record_delivery(
        self,
        job_id: str,
        page_id: str,
        destination: str,
        status: str,
        item_count: int = 0,
        uri: str | None = None,
        error: str | None = None,
    ) -> bool:
        updated_at = utc_now_iso()
        with self._connect() as connection:
            previous = connection.execute(
                """
                SELECT status FROM crawl_deliveries
                WHERE page_id = ? AND destination = ?
                """,
                (page_id, destination),
            ).fetchone()
            newly_succeeded = status == "completed" and not (
                previous and previous["status"] == "completed"
            )
            connection.execute(
                """
                INSERT INTO crawl_deliveries (
                    page_id, destination, status, item_count, uri,
                    error, attempts, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(page_id, destination) DO UPDATE SET
                    status = excluded.status,
                    item_count = excluded.item_count,
                    uri = excluded.uri,
                    error = excluded.error,
                    attempts = crawl_deliveries.attempts + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    page_id,
                    destination,
                    status,
                    item_count,
                    uri,
                    error[:4000] if error else None,
                    updated_at,
                ),
            )
            if newly_succeeded:
                if destination.startswith(("oss:", "local:")):
                    connection.execute(
                        """
                        UPDATE crawl_jobs
                        SET artifacts_uploaded = artifacts_uploaded + ?
                        WHERE id = ?
                        """,
                        (item_count, job_id),
                    )
                elif destination == "mysql":
                    connection.execute(
                        """
                        UPDATE crawl_jobs
                        SET records_written = records_written + ?
                        WHERE id = ?
                        """,
                        (item_count, job_id),
                    )
            connection.commit()
        return newly_succeeded

    def update_page_artifact_uri(self, page_id: str, artifact_uri: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE crawl_pages SET artifact_uri = ? WHERE id = ?",
                (artifact_uri, page_id),
            )
            connection.commit()

    def get_page_artifact_uri(self, page_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT artifact_uri FROM crawl_pages WHERE id = ?",
                (page_id,),
            ).fetchone()
        return row["artifact_uri"] if row else None

    def _update_job(self, job_id: str, **values: Any) -> None:
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE crawl_jobs SET {assignments} WHERE id = ?",
                (*values.values(), job_id),
            )
            connection.commit()

    def _ensure_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS crawl_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    pages_crawled INTEGER NOT NULL DEFAULT 0,
                    records_written INTEGER NOT NULL DEFAULT 0,
                    artifacts_uploaded INTEGER NOT NULL DEFAULT 0,
                    stats_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS crawl_pages (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    records_json TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    artifact_uri TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(job_id, source_url, content_hash),
                    FOREIGN KEY (job_id) REFERENCES crawl_jobs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS crawl_deliveries (
                    page_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    status TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    uri TEXT,
                    error TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (page_id, destination),
                    FOREIGN KEY (page_id) REFERENCES crawl_pages(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_at
                ON crawl_jobs(created_at);

                CREATE INDEX IF NOT EXISTS idx_crawl_pages_job_id
                ON crawl_pages(job_id);
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _build_job(row: sqlite3.Row) -> CrawlJobResponse:
        return CrawlJobResponse(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            request=CreateCrawlRequest.model_validate_json(row["request_json"]),
            pages_crawled=row["pages_crawled"],
            records_written=row["records_written"],
            artifacts_uploaded=row["artifacts_uploaded"],
            stats=json.loads(row["stats_json"]),
            error=row["error"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
