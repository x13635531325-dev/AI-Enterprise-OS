import pytest
from fastapi.testclient import TestClient

from app.gateways.circuit_breaker import circuit_breaker
from app.core.config import settings
from app.main import app
from app.services.knowledge_service import knowledge_service
from app.services.run_service import run_service
from app.storage.knowledge_repository import KnowledgeRepository
from app.storage.run_repository import RunRepository


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
            float("rag" in lowered),
            float("hallucination" in lowered),
            float("enterprise" in lowered),
            0.1,
        ]
        norm = sum(value * value for value in features) ** 0.5
        return [value / norm for value in features]


class FakeRerankerService:
    def rerank(self, query, results, top_k):
        return results[:top_k]


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    circuit_breaker.reset()
    settings.model_provider = "mock"
    settings.deepseek_api_key = None
    settings.openai_api_key = None
    settings.reranker_enabled = False
    db_path = str(tmp_path / "test_ai_enterprise_os.sqlite3")
    run_service.repository = RunRepository(db_path)
    knowledge_service.repository = KnowledgeRepository(db_path)
    knowledge_service.embedding_service = FakeEmbeddingService()
    knowledge_service.reranker_service = FakeRerankerService()
    run_service.reset()
    knowledge_service.repository.reset()


def test_create_run_returns_completed_run():
    response = client.post("/api/runs", json={"input": "Explain RAG"})

    assert response.status_code == 201

    body = response.json()
    assert body["id"].startswith("run_")
    assert body["status"] == "completed"
    assert body["input"] == "Explain RAG"
    assert body["created_at"]
    assert body["output"]
    assert "Model Gateway" in body["output"]
    assert len(body["steps"]) == 2
    assert body["steps"][0]["name"] == "receive_user_input"
    assert body["steps"][1]["name"] == "generate_ai_reply"
    assert body["steps"][1]["metadata"]["model"] == "mock-chat-model-v1"
    assert body["trace"]["status"] == "completed"
    assert body["trace"]["spans"][1]["model_calls"][0]["model"] == "mock-chat-model-v1"
    assert body["metrics"]["model_call_count"] == 1
    assert body["metrics"]["failed_model_call_count"] == 0
    assert body["metrics"]["retryable_failure_count"] == 0
    assert body["metrics"]["short_circuit_count"] == 0
    assert body["metrics"]["retry_count"] == 0
    assert body["metrics"]["total_tokens"] > 0
    assert body["metrics"]["total_cost_usd"] > 0


def test_get_run_returns_existing_run_from_database():
    create_response = client.post("/api/runs", json={"input": "Create a workflow"})
    run_id = create_response.json()["id"]

    get_response = client.get(f"/api/runs/{run_id}")

    assert get_response.status_code == 200

    body = get_response.json()
    assert body["id"] == run_id
    assert body["steps"][1]["name"] == "generate_ai_reply"
    assert body["trace"]["spans"][1]["model_calls"][0]["model"] == "mock-chat-model-v1"


def test_run_repository_can_read_run_after_new_repository_instance():
    create_response = client.post("/api/runs", json={"input": "Persist this Run"})
    run_id = create_response.json()["id"]

    fresh_repository = RunRepository(run_service.repository.db_path)
    saved_run = fresh_repository.get_run(run_id)

    assert saved_run is not None
    assert saved_run.id == run_id
    assert saved_run.input == "Persist this Run"
    assert saved_run.trace is not None
    assert saved_run.trace.spans[1].model_calls[0].model == "mock-chat-model-v1"


def test_list_runs_returns_saved_runs():
    first_response = client.post("/api/runs", json={"input": "First Run"})
    second_response = client.post("/api/runs", json={"input": "Second Run"})

    response = client.get("/api/runs")

    assert response.status_code == 200

    body = response.json()
    run_ids = {item["id"] for item in body}

    assert first_response.json()["id"] in run_ids
    assert second_response.json()["id"] in run_ids
    assert body[0]["created_at"]
    assert body[0]["metrics"]["model_call_count"] == 1


def test_get_run_returns_404_for_missing_run():
    response = client.get("/api/runs/run_missing")

    assert response.status_code == 404


def test_create_run_returns_failed_run_for_unknown_workflow():
    response = client.post(
        "/api/runs",
        json={"input": "Test unknown workflow", "workflow_name": "missing_workflow"},
    )

    assert response.status_code == 201

    body = response.json()
    assert body["status"] == "failed"
    assert body["workflow_name"] == "missing_workflow"
    assert body["steps"][0]["name"] == "select_workflow"
    assert body["steps"][0]["status"] == "failed"
    assert body["trace"]["status"] == "failed"
    assert body["metrics"]["model_call_count"] == 0
    assert body["metrics"]["failed_model_call_count"] == 0
    assert body["metrics"]["retryable_failure_count"] == 0
    assert body["metrics"]["short_circuit_count"] == 0
    assert body["metrics"]["retry_count"] == 0


