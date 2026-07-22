import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_service import knowledge_service
from app.services.text_chunker import TextChunker
from app.storage.knowledge_repository import KnowledgeRepository


client = TestClient(app)


class FakeEmbeddingService:
    model_name = "fake-embedding-model"

    def encode_documents(self, texts):
        return [self._encode(text) for text in texts]

    def encode_query(self, query):
        return self._encode(query)

    def _encode(self, text):
        lowered = text.lower()
        features = [
            float(any(term in lowered for term in ("rag", "hallucination"))),
            float(any(term in lowered for term in ("annual leave", "holiday"))),
            float(any(term in lowered for term in ("atlas", "deployment"))),
            0.1,
        ]
        norm = sum(value * value for value in features) ** 0.5
        return [value / norm for value in features]


class SecondFakeEmbeddingService(FakeEmbeddingService):
    model_name = "second-fake-embedding-model"


class FakeRerankerService:
    def rerank(self, query, results, top_k):
        return results[:top_k]


@pytest.fixture(autouse=True)
def reset_knowledge(tmp_path):
    knowledge_service.repository = KnowledgeRepository(
        str(tmp_path / "test_knowledge.sqlite3")
    )
    knowledge_service.embedding_service = FakeEmbeddingService()
    knowledge_service.reranker_service = FakeRerankerService()
    knowledge_service.repository.reset()


def test_text_chunker_creates_overlapping_chunks():
    chunker = TextChunker(max_chars=20, overlap_chars=5)

    chunks = chunker.split("A" * 35)

    assert len(chunks) == 2
    assert chunks[0].end_offset == 20
    assert chunks[1].start_offset == 15


def test_create_and_list_document():
    response = client.post(
        "/api/knowledge/documents",
        json={
            "title": "RAG Guide",
            "content": "RAG retrieves trusted context before generating an answer.",
            "metadata": {"team": "ai-platform"},
        },
    )

    assert response.status_code == 201
    assert response.json()["chunk_count"] == 1

    list_response = client.get("/api/knowledge/documents")

    assert list_response.status_code == 200
    assert list_response.json()[0]["title"] == "RAG Guide"


def test_search_returns_relevant_chunk():
    client.post(
        "/api/knowledge/documents",
        json={
            "title": "Enterprise RAG",
            "content": (
                "RAG retrieves enterprise documents before generation. "
                "It reduces hallucinations and provides grounded answers."
            ),
        },
    )

    response = client.post(
        "/api/knowledge/search",
        json={"query": "RAG hallucinations", "top_k": 3},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["document_title"] == "Enterprise RAG"
    assert response.json()[0]["retrieval_sources"] == ["lexical", "vector"]


def test_hybrid_search_can_retrieve_semantic_paraphrase():
    client.post(
        "/api/knowledge/documents",
        json={
            "title": "Backup Policy",
            "content": "Production databases receive a full backup every Sunday.",
        },
    )

    client.post(
        "/api/knowledge/documents",
        json={
            "title": "Leave Policy",
            "content": "Employees receive twenty days of annual leave each year.",
        },
    )

    response = client.post(
        "/api/knowledge/search",
        json={"query": "How much holiday is allowed?", "top_k": 3},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["document_title"] == "Leave Policy"
    assert response.json()[0]["retrieval_sources"] == ["vector"]


def test_reindex_updates_chunks_when_embedding_model_changes():
    client.post(
        "/api/knowledge/documents",
        json={
            "title": "Reindex Policy",
            "content": "This document should receive a replacement embedding.",
        },
    )
    knowledge_service.embedding_service = SecondFakeEmbeddingService()

    response = client.post("/api/knowledge/reindex")

    assert response.status_code == 200
    assert response.json() == {
        "updated_chunk_count": 1,
        "embedding_model": "second-fake-embedding-model",
    }
