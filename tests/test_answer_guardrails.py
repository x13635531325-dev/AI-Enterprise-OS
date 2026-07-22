from app.schemas.runs import CitationResponse
from app.services.answer_guardrails import validate_answer_citations


def make_citation(index: int) -> CitationResponse:
    return CitationResponse(
        index=index,
        document_id=f"doc_{index}",
        document_title=f"Document {index}",
        chunk_id=f"chunk_{index}",
        excerpt="Trusted source excerpt.",
    )


def test_citation_guardrail_passes_valid_citation():
    metadata = validate_answer_citations(
        answer_text="The policy requires source citations [1].",
        citations=[make_citation(1)],
    )

    assert metadata["citation_guardrail_status"] == "passed"
    assert metadata["citation_guardrail_passed"] is True
    assert metadata["available_source_indices"] == [1]
    assert metadata["cited_source_indices"] == [1]
    assert metadata["invalid_source_indices"] == []
    assert metadata["missing_required_citation"] is False


def test_citation_guardrail_fails_when_required_citation_is_missing():
    metadata = validate_answer_citations(
        answer_text="The policy requires source citations.",
        citations=[make_citation(1)],
    )

    assert metadata["citation_guardrail_status"] == "failed"
    assert metadata["citation_guardrail_passed"] is False
    assert metadata["cited_source_indices"] == []
    assert metadata["missing_required_citation"] is True


def test_citation_guardrail_fails_invalid_citation_index():
    metadata = validate_answer_citations(
        answer_text="The policy requires source citations [2].",
        citations=[make_citation(1)],
    )

    assert metadata["citation_guardrail_status"] == "failed"
    assert metadata["citation_guardrail_passed"] is False
    assert metadata["cited_source_indices"] == [2]
    assert metadata["invalid_source_indices"] == [2]
