import re

from app.schemas.runs import CitationResponse


def validate_answer_citations(
    answer_text: str,
    citations: list[CitationResponse],
    require_citation: bool = True,
) -> dict:
    available_indices = sorted(citation.index for citation in citations)
    cited_indices = _extract_citation_indices(answer_text)
    invalid_indices = [
        index for index in cited_indices if index not in available_indices
    ]
    missing_required_citation = (
        require_citation
        and bool(available_indices)
        and not cited_indices
    )
    passed = not invalid_indices and not missing_required_citation

    return {
        "citation_guardrail_status": "passed" if passed else "failed",
        "citation_guardrail_passed": passed,
        "citation_required": require_citation,
        "available_source_indices": available_indices,
        "cited_source_indices": cited_indices,
        "invalid_source_indices": invalid_indices,
        "missing_required_citation": missing_required_citation,
    }


def skipped_citation_guardrail_metadata(reason: str) -> dict:
    return {
        "citation_guardrail_status": "skipped",
        "citation_guardrail_passed": False,
        "citation_guardrail_skip_reason": reason,
    }


def _extract_citation_indices(text: str) -> list[int]:
    indices = [int(match) for match in re.findall(r"\[(\d+)\]", text)]
    return sorted(dict.fromkeys(indices))