def test_create_run_can_select_task_planning_workflow():
    response = client.post(
        "/api/runs",
        json={"input": "Create a study plan", "workflow_name": "task_planning_workflow"},
    )

    assert response.status_code == 201

    body = response.json()
    assert body["status"] == "completed"
    assert body["workflow_name"] == "task_planning_workflow"
    assert len(body["steps"]) == 3
    assert body["steps"][1]["name"] == "create_task_plan"
    assert body["steps"][2]["name"] == "summarize_plan"
    assert len(body["trace"]["spans"]) == 3
    assert body["trace"]["spans"][1]["model_calls"][0]["task_type"] == "task_plan"
    assert (
        body["trace"]["spans"][1]["model_calls"][0]["model"]
        == "mock-planner-model-v1"
    )
    assert body["trace"]["spans"][1]["model_calls"][0]["attempt"] == 1
    assert body["trace"]["spans"][1]["model_calls"][0]["status"] == "failed"
    assert body["trace"]["spans"][1]["model_calls"][0]["error_type"] == "timeout"
    assert body["trace"]["spans"][1]["model_calls"][0]["retryable"] is True
    assert (
        body["trace"]["spans"][1]["model_calls"][1]["model"]
        == "mock-planner-model-v1"
    )
    assert body["trace"]["spans"][1]["model_calls"][1]["attempt"] == 2
    assert body["trace"]["spans"][1]["model_calls"][1]["status"] == "failed"
    assert body["trace"]["spans"][1]["model_calls"][1]["error_type"] == "timeout"
    assert body["trace"]["spans"][1]["model_calls"][1]["retryable"] is True
    assert (
        body["trace"]["spans"][1]["model_calls"][2]["model"]
        == "mock-planner-fallback-model-v1"
    )
    assert body["trace"]["spans"][1]["model_calls"][2]["attempt"] == 1
    assert body["trace"]["spans"][1]["model_calls"][2]["status"] == "completed"
    assert (
        body["trace"]["spans"][2]["model_calls"][0]["model"]
        == "mock-summary-model-v1"
    )
    assert body["metrics"]["model_call_count"] == 4
    assert body["metrics"]["failed_model_call_count"] == 2
    assert body["metrics"]["retryable_failure_count"] == 2
    assert body["metrics"]["short_circuit_count"] == 0
    assert body["metrics"]["retry_count"] == 1
    assert body["metrics"]["total_latency_ms"] == 595
    assert body["metrics"]["total_tokens"] > 0
    assert body["metrics"]["total_cost_usd"] > 0


def test_circuit_breaker_skips_unhealthy_primary_model():
    client.post(
        "/api/runs",
        json={"input": "First plan", "workflow_name": "task_planning_workflow"},
    )

    response = client.post(
        "/api/runs",
        json={"input": "Second plan", "workflow_name": "task_planning_workflow"},
    )

    assert response.status_code == 201

    body = response.json()
    model_calls = body["trace"]["spans"][1]["model_calls"]

    assert model_calls[0]["model"] == "mock-planner-model-v1"
    assert model_calls[0]["status"] == "skipped"
    assert model_calls[0]["attempt"] == 0
    assert model_calls[0]["circuit_state"] == "open"
    assert model_calls[0]["error_type"] == "circuit_open"
    assert model_calls[1]["model"] == "mock-planner-fallback-model-v1"
    assert model_calls[1]["status"] == "completed"
    assert body["metrics"]["model_call_count"] == 3
    assert body["metrics"]["failed_model_call_count"] == 0
    assert body["metrics"]["retryable_failure_count"] == 0
    assert body["metrics"]["short_circuit_count"] == 1
    assert body["metrics"]["retry_count"] == 0
    assert body["metrics"]["total_latency_ms"] == 235


def test_model_health_reports_circuit_breaker_state():
    initial_response = client.get("/api/model-health")

    assert initial_response.status_code == 200

    initial_health = {item["model"]: item for item in initial_response.json()}
    assert initial_health["mock-planner-model-v1"]["status"] == "healthy"
    assert initial_health["mock-planner-model-v1"]["failure_count"] == 0
    assert initial_health["mock-planner-model-v1"]["failure_threshold"] == 2
    assert (
        initial_health["mock-planner-model-v1"]["fallback_model"]
        == "mock-planner-fallback-model-v1"
    )

    client.post(
        "/api/runs",
        json={"input": "Trigger model failure", "workflow_name": "task_planning_workflow"},
    )

    health_response = client.get("/api/model-health")

    assert health_response.status_code == 200

    health = {item["model"]: item for item in health_response.json()}
    assert health["mock-planner-model-v1"]["status"] == "open"
    assert health["mock-planner-model-v1"]["circuit_state"] == "open"
    assert health["mock-planner-model-v1"]["failure_count"] == 2
    assert health["mock-planner-fallback-model-v1"]["status"] == "healthy"


