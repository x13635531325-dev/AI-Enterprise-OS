from dataclasses import dataclass
from hashlib import sha256

from app.schemas.knowledge import KnowledgeSearchResult


@dataclass(frozen=True)
class RenderedPrompt:
    text: str
    metadata: dict


RAG_GROUNDED_PROMPT_NAME = "rag_grounded_answer"
RAG_GROUNDED_PROMPT_VERSION = "v1"
RAG_GROUNDED_PROMPT_POLICY = "grounded_with_numbered_citations"

RAG_GROUNDED_PROMPT_TEMPLATE = (
    "Use only the enterprise knowledge sources below to answer the question. "
    "Cite supporting claims with [1], [2], and so on. "
    "Do not invent facts that are absent from the sources.\n\n"
    "Question:\n{question}\n\n"
    "Sources:\n{sources}"
)


def build_rag_grounded_prompt(
    question: str,
    search_results: list[KnowledgeSearchResult],
) -> RenderedPrompt:
    sources = "\n\n".join(
        (
            f"[{index}] Document: {result.document_title}\n"
            f"Content: {result.content}"
        )
        for index, result in enumerate(search_results, start=1)
    )
    text = RAG_GROUNDED_PROMPT_TEMPLATE.format(
        question=question,
        sources=sources,
    )

    return RenderedPrompt(
        text=text,
        metadata={
            "prompt_name": RAG_GROUNDED_PROMPT_NAME,
            "prompt_version": RAG_GROUNDED_PROMPT_VERSION,
            "prompt_policy": RAG_GROUNDED_PROMPT_POLICY,
            "prompt_template_hash": _template_hash(RAG_GROUNDED_PROMPT_TEMPLATE),
            "context_source_count": len(search_results),
            "citation_style": "numbered_brackets",
        },
    )


def _template_hash(template: str) -> str:
    return sha256(template.encode("utf-8")).hexdigest()[:12]
