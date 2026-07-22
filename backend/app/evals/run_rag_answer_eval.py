import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import settings
from app.evals.rag_answer_eval_harness import (
    RagAnswerEvalCase,
    RagAnswerRunOutput,
    load_rag_answer_golden_set,
    run_rag_answer_eval_harness,
)
from app.schemas.knowledge import CreateDocumentRequest
from app.schemas.runs import CreateRunRequest, RunResponse
from app.services.knowledge_service import knowledge_service
from app.services.run_service import run_service
from app.storage.knowledge_repository import KnowledgeRepository
from app.storage.run_repository import RunRepository


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_GOLDEN_SET_PATH = EVAL_DIR / "golden_sets" / "rag_answer_golden_set.json"
DEFAULT_CORPUS_PATH = EVAL_DIR / "golden_sets" / "rag_eval_corpus.json"
DEFAULT_REPORT_DIR = EVAL_DIR / "reports"


def run_rag_answer_eval(
    golden_set_path: str | Path = DEFAULT_GOLDEN_SET_PATH,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    isolated: bool = True,
    model_provider: str | None = None,
    ci_mode: bool = False,
) -> dict:
    cases = load_rag_answer_golden_set(golden_set_path)

    if isolated:
        with TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            report = _run_isolated_eval(
                cases=cases,
                corpus_path=corpus_path,
                tmp_dir=tmp_dir,
                model_provider=model_provider,
                ci_mode=ci_mode,
            )
            return _with_eval_metadata(
                report=report,
                golden_set_path=golden_set_path,
                corpus_path=corpus_path,
                isolated=isolated,
                model_provider=model_provider,
                ci_mode=ci_mode,
            )

    report = _run_eval_against_current_database(cases, model_provider, ci_mode)
    return _with_eval_metadata(
        report=report,
        golden_set_path=golden_set_path,
        corpus_path=corpus_path,
        isolated=isolated,
        model_provider=model_provider,
        ci_mode=ci_mode,
    )


def load_eval_corpus(path: str | Path) -> list[CreateDocumentRequest]:
    raw_data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        CreateDocumentRequest(
            title=item["title"],
            content=item["content"],
            metadata=item.get("metadata", {}),
        )
        for item in raw_data["documents"]
    ]


