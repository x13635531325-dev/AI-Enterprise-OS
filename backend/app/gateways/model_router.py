from pydantic import BaseModel

from app.core.config import settings


class ModelConfig(BaseModel):
    provider: str
    model: str
    latency_ms: int
    input_cost_per_1m_tokens_usd: float
    output_cost_per_1m_tokens_usd: float
    should_fail: bool = False
    failure_error_type: str | None = None
    failure_retryable: bool = False
    retry_attempts: int = 0
    circuit_breaker_failure_threshold: int = 0
    fallback: "ModelConfig | None" = None


DEFAULT_MODEL = ModelConfig(
    provider="mock",
    model="mock-chat-model-v1",
    latency_ms=120,
    input_cost_per_1m_tokens_usd=2,
    output_cost_per_1m_tokens_usd=2,
)


TASK_MODEL_MAP = {
    "chat": DEFAULT_MODEL,
    "task_plan": ModelConfig(
        provider="mock",
        model="mock-planner-model-v1",
        latency_ms=180,
        input_cost_per_1m_tokens_usd=10,
        output_cost_per_1m_tokens_usd=10,
        should_fail=True,
        failure_error_type="timeout",
        failure_retryable=True,
        retry_attempts=1,
        circuit_breaker_failure_threshold=2,
        fallback=ModelConfig(
            provider="mock",
            model="mock-planner-fallback-model-v1",
            latency_ms=140,
            input_cost_per_1m_tokens_usd=4,
            output_cost_per_1m_tokens_usd=4,
        ),
    ),
    "plan_summary": ModelConfig(
        provider="mock",
        model="mock-summary-model-v1",
        latency_ms=90,
        input_cost_per_1m_tokens_usd=1.5,
        output_cost_per_1m_tokens_usd=1.5,
    ),
    "rag_answer": ModelConfig(
        provider="mock",
        model="mock-rag-model-v1",
        latency_ms=150,
        input_cost_per_1m_tokens_usd=3,
        output_cost_per_1m_tokens_usd=3,
    ),
}


def select_model(task_type: str) -> ModelConfig:
    return _active_model_routes().get(task_type, DEFAULT_MODEL)


def list_model_routes() -> list[tuple[str, ModelConfig]]:
    active_routes = _active_model_routes()
    routes = [
        (task_type, model_config)
        for task_type, model_config in active_routes.items()
    ]

    for task_type, model_config in active_routes.items():
        if model_config.fallback is not None:
            routes.append((f"{task_type}:fallback", model_config.fallback))

    return routes


def _active_model_routes() -> dict[str, ModelConfig]:
    if settings.model_provider == "mock":
        return TASK_MODEL_MAP

    if settings.model_provider == "deepseek":
        deepseek_model = ModelConfig(
            provider="deepseek",
            model=settings.deepseek_model,
            latency_ms=0,
            input_cost_per_1m_tokens_usd=(
                settings.deepseek_input_cost_per_1m_tokens_usd
            ),
            output_cost_per_1m_tokens_usd=(
                settings.deepseek_output_cost_per_1m_tokens_usd
            ),
            retry_attempts=1,
            circuit_breaker_failure_threshold=3,
        )

        return {
            task_type: deepseek_model
            for task_type in TASK_MODEL_MAP
        }

    openai_model = ModelConfig(
        provider="openai",
        model=settings.openai_model,
        latency_ms=0,
        input_cost_per_1m_tokens_usd=settings.openai_input_cost_per_1m_tokens_usd,
        output_cost_per_1m_tokens_usd=settings.openai_output_cost_per_1m_tokens_usd,
        retry_attempts=1,
        circuit_breaker_failure_threshold=3,
    )

    return {
        task_type: openai_model
        for task_type in TASK_MODEL_MAP
    }
