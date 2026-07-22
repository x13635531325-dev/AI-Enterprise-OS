from app.schemas.knowledge import KnowledgeSearchResult
from app.services.reranker_service import RerankerService


class FakeCrossEncoder:
    def predict(self, pairs):
        scores = []

        for _, content in pairs:
            lowered = content.lower()
            if "annual leave" in lowered or "twenty days" in lowered:
                scores.append(0.95)
            else:
                scores.append(0.12)

        return scores


class BrokenCrossEncoder:
    def predict(self, pairs):
        raise RuntimeError("reranker model is unavailable")


def make_result(title: str, content: str, score: float) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        chunk_id=f"chunk_{title.lower().replace(' ', '_')}",
        document_id=f"doc_{title.lower().replace(' ', '_')}",
        document_title=title,
        content=content,
        position=0,
        score=score,
        lexical_score=score,
        vector_score=0,
        retrieval_sources=["lexical"],
    )


def test_reranker_reorders_candidates_by_cross_encoder_score():
    service = RerankerService(
        model_name="fake-reranker",
        local_files_only=True,
        enabled=True,
    )
    service._model = FakeCrossEncoder()
    results = [
        make_result(
            title="Backup Policy",
            content="Production databases receive a full backup every Sunday.",
            score=0.9,
        ),
        make_result(
            title="Leave Policy",
            content="Employees receive twenty days of annual leave each year.",
            score=0.4,
        ),
    ]

    reranked = service.rerank(
        query="How much holiday is allowed?",
        results=results,
        top_k=1,
    )

    assert len(reranked) == 1
    assert reranked[0].document_title == "Leave Policy"
    assert reranked[0].reranker_score == 0.95
    assert reranked[0].score == 0.95
    assert reranked[0].retrieval_sources == ["lexical", "reranker"]


def test_disabled_reranker_keeps_existing_order_without_loading_model():
    service = RerankerService(
        model_name="fake-reranker",
        local_files_only=True,
        enabled=False,
    )
    results = [
        make_result(
            title="Backup Policy",
            content="Production databases receive a full backup every Sunday.",
            score=0.9,
        ),
        make_result(
            title="Leave Policy",
            content="Employees receive twenty days of annual leave each year.",
            score=0.4,
        ),
    ]

    reranked = service.rerank(
        query="How much holiday is allowed?",
        results=results,
        top_k=1,
    )

    assert len(reranked) == 1
    assert reranked[0].document_title == "Backup Policy"
    assert reranked[0].reranker_score == 0


def test_reranker_failure_falls_back_to_existing_order():
    service = RerankerService(
        model_name="fake-reranker",
        local_files_only=True,
        enabled=True,
    )
    service._model = BrokenCrossEncoder()
    results = [
        make_result(
            title="Backup Policy",
            content="Production databases receive a full backup every Sunday.",
            score=0.9,
        ),
        make_result(
            title="Leave Policy",
            content="Employees receive twenty days of annual leave each year.",
            score=0.4,
        ),
    ]

    reranked = service.rerank(
        query="How much holiday is allowed?",
        results=results,
        top_k=1,
    )

    assert len(reranked) == 1
    assert reranked[0].document_title == "Backup Policy"
    assert reranked[0].score == 0.9
