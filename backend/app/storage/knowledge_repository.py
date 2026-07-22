import json
import re
import sqlite3
from pathlib import Path

import numpy as np

from app.schemas.knowledge import DocumentResponse, KnowledgeSearchResult
from app.schemas.runs import new_id
from app.services.text_chunker import TextChunk
from app.storage.database import default_db_path, utc_now_iso


class KnowledgeRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or default_db_path()
        self._ensure_schema()

    def save_document(
        self,
        title: str,
        content: str,
        metadata: dict,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_model: str,
    ) -> DocumentResponse:
        if len(chunks) != len(embeddings):
            raise ValueError("Each knowledge chunk must have one embedding.")

        document_id = new_id("doc")
        created_at = utc_now_iso()

        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO documents (
                    id,
                    title,
                    content,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    title,
                    content,
                    json.dumps(metadata, ensure_ascii=False),
                    created_at,
                ),
            )

            for position, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = new_id("chunk")
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        id,
                        document_id,
                        position,
                        content,
                        start_offset,
                        end_offset,
                        embedding,
                        embedding_model
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        document_id,
                        position,
                        chunk.content,
                        chunk.start_offset,
                        chunk.end_offset,
                        sqlite3.Binary(_embedding_to_bytes(embedding)),
                        embedding_model,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks_fts (
                        chunk_id,
                        document_id,
                        content
                    )
                    VALUES (?, ?, ?)
                    """,
                    (chunk_id, document_id, chunk.content),
                )

            connection.commit()

        return DocumentResponse(
            id=document_id,
            title=title,
            content=content,
            metadata=metadata,
            chunk_count=len(chunks),
            created_at=created_at,
        )

    def list_documents(self) -> list[DocumentResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.*,
                    COUNT(c.id) AS chunk_count
                FROM documents AS d
                LEFT JOIN knowledge_chunks AS c
                    ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                """
            ).fetchall()

        return [
            DocumentResponse(
                id=row["id"],
                title=row["title"],
                content=row["content"],
                metadata=json.loads(row["metadata_json"]),
                chunk_count=row["chunk_count"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def search_lexical(
        self,
        query: str,
        top_k: int,
    ) -> list[KnowledgeSearchResult]:
        fts_query = _build_fts_query(query)

        with self._connect() as connection:
            if fts_query:
                rows = connection.execute(
                    """
                    SELECT
                        c.id AS chunk_id,
                        c.document_id,
                        d.title AS document_title,
                        c.content,
                        c.position,
                        bm25(knowledge_chunks_fts) AS rank
                    FROM knowledge_chunks_fts
                    JOIN knowledge_chunks AS c
                        ON c.id = knowledge_chunks_fts.chunk_id
                    JOIN documents AS d
                        ON d.id = c.document_id
                    WHERE knowledge_chunks_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?
                    """,
                    (fts_query, top_k),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        c.id AS chunk_id,
                        c.document_id,
                        d.title AS document_title,
                        c.content,
                        c.position,
                        -1.0 AS rank
                    FROM knowledge_chunks AS c
                    JOIN documents AS d
                        ON d.id = c.document_id
                    WHERE c.content LIKE ?
                    ORDER BY c.position ASC
                    LIMIT ?
                    """,
                    (f"%{query}%", top_k),
                ).fetchall()

        return [
            KnowledgeSearchResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_title=row["document_title"],
                content=row["content"],
                position=row["position"],
                score=round(-float(row["rank"]), 6),
                lexical_score=round(-float(row["rank"]), 6),
                retrieval_sources=["lexical"],
            )
            for row in rows
        ]

    def search_vector(
        self,
        query_embedding: list[float],
        embedding_model: str,
        top_k: int,
        min_similarity: float,
    ) -> list[KnowledgeSearchResult]:
        query_vector = np.asarray(query_embedding, dtype=np.float32)

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    d.title AS document_title,
                    c.content,
                    c.position,
                    c.embedding
                FROM knowledge_chunks AS c
                JOIN documents AS d
                    ON d.id = c.document_id
                WHERE c.embedding IS NOT NULL
                    AND c.embedding_model = ?
                """,
                (embedding_model,),
            ).fetchall()

        scored_results = []

        for row in rows:
            vector = np.frombuffer(row["embedding"], dtype=np.float32)

            if vector.shape != query_vector.shape:
                continue

            similarity = float(np.dot(query_vector, vector))

            if similarity < min_similarity:
                continue

            scored_results.append(
                KnowledgeSearchResult(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    document_title=row["document_title"],
                    content=row["content"],
                    position=row["position"],
                    score=similarity,
                    vector_score=similarity,
                    retrieval_sources=["vector"],
                )
            )

        return sorted(
            scored_results,
            key=lambda result: result.vector_score,
            reverse=True,
        )[:top_k]

    def list_chunks_for_reindex(
        self,
        embedding_model: str,
    ) -> list[tuple[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, content
                FROM knowledge_chunks
                WHERE embedding IS NULL
                    OR embedding_model IS NULL
                    OR embedding_model != ?
                ORDER BY document_id, position
                """,
                (embedding_model,),
            ).fetchall()

        return [(row["id"], row["content"]) for row in rows]

    def update_chunk_embeddings(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        embedding_model: str,
    ) -> None:
        if len(chunk_ids) != len(embeddings):
            raise ValueError("Each chunk ID must have one embedding.")

        with self._connect() as connection:
            connection.executemany(
                """
                UPDATE knowledge_chunks
                SET embedding = ?, embedding_model = ?
                WHERE id = ?
                """,
                [
                    (
                        sqlite3.Binary(_embedding_to_bytes(embedding)),
                        embedding_model,
                        chunk_id,
                    )
                    for chunk_id, embedding in zip(chunk_ids, embeddings)
                ],
            )
            connection.commit()

    def reset(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM knowledge_chunks_fts")
            connection.execute("DELETE FROM knowledge_chunks")
            connection.execute("DELETE FROM documents")
            connection.commit()

    def _ensure_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    embedding BLOB,
                    embedding_model TEXT,
                    FOREIGN KEY (document_id)
                        REFERENCES documents(id)
                        ON DELETE CASCADE
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts
                USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    content,
                    tokenize='trigram'
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document_id
                ON knowledge_chunks(document_id);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(knowledge_chunks)"
                ).fetchall()
            }

            if "embedding" not in columns:
                connection.execute(
                    "ALTER TABLE knowledge_chunks ADD COLUMN embedding BLOB"
                )

            if "embedding_model" not in columns:
                connection.execute(
                    "ALTER TABLE knowledge_chunks ADD COLUMN embedding_model TEXT"
                )

            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _build_fts_query(query: str) -> str:
    terms = []

    for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", query):
        if "\u4e00" <= token[0] <= "\u9fff":
            terms.extend(
                token[index : index + 3]
                for index in range(max(0, len(token) - 2))
            )
        elif len(token) >= 3:
            terms.append(token)

    unique_terms = list(dict.fromkeys(terms))[:16]
    return " OR ".join(
        f'"{term.replace(chr(34), chr(34) * 2)}"'
        for term in unique_terms
    )


def _embedding_to_bytes(embedding: list[float]) -> bytes:
    return np.asarray(embedding, dtype=np.float32).tobytes()
