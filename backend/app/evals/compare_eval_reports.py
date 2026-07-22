import argparse
import json
from pathlib import Path


def load_eval_report(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_eval_reports(baseline_report: dict, candidate_report: dict) -> dict:
    baseline_results = _results_by_name(baseline_report)
    candidate_results = _results_by_name(candidate_report)
    baseline_names = set(baseline_results)
    candidate_names = set(candidate_results)
    shared_names = sorted(baseline_names & candidate_names)
    added_cases = sorted(candidate_names - baseline_names)
    removed_cases = sorted(baseline_names - candidate_names)
    newly_failed_cases = [
        name
        for name in shared_names
        if baseline_results[name]["passed"] and not candidate_results[name]["passed"]
    ]
    newly_passed_cases = [
        name
        for name in shared_names
        if not baseline_results[name]["passed"] and candidate_results[name]["passed"]
    ]
    still_failed_cases = [
        name
        for name in shared_names
        if not baseline_results[name]["passed"] and not candidate_results[name]["passed"]
    ]
    pass_rate_delta = candidate_report["pass_rate"] - baseline_report["pass_rate"]

    return {
        "baseline": _report_identity(baseline_report),
        "candidate": _report_identity(candidate_report),
        "pass_rate_delta": round(pass_rate_delta, 6),
        "passed_count_delta": (
            candidate_report["passed_count"] - baseline_report["passed_count"]
        ),
        "failed_count_delta": (
            candidate_report["failed_count"] - baseline_report["failed_count"]
        ),
        "added_cases": added_cases,
        "removed_cases": removed_cases,
        "newly_failed_cases": [
            _case_change(name, baseline_results[name], candidate_results[name])
            for name in newly_failed_cases
        ],
        "newly_passed_cases": [
            _case_change(name, baseline_results[name], candidate_results[name])
            for name in newly_passed_cases
        ],
        "still_failed_cases": [
            _case_change(name, baseline_results[name], candidate_results[name])
            for name in still_failed_cases
        ],
    }


def format_eval_report_comparison(comparison: dict) -> str:
    pass_rate_delta = comparison["pass_rate_delta"] * 100
    lines = [
        "RAG Eval Report Comparison",
        (
            "Baseline: "
            f"{comparison['baseline']['generated_at']} "
            f"({comparison['baseline']['model_provider']})"
        ),
        (
            "Candidate: "
            f"{comparison['candidate']['generated_at']} "
            f"({comparison['candidate']['model_provider']})"
        ),
        f"Pass rate delta: {pass_rate_delta:+.2f}%",
        f"Passed count delta: {comparison['passed_count_delta']:+d}",
        f"Failed count delta: {comparison['failed_count_delta']:+d}",
        f"Added cases: {_format_names(comparison['added_cases'])}",
        f"Removed cases: {_format_names(comparison['removed_cases'])}",
        (
            "Newly passed: "
            f"{_format_case_changes(comparison['newly_passed_cases'])}"
        ),
        (
            "Newly failed: "
            f"{_format_case_changes(comparison['newly_failed_cases'])}"
        ),
        (
            "Still failed: "
            f"{_format_case_changes(comparison['still_failed_cases'])}"
        ),
    ]
    return "\n".join(lines)


def _results_by_name(report: dict) -> dict:
    return {result["name"]: result for result in report["results"]}


def _report_identity(report: dict) -> dict:
    metadata = report.get("eval_metadata", {})
    return {
        "generated_at": metadata.get("generated_at", "unknown"),
        "model_provider": metadata.get("model_provider", "unknown"),
        "report_path": metadata.get("report_path"),
        "pass_rate": report["pass_rate"],
        "passed_count": report["passed_count"],
        "failed_count": report["failed_count"],
        "total_count": report["total_count"],
    }


def _case_change(name: str, baseline_result: dict, candidate_result: dict) -> dict:
    return {
        "name": name,
        "baseline_passed": baseline_result["passed"],
        "candidate_passed": candidate_result["passed"],
        "baseline_fact_coverage": baseline_result["fact_coverage"],
        "candidate_fact_coverage": candidate_result["fact_coverage"],
        "baseline_missing_facts": baseline_result["missing_facts"],
        "candidate_missing_facts": candidate_result["missing_facts"],
        "baseline_citation_guardrail_status": (
            baseline_result["citation_guardrail_status"]
        ),
        "candidate_citation_guardrail_status": (
            candidate_result["citation_guardrail_status"]
        ),
    }


def _format_names(names: list[str]) -> str:
    return ", ".join(names) if names else "none"


def _format_case_changes(changes: list[dict]) -> str:
    if not changes:
        return "none"

    return ", ".join(change["name"] for change in changes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two RAG eval reports.")
    parser.add_argument("baseline_report", help="Path to the baseline report JSON.")
    parser.add_argument("candidate_report", help="Path to the candidate report JSON.")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only machine-readable JSON without the human summary.",
    )
    args = parser.parse_args()

    comparison = compare_eval_reports(
        load_eval_report(args.baseline_report),
        load_eval_report(args.candidate_report),
    )

    if not args.json_only:
        print(format_eval_report_comparison(comparison))
        print()

    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 1 if comparison["newly_failed_cases"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
