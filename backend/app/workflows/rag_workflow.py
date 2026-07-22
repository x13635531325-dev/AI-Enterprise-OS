from time import perf_counter

from app.core.config import settings
from app.gateways.model_gateway import generate_text
from app.schemas.runs import CitationResponse, SpanResponse, StepResponse, new_id
from app.services.answer_guardrails import (
    skipped_citation_guardrail_metadata,
    validate_answer_citations,
)
from app.services.knowledge_service import knowledge_service
from app.services.prompt_registry import build_rag_grounded_prompt
from app.workflows.workflow_result import WorkflowResult

RAG_RETRIEVAL_TOP_K = 4


def run_rag_workflow(user_input: str) -> WorkflowResult:
    retrieval_started_at = perf_counter()
    search_results = knowledge_service.retrieve(user_input, top_k=RAG_RETRIEVAL_TOP_K)
    retrieval_latency_ms = _elapsed_ms(retrieval_started_at)
    retrieval_metadata = _build_retrieval_metadata(
        search_results,
        top_k=RAG_RETRIEVAL_TOP_K,
    )

    if not search_results:
        message = (
            "I could not find relevant information in the enterprise knowledge base."
        )
        return WorkflowResult(
            steps=[
                _input_step(user_input),
                StepResponse(
                    id=new_id("step"),
                    name="retrieve_knowledge",
                    status="completed",
                    output="No relevant knowledge chunks found.",
                    metadata=retrieval_metadata,
                ),
                StepResponse(
                    id=new_id("step"),
                    name="generate_grounded_answer",
                    status="completed",
                    output=message,
                ),
            ],
            spans=[
                _input_span(user_input),
                SpanResponse(
                    id=new_id("span"),
                    name="retrieve_knowledge",
                    status="completed",
                    latency_ms=retrieval_latency_ms,
                    output="No relevant knowledge chunks found.",
                    metadata=retrieval_metadata,
                ),
                SpanResponse(
                    id=new_id("span"),
                    name="generate_grounded_answer",
                    status="completed",
                    latency_ms=0,
                    output=message,
                ),
            ],
        )

    citations = [
        CitationResponse(
            index=index,
            document_id=result.document_id,
            document_title=result.document_title,
            chunk_id=result.chunk_id,
            excerpt=result.content[:320],
        )
        for index, result in enumerate(search_results, start=1)
    ]
    rendered_prompt = build_rag_grounded_prompt(user_input, search_results)
    reply = generate_text(rendered_prompt.text, task_type="rag_answer")
    guardrail_metadata = (
        validate_answer_citations(reply.text, citations)
        if reply.succeeded
        else skipped_citation_guardrail_metadata("model_call_failed")
    )
    output = _append_sources(reply.text, citations) if reply.succeeded else reply.text
    generation_metadata = {
        **reply.metadata,
        **rendered_prompt.metadata,
        **guardrail_metadata,
    }

    return WorkflowResult(
        steps=[
            _input_step(user_input),
            StepResponse(
                id=new_id("step"),
                name="retrieve_knowledge",
                status="completed",
                output=f"Retrieved {len(search_results)} knowledge chunks.",
                metadata=retrieval_metadata,
            ),
            StepResponse(
                id=new_id("step"),
                name="generate_grounded_answer",
                status=reply.status,
                output=output,
                metadata=generation_metadata,
            ),
        ],
        spans=[
            _input_span(user_input),
            SpanResponse(
                id=new_id("span"),
                name="retrieve_knowledge",
                status="completed",
                latency_ms=retrieval_latency_ms,
                output=f"Retrieved {len(search_results)} knowledge chunks.",
                metadata=retrieval_metadata,
            ),
            SpanResponse(
                id=new_id("span"),
                name="generate_grounded_answer",
                status=reply.status,
                latency_ms=reply.latency_ms,
                output=output,
                error=reply.error,
                model_calls=reply.model_calls,
                tool_calls=reply.tool_calls,
                metadata={
                    **rendered_prompt.metadata,
                    **guardrail_metadata,
                },
            ),
        ],
        citations=citations,
    )


def _append_sources(text: str, citations: list[CitationResponse]) -> str:
    source_lines = "\n".join(
        f"[{citation.index}] {citation.document_title}"
        for citation in citations
    )
    return f"{text}\n\nSources:\n{source_lines}"


def _build_retrieval_metadata(search_results: list, top_k: int) -> dict:
    return {
        "requested_top_k": top_k,
        "candidate_k": top_k * settings.hybrid_candidate_multiplier,
        "hybrid_candidate_multiplier": settings.hybrid_candidate_multiplier,
        "reranker_enabled": settings.reranker_enabled,
        "result_count": len(search_results),
        "retrieval_results": [
            {
                "rank": index,
                "document_title": result.document_title,
                "chunk_id": result.chunk_id,
                "score": _round_score(result.score),
                "lexical_score": _round_score(result.lexical_score),
                "vector_score": _round_score(result.vector_score),
                "reranker_score": _round_score(result.reranker_score),
                "retrieval_sources": result.retrieval_sources,
            }
            for index, result in enumerate(search_results, start=1)
        ],
    }


def _round_score(value: float) -> float:
    return round(float(value), 6)


def _input_step(user_input: str) -> StepResponse:
    return StepResponse(
        id=new_id("step"),
        name="receive_user_input",
        status="completed",
        output=user_input,
    )


def _input_span(user_input: str) -> SpanResponse:
    return SpanResponse(
        id=new_id("span"),
        name="receive_user_input",
        status="completed",
        latency_ms=5,
        output=user_input,
    )


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))