def test_openai_mode_without_api_key_persists_failed_run():
    settings.model_provider = "openai"

    response = client.post("/api/runs", json={"input": "Use a real model"})

    assert response.status_code == 201

    body = response.json()
    model_call = body["trace"]["spans"][1]["model_calls"][0]

    assert body["status"] == "failed"
    assert body["trace"]["status"] == "failed"
    assert body["steps"][1]["status"] == "failed"
    assert model_call["provider"] == "openai"
    assert model_call["model"] == settings.openai_model
    assert model_call["status"] == "failed"
    assert model_call["error_type"] == "invalid_request"
    assert model_call["retryable"] is False


def test_deepseek_mode_without_api_key_persists_failed_run():
    settings.model_provider = "deepseek"

    response = client.post("/api/runs", json={"input": "Use DeepSeek"})

    assert response.status_code == 201

    body = response.json()
    model_call = body["trace"]["spans"][1]["model_calls"][0]

    assert body["status"] == "failed"
    assert model_call["provider"] == "deepseek"
    assert model_call["model"] == settings.deepseek_model
    assert model_call["error_type"] == "invalid_request"


def test_rag_workflow_retrieves_knowledge_and_persists_citations():
    document_response = client.post(
        "/api/knowledge/documents",
        json={
            "title": "Enterprise RAG Policy",
            "content": (
                "The approved RAG system retrieves internal documents before "
                "generation and cites its sources to reduce hallucinations."
            ),
        },
    )
    document_id = document_response.json()["id"]

    response = client.post(
        "/api/runs",
        json={
            "input": "How does the approved RAG system reduce hallucinations?",
            "workflow_name": "rag_workflow",
        },
    )

    assert response.status_code == 201

    body = response.json()
    assert body["status"] == "completed"
    assert body["workflow_name"] == "rag_workflow"
    assert body["steps"][1]["name"] == "retrieve_knowledge"
    assert body["steps"][1]["metadata"]["result_count"] == 1
    assert body["steps"][1]["metadata"]["requested_top_k"] == 4
    assert body["steps"][1]["metadata"]["candidate_k"] == (
        4 * settings.hybrid_candidate_multiplier
    )
    assert body["steps"][1]["metadata"]["reranker_enabled"] is False
    assert (
        body["steps"][1]["metadata"]["retrieval_results"][0]["document_title"]
        == "Enterprise RAG Policy"
    )
    assert body["steps"][1]["metadata"]["retrieval_results"][0]["score"] > 0
    assert body["steps"][1]["metadata"]["retrieval_results"][0]["retrieval_sources"] == [
        "lexical",
        "vector",
    ]
    assert body["trace"]["spans"][1]["metadata"] == body["steps"][1]["metadata"]
    assert body["steps"][2]["metadata"]["prompt_name"] == "rag_grounded_answer"
    assert body["steps"][2]["metadata"]["prompt_version"] == "v1"
    assert body["steps"][2]["metadata"]["context_source_count"] == 1
    assert body["steps"][2]["metadata"]["citation_style"] == "numbered_brackets"
    assert len(body["steps"][2]["metadata"]["prompt_template_hash"]) == 12
    assert body["steps"][2]["metadata"]["citation_guardrail_status"] == "passed"
    assert body["steps"][2]["metadata"]["citation_guardrail_passed"] is True
    assert body["steps"][2]["metadata"]["citation_required"] is True
    assert body["steps"][2]["metadata"]["available_source_indices"] == [1]
    assert body["steps"][2]["metadata"]["cited_source_indices"] == [1]
    assert body["steps"][2]["metadata"]["invalid_source_indices"] == []
    assert body["steps"][2]["metadata"]["missing_required_citation"] is False
    assert body["trace"]["spans"][2]["metadata"]["prompt_version"] == "v1"
    assert (
        body["trace"]["spans"][2]["metadata"]["citation_guardrail_status"]
        == "passed"
    )
    assert body["trace"]["spans"][2]["model_calls"][0]["model"] == "mock-rag-model-v1"
    assert body["citations"][0]["document_id"] == document_id
    assert body["citations"][0]["document_title"] == "Enterprise RAG Policy"

    saved_response = client.get(f"/api/runs/{body['id']}")

    assert saved_response.json()["citations"] == body["citations"]
