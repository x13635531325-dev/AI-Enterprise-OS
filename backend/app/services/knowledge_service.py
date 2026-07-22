from app.core.config import settings
from app.schemas.knowledge import (
    CreateDocumentRequest,
    DocumentResponse,
    KnowledgeSearchResult,
    ReindexKnowledgeResponse,
    SearchKnowledgeRequest,
)
from app.services.embedding_service import EmbeddingService
from app.services.reranker_service import RerankerService
from app.services.text_chunker import TextChunker
from app.storage.knowledge_repository import KnowledgeRepository


class KnowledgeService:
    def __init__(self):
        self.repository = KnowledgeRepository()
        self.chunker = TextChunker()
        self.embedding_service = EmbeddingService()
        self.reranker_service = RerankerService()

    def create_document(
        self,
        request: CreateDocumentRequest,
    ) -> DocumentResponse:
        chunks = self.chunker.split(request.content)
        embeddings = self.embedding_service.encode_documents(
            [chunk.content for chunk in chunks]
        )
        return self.repository.save_document(
            title=request.title,
            content=request.content,
            metadata=request.metadata,
            chunks=chunks,
            embeddings=embeddings,
            embedding_model=self.embedding_service.model_name,
        )

    def list_documents(self) -> list[DocumentResponse]:
        return self.repository.list_documents()

    def search(
        self,
        request: SearchKnowledgeRequest,
    ) -> list[KnowledgeSearchResult]:
        return self.retrieve(request.query, request.top_k)

    def retrieve(
        self,
        query: str,
        top_k: int,
    ) -> list[KnowledgeSearchResult]:
        candidate_k = top_k * settings.hybrid_candidate_multiplier
        lexical_results = self.repository.search_lexical(query, candidate_k)

        try:
            query_embedding = self.embedding_service.encode_query(query)
            vector_results = self.repository.search_vector(
                query_embedding=query_embedding,
                embedding_model=self.embedding_service.model_name,
                top_k=candidate_k,
                min_similarity=settings.vector_min_similarity,
            )
        except (OSError, RuntimeError):
            vector_results = []

        fused_results = _fuse_with_rrf(
            lexical_results=lexical_results,
            vector_results=vector_results,
            top_k=candidate_k,
            rrf_k=settings.hybrid_rrf_k,
        )
        return self.reranker_service.rerank(query, fused_results, top_k)

    def reindex_embeddings(self) -> ReindexKnowledgeResponse:
        chunks = self.repository.list_chunks_for_reindex(
            self.embedding_service.model_name
        )

        if chunks:
            chunk_ids = [chunk_id for chunk_id, _ in chunks]
            embeddings = self.embedding_service.encode_documents(
                [content for _, content in chunks]
            )
            self.repository.update_chunk_embeddings(
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                embedding_model=self.embedding_service.model_name,
            )

        return ReindexKnowledgeResponse(
            updated_chunk_count=len(chunks),
            embedding_model=self.embedding_service.model_name,
        )


knowledge_service = KnowledgeService()


def _fuse_with_rrf(
    lexical_results: list[KnowledgeSearchResult],
    vector_results: list[KnowledgeSearchResult],
    top_k: int,
    rrf_k: int,
) -> list[KnowledgeSearchResult]:
    fused: dict[str, dict] = {}

    for source, results in (
        ("lexical", lexical_results),
        ("vector", vector_results),
    ):
        for rank, result in enumerate(results, start=1):
            item = fused.setdefault(
                result.chunk_id,
                {
                    "result": result,
                    "score": 0.0,
                    "lexical_score": 0.0,
                    "vector_score": 0.0,
                    "sources": [],
                },
            )
            item["score"] += 1 / (rrf_k + rank)
            item[f"{source}_score"] = getattr(result, f"{source}_score")
            item["sources"].append(source)

    ranked = sorted(
        fused.values(),
        key=lambda item: item["score"],
        reverse=True,
    )

    return [
        item["result"].model_copy(
            update={
                "score": round(item["score"], 8),
                "lexical_score": item["lexical_score"],
                "vector_score": item["vector_score"],
                "retrieval_sources": item["sources"],
            }
        )
        for item in ranked[:top_k]
    ]
