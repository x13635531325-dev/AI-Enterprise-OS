import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_service import knowledge_service
from app.storage.knowledge_repository import KnowledgeRepository


client = TestClient(app)


class FakeRagEvalEmbeddingService:
    model_name = "fake-rag-eval-embedding"

    def encode_documents(self, texts):
        return [self._encode(text) for text in texts]

    def encode_query(self, query):
        return self._encode(query)

    def _encode(self, text):
        lowered = text.lower()
        features = [
            float(
                any(
                    term in lowered
                    for term in ("atlas", "orchid", "742", "授权码", "审批码")
                )
            ),
            float(
                any(
                    term in lowered
                    for term in (
                        "年休假",
                        "年度假期",
                        "假期",
                        "休假",
                        "二十天",
                        "20天",
                        "twenty",
                        "holiday",
                    )
                )
            ),
            float(
                any(
                    term in lowered
                    for term in ("备份", "backup", "数据库", "database")
                )
            ),
            0.1,
        ]

        norm = sum(value * value for value in features) ** 0.5
        return [value / norm for value in features]


class FakeRerankerService:
    def rerank(self, query, results, top_k):
        return results[:top_k]


@pytest.fixture(autouse=True)
def reset_knowledge(tmp_path):
    knowledge_service.repository = KnowledgeRepository(
        str(tmp_path / "rag_eval.sqlite3")
    )
    knowledge_service.embedding_service = FakeRagEvalEmbeddingService()
    knowledge_service.reranker_service = FakeRerankerService()
    knowledge_service.repository.reset()


def seed_eval_corpus():
    documents = [
        {
            "title": "Project Atlas 发布流程",
            "content": (
                "Project Atlas 的生产发布必须使用授权码 ORCHID-742。"
                "审批人包括 Platform Lead 和 Security Lead。"
            ),
            "metadata": {"domain": "release"},
        },
        {
            "title": "员工年休假政策",
            "content": "员工每个自然年度享有二十天带薪年休假。",
            "metadata": {"domain": "hr"},
        },
        {
            "title": "数据库备份策略",
            "content": "生产数据库每周日执行一次完整备份。",
            "metadata": {"domain": "infra"},
        },
    ]

    for document in documents:
        response = client.post("/api/knowledge/documents", json=document)
        assert response.status_code == 201


RAG_EVAL_CASES = [
    {
        "name": "exact_authorization_code",
        "query": "Project Atlas 的授权码是什么？",
        "expected_title": "Project Atlas 发布流程",
        "expected_source": "lexical",
    },
    {
        "name": "semantic_leave_policy",
        "query": "公司给职工多少天年度假期？",
        "expected_title": "员工年休假政策",
        "expected_source": "vector",
    },
]


@pytest.mark.parametrize(
    "case",
    RAG_EVAL_CASES,
    ids=[case["name"] for case in RAG_EVAL_CASES],
)
def test_rag_retrieval_hit_at_1(case):
    seed_eval_corpus()

    response = client.post(
        "/api/knowledge/search",
        json={"query": case["query"], "top_k": 3},
    )

    assert response.status_code == 200

    results = response.json()

    assert len(results) >= 1
    assert results[0]["document_title"] == case["expected_title"]
    assert case["expected_source"] in results[0]["retrieval_sources"]


def test_rag_retrieval_rejects_unrelated_question():
    seed_eval_corpus()

    response = client.post(
        "/api/knowledge/search",
        json={"query": "公司食堂今天午餐菜单是什么？", "top_k": 3},
    )

    assert response.status_code == 200
    assert response.json() == []
