from app.evals.rag_answer_eval_harness import (
    RagAnswerEvalCase,
    RagAnswerRunOutput,
    load_rag_answer_golden_set,
    run_rag_answer_eval_harness,
)


def test_rag_answer_eval_harness_runs_cases_and_summarizes_results():
    cases = [
        RagAnswerEvalCase(
            name="atlas_release_code",
            question="What is the Project Atlas authorization code?",
            expected_facts=["ORCHID-742"],
        ),
        RagAnswerEvalCase(
            name="atlas_approval_missing_fact",
            question="Who must approve Project Atlas?",
            expected_facts=["Platform Lead", "Security Lead"],
        ),
    ]

    def run_case(case):
        if case.name == "atlas_release_code":
            return RagAnswerRunOutput(
                answer_text="Project Atlas uses authorization code ORCHID-742 [1].",
                citation_guardrail_metadata={
                    "citation_guardrail_status": "passed",
                    "citation_guardrail_passed": True,
                },
                trace_metadata={"prompt_version": "v1"},
            )

        return RagAnswerRunOutput(
            answer_text="Project Atlas requires Platform Lead approval [1].",
            citation_guardrail_metadata={
                "citation_guardrail_status": "passed",
                "citation_guardrail_passed": True,
            },
            trace_metadata={"prompt_version": "v1"},
        )

    report = run_rag_answer_eval_harness(cases, run_case)

    assert report["total_count"] == 2
    assert report["passed_count"] == 1
    assert report["failed_count"] == 1
    assert report["pass_rate"] == 0.5
    assert report["results"][0]["passed"] is True
    assert report["results"][1]["passed"] is False
    assert report["results"][1]["missing_facts"] == ["Security Lead"]
    assert report["results"][0]["trace_metadata"] == {"prompt_version": "v1"}


def test_rag_answer_eval_harness_loads_golden_set_file():
    cases = load_rag_answer_golden_set(
        "backend/app/evals/golden_sets/rag_answer_golden_set.json"
    )

    assert len(cases) == 3
    assert cases[0].name == "atlas_release_authorization_code"
    assert cases[0].expected_facts == ["ORCHID-742"]
    assert cases[0].min_fact_coverage == 1.0


def test_rag_answer_eval_harness_can_run_loaded_golden_set_cases():
    cases = load_rag_answer_golden_set(
        "backend/app/evals/golden_sets/rag_answer_golden_set.json"
    )

    answers_by_case_name = {
        "atlas_release_authorization_code": (
            "Project Atlas uses authorization code ORCHID-742 [1]."
        ),
        "atlas_release_approvers": (
            "Project Atlas requires Platform Lead and Security Lead approval [1]."
        ),
        "annual_leave_days": "Employees receive twenty days of annual leave [1].",
    }

    def run_case(case):
        return RagAnswerRunOutput(
            answer_text=answers_by_case_name[case.name],
            citation_guardrail_metadata={
                "citation_guardrail_status": "passed",
                "citation_guardrail_passed": True,
            },
            trace_metadata={"prompt_version": "v1"},
        )

    report = run_rag_answer_eval_harness(cases, run_case)

    assert report["total_count"] == 3
    assert report["passed_count"] == 3
    assert report["failed_count"] == 0
    assert report["pass_rate"] == 1.0