def save_eval_report(report: dict, report_dir: str | Path = DEFAULT_REPORT_DIR) -> Path:
    target_dir = Path(report_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    metadata = report["eval_metadata"]
    timestamp = metadata["generated_at"].replace(":", "").replace("-", "")
    timestamp = timestamp.replace(".", "").replace("Z", "Z")
    filename = (
        f"rag_answer_eval_{timestamp}_"
        f"{metadata['model_provider']}_{metadata['golden_set']['version']}.json"
    )
    report_path = target_dir / filename
    report["eval_metadata"]["report_path"] = str(report_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def format_eval_summary(report: dict) -> str:
    metadata = report["eval_metadata"]
    golden_set = metadata["golden_set"]
    corpus = metadata["corpus"]
    reranker = metadata["reranker"]
    pass_rate_percent = report["pass_rate"] * 100
    failed_results = [
        result for result in report["results"] if not result["passed"]
    ]
    lines = [
        "RAG Answer Eval Summary",
        f"Generated: {metadata['generated_at']}",
        f"Model provider: {metadata['model_provider']}",
        f"Golden set: {golden_set['name']}@{golden_set['version']}",
        f"Corpus: {corpus['name']}@{corpus['version']}",
        (
            "Reranker: "
            f"{'enabled' if reranker['enabled'] else 'disabled'} "
            f"({reranker['model']})"
        ),
        (
            "Pass rate: "
            f"{pass_rate_percent:.2f}% "
            f"({report['passed_count']}/{report['total_count']} passed)"
        ),
    ]

    if metadata.get("report_path"):
        lines.append(f"Report: {metadata['report_path']}")

    if not failed_results:
        lines.append("Failed cases: none")
        return "\n".join(lines)

    lines.append("Failed cases:")

    for result in failed_results:
        missing_facts = _format_list(result["missing_facts"])
        lines.append(
            f"- {result['name']}: "
            f"coverage={result['fact_coverage']:.2f}, "
            f"missing_facts={missing_facts}, "
            f"citation={result['citation_guardrail_status']}"
        )

    return "\n".join(lines)


def build_rag_answer_run_output(run: RunResponse) -> RagAnswerRunOutput:
    generation_step = _find_step(run, "generate_grounded_answer")
    generation_span = _find_span(run, "generate_grounded_answer")
    retrieval_span = _find_span(run, "retrieve_knowledge")

    return RagAnswerRunOutput(
        answer_text=run.output or "",
        citation_guardrail_metadata=generation_step.metadata,
        trace_metadata={
            "run_id": run.id,
            "run_status": run.status,
            "prompt_version": generation_step.metadata.get("prompt_version"),
            "prompt_template_hash": generation_step.metadata.get(
                "prompt_template_hash"
            ),
            "retrieval": retrieval_span.metadata if retrieval_span else {},
            "generation": generation_span.metadata if generation_span else {},
            "metrics": run.metrics.model_dump(),
        },
    )


def _run_isolated_eval(
    cases: list[RagAnswerEvalCase],
    corpus_path: str | Path,
    tmp_dir: str,
    model_provider: str | None,
    ci_mode: bool,
) -> dict:
    original_run_repository = run_service.repository
    original_knowledge_repository = knowledge_service.repository
    original_embedding_service = knowledge_service.embedding_service
    original_reranker_service = knowledge_service.reranker_service

    try:
        db_path = str(Path(tmp_dir) / "rag_answer_eval.sqlite3")
        run_service.repository = RunRepository(db_path)
        knowledge_service.repository = KnowledgeRepository(db_path)
        if ci_mode:
            knowledge_service.embedding_service = DeterministicEvalEmbeddingService()
            knowledge_service.reranker_service = DeterministicEvalRerankerService()
        run_service.reset()
        knowledge_service.repository.reset()
        _seed_eval_corpus(corpus_path)
        return _run_eval_against_current_database(cases, model_provider, ci_mode)
    finally:
        run_service.repository = original_run_repository
        knowledge_service.repository = original_knowledge_repository
        knowledge_service.embedding_service = original_embedding_service
        knowledge_service.reranker_service = original_reranker_service


def _run_eval_against_current_database(
    cases: list[RagAnswerEvalCase],
    model_provider: str | None,
    ci_mode: bool = False,
) -> dict:
    original_model_provider = settings.model_provider
    original_reranker_enabled = settings.reranker_enabled

    if model_provider is not None:
        settings.model_provider = model_provider
    if ci_mode:
        settings.model_provider = "mock"
        settings.reranker_enabled = False

    try:
        return run_rag_answer_eval_harness(cases, _run_rag_eval_case)
    finally:
        settings.model_provider = original_model_provider
        settings.reranker_enabled = original_reranker_enabled


def _run_rag_eval_case(case: RagAnswerEvalCase) -> RagAnswerRunOutput:
    run = run_service.create_run(
        CreateRunRequest(
            input=case.question,
            workflow_name="rag_workflow",
        )
    )
    return build_rag_answer_run_output(run)


def _seed_eval_corpus(corpus_path: str | Path) -> None:
    for document in load_eval_corpus(corpus_path):
        knowledge_service.create_document(document)


def _with_eval_metadata(
    report: dict,
    golden_set_path: str | Path,
    corpus_path: str | Path,
    isolated: bool,
    model_provider: str | None,
    ci_mode: bool,
) -> dict:
    active_model_provider = (
        "mock" if ci_mode else model_provider or settings.model_provider
    )
    active_reranker_enabled = False if ci_mode else settings.reranker_enabled

    return {
        "eval_metadata": {
            "generated_at": _utc_now_iso(),
            "eval_type": "rag_answer_eval",
            "isolated": isolated,
            "ci_mode": ci_mode,
            "model_provider": active_model_provider,
            "models": {
                "deepseek_model": settings.deepseek_model,
                "openai_model": settings.openai_model,
            },
            "golden_set": _load_eval_file_metadata(golden_set_path),
            "corpus": _load_eval_file_metadata(corpus_path),
            "retrieval": {
                "embedding_model": settings.embedding_model,
                "embedding_local_files_only": settings.embedding_local_files_only,
                "hybrid_rrf_k": settings.hybrid_rrf_k,
                "hybrid_candidate_multiplier": (
                    settings.hybrid_candidate_multiplier
                ),
                "vector_min_similarity": settings.vector_min_similarity,
            },
            "reranker": {
                "enabled": active_reranker_enabled,
                "model": settings.reranker_model,
                "local_files_only": settings.reranker_local_files_only,
            },
        },
        **report,
    }


def _load_eval_file_metadata(path: str | Path) -> dict:
    resolved_path = Path(path)
    raw_data = json.loads(resolved_path.read_text(encoding="utf-8"))
    return {
        "name": raw_data.get("name"),
        "version": raw_data.get("version"),
        "description": raw_data.get("description"),
        "path": str(resolved_path),
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _format_list(values: list) -> str:
    return ", ".join(str(value) for value in values) if values else "-"


class DeterministicEvalEmbeddingService:
    model_name = "deterministic-eval-embedding"

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    def encode_query(self, query: str) -> list[float]:
        return self._encode(query)

    def _encode(self, text: str) -> list[float]:
        lowered = text.lower()
        features = [
            float(
                any(
                    term in lowered
                    for term in (
                        "atlas",
                        "orchid",
                        "authorization",
                        "code",
                        "approve",
                        "approval",
                        "platform",
                        "security",
                    )
                )
            ),
            float(
                any(
                    term in lowered
                    for term in ("annual", "leave", "twenty", "days", "paid")
                )
            ),
            0.1,
        ]
        norm = sum(value * value for value in features) ** 0.5
        return [value / norm for value in features]


class DeterministicEvalRerankerService:
    def rerank(self, query, results, top_k):
        return results[:top_k]


def _find_step(run: RunResponse, name: str):
    return next(step for step in run.steps if step.name == name)


def _find_span(run: RunResponse, name: str):
    if run.trace is None:
        return None

    return next(
        (span for span in run.trace.spans if span.name == name),
        None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline RAG answer eval.")
    parser.add_argument(
        "--golden-set",
        default=str(DEFAULT_GOLDEN_SET_PATH),
        help="Path to the RAG answer golden set JSON file.",
    )
    parser.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS_PATH),
        help="Path to the eval corpus JSON file.",
    )
    parser.add_argument(
        "--use-current-db",
        action="store_true",
        help="Evaluate against the current configured SQLite database.",
    )
    parser.add_argument(
        "--model-provider",
        choices=["mock", "deepseek", "openai"],
        default=None,
        help="Override MODEL_PROVIDER for this eval run.",
    )
    parser.add_argument(
        "--ci-mode",
        action="store_true",
        help=(
            "Use deterministic fake retrieval services and mock model routing "
            "for fast, offline CI quality gates."
        ),
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=1.0,
        help="Minimum pass rate required for a zero exit code.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory where eval report JSON files are saved.",
    )
    parser.add_argument(
        "--no-save-report",
        action="store_true",
        help="Print the report without saving it to disk.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only machine-readable JSON without the human summary.",
    )
    args = parser.parse_args()

    report = run_rag_answer_eval(
        golden_set_path=args.golden_set,
        corpus_path=args.corpus,
        isolated=not args.use_current_db,
        model_provider=args.model_provider,
        ci_mode=args.ci_mode,
    )

    if not args.no_save_report:
        save_eval_report(report, args.report_dir)

    if not args.json_only:
        print(format_eval_summary(report))
        print()

    print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report["pass_rate"] >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
