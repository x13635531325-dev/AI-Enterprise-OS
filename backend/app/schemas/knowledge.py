from typing import Any

from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    metadata: dict[str, Any]
    chunk_count: int
    created_at: str


class SearchKnowledgeRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    content: str
    position: int
    score: float
    lexical_score: float = 0
    vector_score: float = 0
    reranker_score: float = 0
    retrieval_sources: list[str] = Field(default_factory=list)


class ReindexKnowledgeResponse(BaseModel):
    updated_chunk_count: int
    embedding_model: str
