from threading import Lock
from typing import Any

from app.core.config import settings
from app.schemas.knowledge import KnowledgeSearchResult


class RerankerService:
    def __init__(
        self,
        model_name: str | None = None,
        local_files_only: bool | None = None,
        enabled: bool | None = None,
    ):
        self.model_name = model_name or settings.reranker_model
        self.local_files_only = (
            settings.reranker_local_files_only
            if local_files_only is None
            else local_files_only
        )
        self.enabled = settings.reranker_enabled if enabled is None else enabled
        self._model: Any | None = None
        self._load_lock = Lock()

    def rerank(
        self,
        query: str,
        results: list[KnowledgeSearchResult],
        top_k: int,
    ) -> list[KnowledgeSearchResult]:
        if not self.enabled or not results:
            return results[:top_k]

        try:
            pairs = [(query, result.content) for result in results]
            scores = self._get_model().predict(pairs)
        except (OSError, RuntimeError):
            return results[:top_k]

        reranked_results = []

        for result, score in zip(results, scores):
            reranker_score = float(score)
            retrieval_sources = list(
                dict.fromkeys([*result.retrieval_sources, "reranker"])
            )
            reranked_results.append(
                result.model_copy(
                    update={
                        "score": reranker_score,
                        "reranker_score": reranker_score,
                        "retrieval_sources": retrieval_sources,
                    }
                )
            )

        return sorted(
            reranked_results,
            key=lambda result: result.reranker_score,
            reverse=True,
        )[:top_k]

    def _get_model(self):
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_name,
                    local_files_only=self.local_files_only,
                )

        return self._model
