from threading import Lock
from typing import Any

import numpy as np

from app.core.config import settings


QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class EmbeddingService:
    def __init__(
        self,
        model_name: str | None = None,
        local_files_only: bool | None = None,
    ):
        self.model_name = model_name or settings.embedding_model
        self.local_files_only = (
            settings.embedding_local_files_only
            if local_files_only is None
            else local_files_only
        )
        self._model: Any | None = None
        self._load_lock = Lock()

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self._get_model().encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return _to_float_lists(embeddings)

    def encode_query(self, query: str) -> list[float]:
        embedding = self._get_model().encode(
            [f"{QUERY_INSTRUCTION}{query}"],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return np.asarray(embedding, dtype=np.float32).tolist()

    def _get_model(self):
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    self.model_name,
                    local_files_only=self.local_files_only,
                )

        return self._model


def _to_float_lists(embeddings) -> list[list[float]]:
    array = np.asarray(embeddings, dtype=np.float32)
    return [embedding.tolist() for embedding in array]
