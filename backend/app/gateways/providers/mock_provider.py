from app.gateways.model_router import ModelConfig
from app.gateways.providers.base import (
    ProviderError,
    ProviderRequestResult,
    ProviderResult,
)


def call_mock_model(
    model_config: ModelConfig,
    prompt: str,
    task_type: str,
) -> ProviderResult:
    if model_config.should_fail:
        raise ProviderError(
            message=f"Primary model simulated {model_config.failure_error_type}",
            error_type=model_config.failure_error_type or "provider_error",
            retryable=model_config.failure_retryable,
            latency_ms=model_config.latency_ms,
        )

    text = _mock_text(prompt, task_type)

    return ProviderResult(
        text=text,
        requests=[
            ProviderRequestResult(
                text=text,
                input_tokens=max(1, len(prompt) // 2),
                output_tokens=max(1, len(text) // 2),
                latency_ms=model_config.latency_ms,
            )
        ],
    )


def _mock_text(prompt: str, task_type: str) -> str:
    if task_type == "chat":
        return (
            f"Received task: {prompt}. "
            "This is a mock chat result returned by the Model Gateway."
        )

    if task_type == "task_plan":
        return (
            "Task plan: understand the request, split it into steps, "
            f"then produce an execution suggestion. Original task: {prompt}"
        )

    if task_type == "plan_summary":
        return (
            "A basic task plan has been generated. Later we can connect a "
            "Planner Agent to create a more advanced plan."
        )

    if task_type == "rag_answer":
        lowered = prompt.lower()

        if "approve" in lowered and "platform lead" in lowered:
            return (
                "The Project Atlas production release requires approval from "
                "the Platform Lead and the Security Lead [1]."
            )

        if "authorization code" in lowered and "orchid-742" in lowered:
            return "Project Atlas uses authorization code ORCHID-742 [1]."

        if "annual leave" in lowered and "twenty days" in lowered:
            return "Employees receive twenty days of paid annual leave [1]."

        return (
            "The answer was generated from retrieved enterprise knowledge "
            "and includes source citations [1]."
        )

    return f"Model Gateway processed task: {prompt}"
