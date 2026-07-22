from app.services.answer_evaluator import evaluate_expected_facts


def test_answer_eval_passes_when_all_expected_facts_are_present():
    metadata = evaluate_expected_facts(
        answer_text=(
            "Project Atlas uses authorization code ORCHID-742 "
            "and requires Platform Lead approval [1]."
        ),
        expected_facts=[
            "ORCHID-742",
            "Platform Lead",
        ],
        citation_guardrail_metadata={
            "citation_guardrail_passed": True,
        },
    )

    assert metadata["answer_eval_status"] == "passed"
    assert metadata["answer_eval_passed"] is True
    assert metadata["fact_coverage"] == 1.0
    assert metadata["matched_fact_count"] == 2
    assert metadata["missing_facts"] == []


def test_answer_eval_fails_when_expected_fact_is_missing():
    metadata = evaluate_expected_facts(
        answer_text="Project Atlas uses authorization code ORCHID-742 [1].",
        expected_facts=[
            "ORCHID-742",
            "Security Lead",
        ],
        citation_guardrail_metadata={
            "citation_guardrail_passed": True,
        },
    )

    assert metadata["answer_eval_status"] == "failed"
    assert metadata["answer_eval_passed"] is False
    assert metadata["fact_coverage"] == 0.5
    assert metadata["matched_facts"] == ["ORCHID-742"]
    assert metadata["missing_facts"] == ["Security Lead"]


def test_answer_eval_fails_when_citation_guardrail_failed():
    metadata = evaluate_expected_facts(
        answer_text="Project Atlas uses authorization code ORCHID-742.",
        expected_facts=["ORCHID-742"],
        citation_guardrail_metadata={
            "citation_guardrail_passed": False,
        },
    )

    assert metadata["answer_eval_status"] == "failed"
    assert metadata["answer_eval_passed"] is False
    assert metadata["fact_coverage"] == 1.0
    assert metadata["citation_guardrail_passed"] is False
