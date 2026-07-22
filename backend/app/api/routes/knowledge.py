from fastapi import APIRouter

from app.schemas.knowledge import (
    CreateDocumentRequest,
    DocumentResponse,
    KnowledgeSearchResult,
    ReindexKnowledgeResponse,
    SearchKnowledgeRequest,
)
from app.services.knowledge_service import knowledge_service


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=201,
)
def create_document(request: CreateDocumentRequest):
    return knowledge_service.create_document(request)


@router.get(
    "/documents",
    response_model=list[DocumentResponse],
)
def list_documents():
    return knowledge_service.list_documents()


@router.post(
    "/search",
    response_model=list[KnowledgeSearchResult],
)
def search_knowledge(request: SearchKnowledgeRequest):
    return knowledge_service.search(request)


@router.post(
    "/reindex",
    response_model=ReindexKnowledgeResponse,
)
def reindex_knowledge():
    return knowledge_service.reindex_embeddings()
