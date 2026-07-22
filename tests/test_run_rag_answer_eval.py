import json

from app.evals.run_rag_answer_eval import (
    build_rag_answer_run_output,
    format_eval_summary,
    load_eval_corpus,
    run_rag_answer_eval,
    save_eval_report,
)
from app.schemas.runs import (
    RunMetricsResponse,
    RunResponse,
    SpanResponse,
    StepResponse,
    TraceResponse,
)


def test_load_eval_corpus_returns_document_requests():
    documents = load_eval_corpus(
        "backend/app/evals/golden_sets/rag_eval_corpus.json"
    )

    assert len(documents) == 2
    assert documents[0].title == "Project Atlas Release Procedure"
    assert "ORCHID-742" in documents[0].content
    assert documents[0].metadata == {"domain": "release"}


def test_build_rag_answer_run_output_extracts_answer_guardrail_and_trace():
    run = RunResponse(
        id="run_eval",
        workflow_name="rag_workflow",
        input="What is the authorization code?",
        status="completed",
        output="Project Atlas uses ORCHID-742 [1].",
        steps=[
            StepResponse(
                id="step_input",
                name="receive_user_input",
                status="completed",
                output="What is the authorization code?",
            ),
            StepResponse(
                id="step_retrieve",
                name="retrieve_knowledge",
                status="completed",
                output="Retrieved 1 knowledge chunks.",
                metadata={"result_count": 1},
            ),
            StepResponse(
                id="step_generate",
                name="generate_grounded_answer",
                status="completed",
                output="Project Atlas uses ORCHID-742 [1].",
                metadata={
                    "prompt_version": "v1",
                    "prompt_template_hash": "abc123abc123",
                    "citation_guardrail_status": "passed",
                    "citation_guardrail_passed": True,
                },
            ),
        ],
        trace=TraceResponse(
            id="trace_eval",
            status="completed",
            spans=[
                SpanResponse(
                    id="span_input",
                    name="receive_user_input",
                    status="completed",
                    latency_ms=1,
                ),
                SpanResponse(
                    id="span_retrieve",
                    name="retrieve_knowledge",
                    status="completed",
                    latency_ms=2,
                    metadata={"result_count": 1},
                ),
                SpanResponse(
                    id="span_generate",
                    name="generate_grounded_answer",
                    status="completed",
                    latency_ms=3,
                    metadata={
                        "prompt_version": "v1",
                        "citation_guardrail_status": "passed",
                    },
                ),
            ],
        ),
        metrics=RunMetricsResponse(total_tokens=10),
    )

    run_output = build_rag_answer_run_output(run)

    assert run_output.answer_text == "Project Atlas uses ORCHID-742 [1]."
    assert run_output.citation_guardrail_metadata["citation_guardrail_passed"] is True
    assert run_output.trace_metadata["run_id"] == "run_eval"
    assert run_output.trace_metadata["prompt_version"] == "v1"
    assert run_output.trace_metadata["retrieval"] == {"result_count": 1}
    assert run_output.trace_metadata["metrics"]["total_tokens"] == 10


def test_save_eval_report_writes_report_json_with_metadata(tmp_path):
    report = {
        "eval_metadata": {
            "generated_at": "2026-07-10T12:00:00Z",
            "model_provider": "mock",
            "golden_set": {
                "name": "rag_answer_golden_set",
                "version": "v1",
            },
            "reranker": {
                "enabled": False,
                "model": "BAAI/bge-reranker-base",
            },
        },
        "total_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "pass_rate": 1.0,
        "results": [],
    }

    report_path = save_eval_report(report, tmp_path)

    assert report_path.exists()
    assert report_path.name.startswith("rag_answer_eval_")
    assert report["eval_metadata"]["report_path"] == str(report_path)

    saved_report = json.loads(report_path.read_text(encoding="utf-8"))

    assert saved_report["eval_metadata"]["model_provider"] == "mock"
    assert saved_report["pass_rate"] == 1.0
    assert saved_report["eval_metadata"]["report_path"] == str(report_path)


def test_run_rag_answer_eval_ci_mode_uses_deterministic_offline_services():
    report = run_rag_answer_eval(ci_mode=True)

    assert report["eval_metadata"]["ci_mode"] is True
    assert report["eval_metadata"]["model_provider"] == "mock"
    assert report["eval_metadata"]["isolated"] is True
    assert report["total_count"] == 3
    assert report["passed_count"] == 3
    assert report["failed_count"] == 0
    assert report["pass_rate"] == 1.0


def test_format_eval_summary_shows_pass_rate_and_report_path():
    summary = format_eval_summary(
        {
            "eval_metadata": {
                "generated_at": "2026-07-10T12:00:00Z",
                "model_provider": "mock",
                "report_path": "backend/app/evals/reports/report.json",
                "golden_set": {
                    "name": "rag_answer_golden_set",
                    "version": "v1",
                },
                "corpus": {
                    "name": "rag_eval_corpus",
                    "version": "v1",
                },
                "reranker": {
                    "enabled": False,
                    "model": "BAAI/bge-reranker-base",
                },
            },
            "total_count": 2,
            "passed_count": 2,
            "failed_count": 0,
            "pass_rate": 1.0,
            "results": [
                {
                    "name": "atlas_release_authorization_code",
                    "passed": True,
                }
            ],
        }
    )

    assert "RAG Answer Eval Summary" in summary
    assert "Model provider: mock" in summary
    assert "Golden set: rag_answer_golden_set@v1" in summary
    assert "Pass rate: 100.00% (2/2 passed)" in summary
    assert "Report: backend/app/evals/reports/report.json" in summary
    assert "Failed cases: none" in summary


def test_format_eval_summary_lists_failed_cases():
    summary = format_eval_summary(
        {
            "eval_metadata": {
                "generated_at": "2026-07-10T12:00:00Z",
                "model_provider": "mock",
                "golden_set": {
                    "name": "rag_answer_golden_set",
                    "version": "v1",
                },
                "corpus": {
                    "name": "rag_eval_corpus",
                    "version": "v1",
                },
                "reranker": {
                    "enabled": True,
                    "model": "BAAI/bge-reranker-base",
                },
            },
            "total_count": 2,
            "passed_count": 1,
            "failed_count": 1,
            "pass_rate": 0.5,
            "results": [
                {
                    "name": "atlas_release_authorization_code",
                    "passed": True,
                    "fact_coverage": 1.0,
                    "missing_facts": [],
                    "citation_guardrail_status": "passed",
                },
                {
                    "name": "atlas_release_approvers",
                    "passed": False,
                    "fact_coverage": 0.5,
                    "missing_facts": ["Security Lead"],
                    "citation_guardrail_status": "passed",
                },
            ],
        }
    )

    assert "Reranker: enabled (BAAI/bge-reranker-base)" in summary
    assert "Pass rate: 50.00% (1/2 passed)" in summary
    assert "Failed cases:" in summary
    assert (
        "- atlas_release_approvers: coverage=0.50, "
        "missing_facts=Security Lead, citation=passed"
    ) in summary
