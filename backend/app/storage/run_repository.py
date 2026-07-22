import json
import sqlite3
from pathlib import Path
from typing import Any

from app.schemas.runs import (
    CitationResponse,
    ModelCallResponse,
    RunListItemResponse,
    RunMetricsResponse,
    RunResponse,
    SpanResponse,
    StepResponse,
    ToolExecutionResponse,
    TraceResponse,
)
from app.storage.database import default_db_path, utc_now_iso


class RunRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or default_db_path()
        self._ensure_schema()

    def save_run(self, run: RunResponse) -> RunResponse:
        created_at = run.created_at or utc_now_iso()
        saved_run = run.model_copy(update={"created_at": created_at})

        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            self._delete_run_children(connection, saved_run.id)
            connection.execute(
                """
                INSERT OR REPLACE INTO runs (
                    id,
                    workflow_name,
                    input,
                    status,
                    output,
                    created_at,
                    metrics_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    saved_run.id,
                    saved_run.workflow_name,
                    saved_run.input,
                    saved_run.status,
                    saved_run.output,
                    saved_run.created_at,
                    _to_json(saved_run.metrics),
                ),
            )

            for citation in saved_run.citations:
                connection.execute(
                    """
                    INSERT INTO citations (
                        run_id,
                        position,
                        document_id,
                        document_title,
                        chunk_id,
                        excerpt
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        saved_run.id,
                        citation.index,
                        citation.document_id,
                        citation.document_title,
                        citation.chunk_id,
                        citation.excerpt,
                    ),
                )

            for index, step in enumerate(saved_run.steps):
                connection.execute(
                    """
                    INSERT INTO steps (
                        id,
                        run_id,
                        position,
                        name,
                        status,
                        output,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.id,
                        saved_run.id,
                        index,
                        step.name,
                        step.status,
                        step.output,
                        json.dumps(step.metadata),
                    ),
                )

            if saved_run.trace is not None:
                connection.execute(
                    """
                    INSERT INTO traces (id, run_id, status)
                    VALUES (?, ?, ?)
                    """,
                    (
                        saved_run.trace.id,
                        saved_run.id,
                        saved_run.trace.status,
                    ),
                )

                for span_index, span in enumerate(saved_run.trace.spans):
                    connection.execute(
                        """
                        INSERT INTO spans (
                            id,
                            trace_id,
                            position,
                            name,
                            status,
                            latency_ms,
                            output,
                            error,
                            metadata_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            span.id,
                            saved_run.trace.id,
                            span_index,
                            span.name,
                            span.status,
                            span.latency_ms,
                            span.output,
                            span.error,
                            json.dumps(span.metadata),
                        ),
                    )

                    for call_index, model_call in enumerate(span.model_calls):
                        connection.execute(
                            """
                            INSERT INTO model_calls (
                                id,
                                span_id,
                                position,
                                provider,
                                model,
                                task_type,
                                attempt,
                                status,
                                input_tokens,
                                output_tokens,
                                latency_ms,
                                cost_usd,
                                output,
                                circuit_state,
                                error_type,
                                retryable,
                                error
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                model_call.id,
                                span.id,
                                call_index,
                                model_call.provider,
                                model_call.model,
                                model_call.task_type,
                                model_call.attempt,
                                model_call.status,
                                model_call.input_tokens,
                                model_call.output_tokens,
                                model_call.latency_ms,
                                model_call.cost_usd,
                                model_call.output,
                                model_call.circuit_state,
                                model_call.error_type,
                                1 if model_call.retryable else 0,
                                model_call.error,
                            ),
                        )

                    for tool_index, tool_call in enumerate(span.tool_calls):
                        connection.execute(
                            """
                            INSERT INTO tool_calls (
                                id,
                                span_id,
                                position,
                                tool_name,
                                status,
                                arguments_json,
                                output,
                                error,
                                latency_ms
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                tool_call.tool_call_id,
                                span.id,
                                tool_index,
                                tool_call.tool_name,
                                tool_call.status,
                                json.dumps(tool_call.arguments),
                                tool_call.output,
                                tool_call.error,
                                tool_call.latency_ms,
                            ),
                        )

            connection.commit()

        return saved_run

    def get_run(self, run_id: str) -> RunResponse | None:
        with self._connect() as connection:
            run_row = connection.execute(
                """
                SELECT *
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

            if run_row is None:
                return None

            return self._build_run(connection, run_row)

    def list_runs(self, limit: int = 20) -> list[RunListItemResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            RunListItemResponse(
                id=row["id"],
                workflow_name=row["workflow_name"],
                input=row["input"],
                status=row["status"],
                output=row["output"],
                created_at=row["created_at"],
                metrics=RunMetricsResponse(**json.loads(row["metrics_json"])),
            )
            for row in rows
        ]

    def reset(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            for table_name in (
                "citations",
                "tool_calls",
                "model_calls",
                "spans",
                "traces",
                "steps",
                "runs",
            ):
                connection.execute(f"DELETE FROM {table_name}")

            connection.commit()

    def _build_run(self, connection: sqlite3.Connection, run_row: sqlite3.Row) -> RunResponse:
        steps = [
            StepResponse(
                id=row["id"],
                name=row["name"],
                status=row["status"],
                output=row["output"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in connection.execute(
                """
                SELECT *
                FROM steps
                WHERE run_id = ?
                ORDER BY position ASC
                """,
                (run_row["id"],),
            ).fetchall()
        ]

        trace = self._load_trace(connection, run_row["id"])
        citations = [
            CitationResponse(
                index=row["position"],
                document_id=row["document_id"],
                document_title=row["document_title"],
                chunk_id=row["chunk_id"],
                excerpt=row["excerpt"],
            )
            for row in connection.execute(
                """
                SELECT *
                FROM citations
                WHERE run_id = ?
                ORDER BY position ASC
                """,
                (run_row["id"],),
            ).fetchall()
        ]

        return RunResponse(
            id=run_row["id"],
            workflow_name=run_row["workflow_name"],
            input=run_row["input"],
            status=run_row["status"],
            output=run_row["output"],
            created_at=run_row["created_at"],
            steps=steps,
            trace=trace,
            citations=citations,
            metrics=RunMetricsResponse(**json.loads(run_row["metrics_json"])),
        )

    def _load_trace(self, connection: sqlite3.Connection, run_id: str) -> TraceResponse | None:
        trace_row = connection.execute(
            """
            SELECT *
            FROM traces
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

        if trace_row is None:
            return None

        spans = []
        span_rows = connection.execute(
            """
            SELECT *
            FROM spans
            WHERE trace_id = ?
            ORDER BY position ASC
            """,
            (trace_row["id"],),
        ).fetchall()

        for span_row in span_rows:
            model_calls = [
                ModelCallResponse(
                    id=row["id"],
                    provider=row["provider"],
                    model=row["model"],
                    task_type=row["task_type"],
                    attempt=row["attempt"],
                    status=row["status"],
                    input_tokens=row["input_tokens"],
                    output_tokens=row["output_tokens"],
                    latency_ms=row["latency_ms"],
                    cost_usd=row["cost_usd"],
                    output=row["output"],
                    circuit_state=row["circuit_state"],
                    error_type=row["error_type"],
                    retryable=bool(row["retryable"]),
                    error=row["error"],
                )
                for row in connection.execute(
                    """
                    SELECT *
                    FROM model_calls
                    WHERE span_id = ?
                    ORDER BY position ASC
                    """,
                    (span_row["id"],),
                ).fetchall()
            ]
            tool_calls = [
                ToolExecutionResponse(
                    tool_call_id=row["id"],
                    tool_name=row["tool_name"],
                    status=row["status"],
                    arguments=json.loads(row["arguments_json"]),
                    output=row["output"],
                    error=row["error"],
                    latency_ms=row["latency_ms"],
                )
                for row in connection.execute(
                    """
                    SELECT *
                    FROM tool_calls
                    WHERE span_id = ?
                    ORDER BY position ASC
                    """,
                    (span_row["id"],),
                ).fetchall()
            ]

            spans.append(
                SpanResponse(
                    id=span_row["id"],
                    name=span_row["name"],
                    status=span_row["status"],
                    latency_ms=span_row["latency_ms"],
                    output=span_row["output"],
                    error=span_row["error"],
                    model_calls=model_calls,
                    tool_calls=tool_calls,
                    metadata=json.loads(span_row["metadata_json"]),
                )
            )

        return TraceResponse(
            id=trace_row["id"],
            status=trace_row["status"],
            spans=spans,
        )

    def _ensure_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    input TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    created_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS citations (
                    run_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    document_id TEXT NOT NULL,
                    document_title TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    PRIMARY KEY (run_id, position),
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS traces (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS spans (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    output TEXT,
                    error TEXT,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS model_calls (
                    id TEXT PRIMARY KEY,
                    span_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    output TEXT,
                    circuit_state TEXT NOT NULL,
                    error_type TEXT,
                    retryable INTEGER NOT NULL,
                    error TEXT,
                    FOREIGN KEY (span_id) REFERENCES spans(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tool_calls (
                    id TEXT PRIMARY KEY,
                    span_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    latency_ms INTEGER NOT NULL,
                    FOREIGN KEY (span_id) REFERENCES spans(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_runs_created_at
                ON runs(created_at);

                CREATE INDEX IF NOT EXISTS idx_steps_run_id
                ON steps(run_id);

                CREATE INDEX IF NOT EXISTS idx_citations_run_id
                ON citations(run_id);

                CREATE INDEX IF NOT EXISTS idx_spans_trace_id
                ON spans(trace_id);

                CREATE INDEX IF NOT EXISTS idx_model_calls_span_id
                ON model_calls(span_id);

                CREATE INDEX IF NOT EXISTS idx_tool_calls_span_id
                ON tool_calls(span_id);
                """
            )
            connection.commit()

    def _delete_run_children(
        self,
        connection: sqlite3.Connection,
        run_id: str,
    ) -> None:
        connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _to_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump())

    return json.dumps(value)
