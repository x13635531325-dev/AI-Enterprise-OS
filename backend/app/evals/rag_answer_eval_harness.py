import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.services.answer_evaluator import evaluate_expected_facts


@dataclass(frozen=True)
class RagAnswerEvalCase:
    name: str
    question: str
    expected_facts: list[str]
    min_fact_coverage: float = 1.0


@dataclass(frozen=True)
class RagAnswerRunOutput:
    answer_text: str
    citation_guardrail_metadata: dict
    trace_metadata: dict | None = None


def load_rag_answer_golden_set(path: str | Path) -> list[RagAnswerEvalCase]:
    raw_data = json.loads(Path(path).read_text(encoding="utf-8"))

    return [
        RagAnswerEvalCase(
            name=item["name"],
            question=item["question"],
            expected_facts=item["expected_facts"],
            min_fact_coverage=item.get("min_fact_coverage", 1.0),
        )
        for item in raw_data["cases"]
    ]


def run_rag_answer_eval_harness(
    cases: list[RagAnswerEvalCase],
    run_case: Callable[[RagAnswerEvalCase], RagAnswerRunOutput],
) -> dict:
    results = []

    for case in cases:
        run_output = run_case(case)
        answer_eval = evaluate_expected_facts(
            answer_text=run_output.answer_text,
            expected_facts=case.expected_facts,
            citation_guardrail_metadata=run_output.citation_guardrail_metadata,
            min_fact_coverage=case.min_fact_coverage,
        )
        results.append(
            {
                "name": case.name,
                "question": case.question,
                "passed": answer_eval["answer_eval_passed"],
                "fact_coverage": answer_eval["fact_coverage"],
                "matched_facts": answer_eval["matched_facts"],
                "missing_facts": answer_eval["missing_facts"],
                "citation_guardrail_status": (
                    run_output.citation_guardrail_metadata.get(
                        "citation_guardrail_status"
                    )
                ),
                "trace_metadata": run_output.trace_metadata or {},
            }
        )

    passed_count = sum(1 for result in results if result["passed"])
    total_count = len(results)
    pass_rate = passed_count / total_count if total_count else 1.0

    return {
        "total_count": total_count,
        "passed_count": passed_count,
        "failed_count": total_count - passed_count,
        "pass_rate": round(pass_rate, 6),
        "results": results,
    }
