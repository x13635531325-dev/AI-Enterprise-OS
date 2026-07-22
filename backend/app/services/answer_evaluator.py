import re


def evaluate_expected_facts(
    answer_text: str,
    expected_facts: list[str],
    citation_guardrail_metadata: dict | None = None,
    min_fact_coverage: float = 1.0,
) -> dict:
    matched_facts = [
        fact for fact in expected_facts if _contains_fact(answer_text, fact)
    ]
    missing_facts = [
        fact for fact in expected_facts if fact not in matched_facts
    ]
    fact_coverage = (
        len(matched_facts) / len(expected_facts)
        if expected_facts
        else 1.0
    )
    citation_guardrail_passed = (
        True
        if citation_guardrail_metadata is None
        else bool(citation_guardrail_metadata.get("citation_guardrail_passed"))
    )
    passed = (
        fact_coverage >= min_fact_coverage
        and citation_guardrail_passed
    )

    return {
        "answer_eval_status": "passed" if passed else "failed",
        "answer_eval_passed": passed,
        "min_fact_coverage": min_fact_coverage,
        "fact_coverage": round(fact_coverage, 6),
        "expected_fact_count": len(expected_facts),
        "matched_fact_count": len(matched_facts),
        "matched_facts": matched_facts,
        "missing_facts": missing_facts,
        "citation_guardrail_passed": citation_guardrail_passed,
    }


def _contains_fact(answer_text: str, expected_fact: str) -> bool:
    return _normalize(expected_fact) in _normalize(answer_text)


def _normalize(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered).strip()
