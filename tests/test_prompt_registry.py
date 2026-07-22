from app.schemas.knowledge import KnowledgeSearchResult
from app.services.prompt_registry import build_rag_grounded_prompt


def test_rag_grounded_prompt_includes_question_sources_and_version_metadata():
    result = KnowledgeSearchResult(
        chunk_id="chunk_policy",
        document_id="doc_policy",
        document_title="Enterprise RAG Policy",
        content="The approved RAG system must cite retrieved sources.",
        position=0,
        score=0.9,
        lexical_score=0.9,
        vector_score=0.8,
        reranker_score=0.7,
        retrieval_sources=["lexical", "vector", "reranker"],
    )

    rendered_prompt = build_rag_grounded_prompt(
        question="How should the RAG system answer?",
        search_results=[result],
    )

    assert "How should the RAG system answer?" in rendered_prompt.text
    assert "[1] Document: Enterprise RAG Policy" in rendered_prompt.text
    assert "Do not invent facts" in rendered_prompt.text
    assert rendered_prompt.metadata["prompt_name"] == "rag_grounded_answer"
    assert rendered_prompt.metadata["prompt_version"] == "v1"
    assert rendered_prompt.metadata["context_source_count"] == 1
    assert len(rendered_prompt.metadata["prompt_template_hash"]) == 12
