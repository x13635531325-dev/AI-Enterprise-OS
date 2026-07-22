import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.runs import new_id
from app.schemas.site_crawlers import (
    CreateSiteCrawlerTaskRequest,
    SiteCrawlerLogResponse,
    SiteCrawlerTaskResponse,
)
from app.storage.database import default_db_path, utc_now_iso


class SiteCrawlerRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or default_db_path()
        self._ensure_schema()

    def create_task(
        self, request: CreateSiteCrawlerTaskRequest
    ) -> SiteCrawlerTaskResponse:
        task_id = new_id("spider")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO site_crawler_tasks (
                    id, adapter_id, action, status, request_json,
                    max_attempts, result_json, created_at
                )
                VALUES (?, ?, ?, 'queued', ?, ?, '{}', ?)
                """,
                (
                    task_id,
                    request.adapter_id,
                    request.action,
                    request.model_dump_json(),
                    request.max_attempts,
                    utc_now_iso(),
                ),
            )
            connection.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> SiteCrawlerTaskResponse | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM site_crawler_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return self._build_task(row) if row else None

    def list_tasks(self, limit: int = 100) -> list[SiteCrawlerTaskResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM site_crawler_tasks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._build_task(row) for row in rows]

    def mark_running(self, task_id: str, process_id: int, attempt: int) -> None:
        self._update(
            task_id,
            status="running",
            process_id=process_id,
            attempts=attempt,
            started_at=utc_now_iso(),
            completed_at=None,
            retry_at=None,
            error_code=None,
            error=None,
        )

    def mark_retrying(
        self,
        task_id: str,
        error_code: str,
        error: str,
        retry_at: str,
    ) -> None:
        self._update(
            task_id,
            status="retrying",
            process_id=None,
            error_code=error_code,
            error=error[:4000],
            retry_at=retry_at,
        )

    def mark_completed(self, task_id: str, result: dict[str, Any]) -> None:
        self._update(
            task_id,
            status="completed",
            process_id=None,
            result_json=json.dumps(result, ensure_ascii=False),
            error_code=None,
            error=None,
            retry_at=None,
            completed_at=utc_now_iso(),
        )

    def mark_paused(self, task_id: str, error_code: str, error: str) -> None:
        self._update(
            task_id,
            status="paused",
            process_id=None,
            error_code=error_code,
            error=error[:4000],
            retry_at=None,
            completed_at=utc_now_iso(),
        )

    def mark_failed(self, task_id: str, error_code: str, error: str) -> None:
        self._update(
            task_id,
            status="failed",
            process_id=None,
            error_code=error_code,
            error=error[:4000],
            retry_at=None,
            completed_at=utc_now_iso(),
        )

    def mark_cancelled(self, task_id: str) -> None:
        self._update(
            task_id,
            status="cancelled",
            process_id=None,
            error_code="cancelled_by_user",
            error="Task was cancelled by the user.",
            retry_at=None,
            completed_at=utc_now_iso(),
        )

    def requeue(self, task_id: str) -> SiteCrawlerTaskResponse | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE site_crawler_tasks
                SET status = 'queued', attempts = 0, process_id = NULL,
                    error_code = NULL, error = NULL, retry_at = NULL,
                    completed_at = NULL
                WHERE id = ? AND status IN ('paused', 'failed', 'cancelled')
                """,
                (task_id,),
            )
            connection.commit()
        return self.get_task(task_id)

    def recover_interrupted_tasks(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE site_crawler_tasks
                SET status = 'paused', process_id = NULL,
                    error_code = 'backend_restarted',
                    error = 'Backend restarted while the crawler process was active.',
                    completed_at = ?
                WHERE status IN ('running', 'retrying')
                """,
                (utc_now_iso(),),
            )
            connection.commit()
        return cursor.rowcount

    def append_log(
        self,
        task_id: str,
        message: str,
        level: str = "info",
    ) -> None:
        normalized_level = level if level in {"info", "warning", "error"} else "info"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO site_crawler_logs (task_id, level, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, normalized_level, message[:8000], utc_now_iso()),
            )
            connection.commit()

    def list_logs(
        self,
        task_id: str,
        after_id: int = 0,
        limit: int = 500,
    ) -> list[SiteCrawlerLogResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM site_crawler_logs
                WHERE task_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (task_id, after_id, limit),
            ).fetchall()
        return [SiteCrawlerLogResponse(**dict(row)) for row in rows]

    def _update(self, task_id: str, **values: Any) -> None:
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE site_crawler_tasks SET {assignments} WHERE id = ?",
                (*values.values(), task_id),
            )
            connection.commit()

    def _ensure_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS site_crawler_tasks (
                    id TEXT PRIMARY KEY,
                    adapter_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    process_id INTEGER,
                    result_json TEXT NOT NULL DEFAULT '{}',
                    error_code TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    retry_at TEXT
                );

                CREATE TABLE IF NOT EXISTS site_crawler_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES site_crawler_tasks(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_site_crawler_tasks_created_at
                ON site_crawler_tasks(created_at);

                CREATE INDEX IF NOT EXISTS idx_site_crawler_logs_task_id
                ON site_crawler_logs(task_id, id);
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
    def _build_task(row: sqlite3.Row) -> SiteCrawlerTaskResponse:
        return SiteCrawlerTaskResponse(
            id=row["id"],
            adapter_id=row["adapter_id"],
            action=row["action"],
            status=row["status"],
            request=CreateSiteCrawlerTaskRequest.model_validate_json(
                row["request_json"]
            ),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            process_id=row["process_id"],
            result=json.loads(row["result_json"]),
            error_code=row["error_code"],
            error=row["error"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            retry_at=row["retry_at"],
        )


def retry_at_after(seconds: float) -> str:
    timestamp = datetime.now(timezone.utc).timestamp() + seconds
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
