from app.evals.compare_eval_reports import (
    compare_eval_reports,
    format_eval_report_comparison,
)


def make_report(generated_at, pass_rate, passed_count, failed_count, results):
    return {
        "eval_metadata": {
            "generated_at": generated_at,
            "model_provider": "mock",
        },
        "total_count": len(results),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pass_rate": pass_rate,
        "results": results,
    }


def make_result(name, passed, coverage, missing_facts=None):
    return {
        "name": name,
        "question": f"Question for {name}",
        "passed": passed,
        "fact_coverage": coverage,
        "matched_facts": [],
        "missing_facts": missing_facts or [],
        "citation_guardrail_status": "passed",
        "trace_metadata": {},
    }


def test_compare_eval_reports_detects_case_regressions_and_fixes():
    baseline = make_report(
        generated_at="2026-07-10T10:00:00Z",
        pass_rate=0.5,
        passed_count=1,
        failed_count=1,
        results=[
            make_result("stable_pass", True, 1.0),
            make_result("fixed_later", False, 0.5, ["Security Lead"]),
            make_result("removed_case", True, 1.0),
        ],
    )
    candidate = make_report(
        generated_at="2026-07-10T11:00:00Z",
        pass_rate=0.5,
        passed_count=1,
        failed_count=1,
        results=[
            make_result("stable_pass", False, 0.5, ["ORCHID-742"]),
            make_result("fixed_later", True, 1.0),
            make_result("added_case", True, 1.0),
        ],
    )

    comparison = compare_eval_reports(baseline, candidate)

    assert comparison["pass_rate_delta"] == 0
    assert comparison["passed_count_delta"] == 0
    assert comparison["failed_count_delta"] == 0
    assert comparison["added_cases"] == ["added_case"]
    assert comparison["removed_cases"] == ["removed_case"]
    assert comparison["newly_failed_cases"][0]["name"] == "stable_pass"
    assert comparison["newly_failed_cases"][0]["candidate_missing_facts"] == [
        "ORCHID-742"
    ]
    assert comparison["newly_passed_cases"][0]["name"] == "fixed_later"
    assert comparison["still_failed_cases"] == []


def test_compare_eval_reports_detects_still_failed_cases():
    baseline = make_report(
        generated_at="2026-07-10T10:00:00Z",
        pass_rate=0.0,
        passed_count=0,
        failed_count=1,
        results=[
            make_result("still_bad", False, 0.5, ["Security Lead"]),
        ],
    )
    candidate = make_report(
        generated_at="2026-07-10T11:00:00Z",
        pass_rate=0.0,
        passed_count=0,
        failed_count=1,
        results=[
            make_result("still_bad", False, 0.5, ["Security Lead"]),
        ],
    )

    comparison = compare_eval_reports(baseline, candidate)

    assert comparison["still_failed_cases"][0]["name"] == "still_bad"


def test_format_eval_report_comparison_summarizes_changes():
    comparison = {
        "baseline": {
            "generated_at": "2026-07-10T10:00:00Z",
            "model_provider": "mock",
        },
        "candidate": {
            "generated_at": "2026-07-10T11:00:00Z",
            "model_provider": "deepseek",
        },
        "pass_rate_delta": 0.25,
        "passed_count_delta": 1,
        "failed_count_delta": -1,
        "added_cases": ["new_case"],
        "removed_cases": [],
        "newly_passed_cases": [{"name": "fixed_case"}],
        "newly_failed_cases": [{"name": "regressed_case"}],
        "still_failed_cases": [],
    }

    summary = format_eval_report_comparison(comparison)

    assert "RAG Eval Report Comparison" in summary
    assert "Pass rate delta: +25.00%" in summary
    assert "Passed count delta: +1" in summary
    assert "Failed count delta: -1" in summary
    assert "Added cases: new_case" in summary
    assert "Newly passed: fixed_case" in summary
    assert "Newly failed: regressed_case" in summary
