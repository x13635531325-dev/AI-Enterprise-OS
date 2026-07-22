from pydantic import BaseModel, Field

from app.gateways.circuit_breaker import circuit_breaker
from app.gateways.circuit_breaker import model_circuit_key
from app.gateways.model_router import ModelConfig
from app.gateways.model_router import select_model
from app.gateways.providers.base import (
    ProviderError,
    ProviderRequestResult,
    ProviderResult,
)
from app.gateways.providers.deepseek_provider import call_deepseek_model
from app.gateways.providers.mock_provider import call_mock_model
from app.gateways.providers.openai_provider import call_openai_model
from app.schemas.runs import ModelCallResponse, ToolExecutionResponse, new_id


class ModelGatewayResult(BaseModel):
    text: str
    model_calls: list[ModelCallResponse]
    tool_calls: list[ToolExecutionResponse] = Field(default_factory=list)
    status: str = "completed"
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"

    @property
    def model_call(self) -> ModelCallResponse:
        return self.model_calls[-1]

    @property
    def latency_ms(self) -> int:
        return sum(model_call.latency_ms for model_call in self.model_calls)

    @property
    def metadata(self) -> dict[str, str | int | float]:
        return {
            "model": self.model_call.model,
            "provider": self.model_call.provider,
            "task_type": self.model_call.task_type,
            "latency_ms": self.latency_ms,
            "input_tokens": sum(call.input_tokens for call in self.model_calls),
            "output_tokens": sum(call.output_tokens for call in self.model_calls),
            "cost_usd": round(sum(call.cost_usd for call in self.model_calls), 6),
            "tool_call_count": len(self.tool_calls),
        }


def generate_text(prompt: str, task_type: str) -> ModelGatewayResult:
    model_config = select_model(task_type)
    model_calls = []
    circuit_key = model_circuit_key(model_config)

    if _should_short_circuit(model_config, circuit_key):
        model_calls.append(
            _build_model_call(
                model_config=model_config,
                task_type=task_type,
                attempt=0,
                status="skipped",
                circuit_state="open",
                error_type="circuit_open",
                error="Circuit breaker is open; primary model was skipped.",
            )
        )

        if model_config.fallback is None:
            return _failed_result(model_calls)

        fallback_result = _call_with_retries(
            model_config=model_config.fallback,
            prompt=prompt,
            task_type=task_type,
            model_calls=model_calls,
        )
        return _result_from_provider(fallback_result, model_calls)

    provider_result = _call_with_retries(
        model_config=model_config,
        prompt=prompt,
        task_type=task_type,
        model_calls=model_calls,
    )

    if provider_result is not None:
        return _result_from_provider(provider_result, model_calls)

    if model_config.fallback is not None:
        fallback_result = _call_with_retries(
            model_config=model_config.fallback,
            prompt=prompt,
            task_type=task_type,
            model_calls=model_calls,
        )
        return _result_from_provider(fallback_result, model_calls)

    return _failed_result(model_calls)


def _call_with_retries(
    model_config: ModelConfig,
    prompt: str,
    task_type: str,
    model_calls: list[ModelCallResponse],
) -> ProviderResult | None:
    max_attempts = model_config.retry_attempts + 1
    circuit_key = model_circuit_key(model_config)

    for attempt in range(1, max_attempts + 1):
        try:
            provider_result = _call_provider(
                model_config=model_config,
                prompt=prompt,
                task_type=task_type,
            )
        except ProviderError as error:
            model_calls.append(
                _build_model_call(
                    model_config=model_config,
                    task_type=task_type,
                    attempt=attempt,
                    status="failed",
                    latency_ms=error.latency_ms,
                    error_type=error.error_type,
                    retryable=error.retryable,
                    error=str(error),
                )
            )
            circuit_breaker.record_failure(
                circuit_key,
                model_config.circuit_breaker_failure_threshold,
            )

            if not _should_retry(
                retryable=error.retryable,
                attempt=attempt,
                max_attempts=max_attempts,
            ):
                break
        else:
            for request_result in provider_result.requests:
                model_calls.append(
                    _build_model_call(
                        model_config=model_config,
                        task_type=task_type,
                        attempt=attempt,
                        status="completed",
                        provider_request=request_result,
                    )
                )
            circuit_breaker.record_success(circuit_key)
            return provider_result

    return None


def _build_model_call(
    model_config: ModelConfig,
    task_type: str,
    attempt: int,
    status: str,
    provider_request: ProviderRequestResult | None = None,
    latency_ms: int = 0,
    circuit_state: str = "closed",
    error_type: str | None = None,
    retryable: bool = False,
    error: str | None = None,
) -> ModelCallResponse:
    input_tokens = provider_request.input_tokens if provider_request else 0
    output_tokens = provider_request.output_tokens if provider_request else 0
    cost_usd = round(
        (input_tokens / 1_000_000)
        * model_config.input_cost_per_1m_tokens_usd
        + (output_tokens / 1_000_000)
        * model_config.output_cost_per_1m_tokens_usd,
        6,
    )

    return ModelCallResponse(
        id=new_id("model_call"),
        provider=model_config.provider,
        model=model_config.model,
        task_type=task_type,
        attempt=attempt,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=provider_request.latency_ms if provider_request else latency_ms,
        cost_usd=cost_usd,
        output=provider_request.text if provider_request else None,
        circuit_state=circuit_state,
        error_type=error_type,
        retryable=retryable,
        error=error,
    )


def _should_retry(retryable: bool, attempt: int, max_attempts: int) -> bool:
    return retryable and attempt < max_attempts


def _should_short_circuit(model_config: ModelConfig, circuit_key: str) -> bool:
    return (
        model_config.circuit_breaker_failure_threshold > 0
        and circuit_breaker.is_open(circuit_key)
    )


def _call_provider(
    model_config: ModelConfig,
    prompt: str,
    task_type: str,
) -> ProviderResult:
    if model_config.provider == "mock":
        return call_mock_model(model_config, prompt, task_type)

    if model_config.provider == "openai":
        return call_openai_model(model_config, prompt, task_type)

    if model_config.provider == "deepseek":
        return call_deepseek_model(model_config, prompt, task_type)

    raise ProviderError(
        message=f"Unsupported model provider: {model_config.provider}",
        error_type="invalid_request",
        retryable=False,
    )


def _result_from_provider(
    provider_result: ProviderResult | None,
    model_calls: list[ModelCallResponse],
) -> ModelGatewayResult:
    if provider_result is None:
        return _failed_result(model_calls)

    return ModelGatewayResult(
        text=provider_result.text,
        model_calls=model_calls,
        tool_calls=provider_result.tool_calls,
    )


def _failed_result(
    model_calls: list[ModelCallResponse],
) -> ModelGatewayResult:
    error = model_calls[-1].error if model_calls else "Model call failed."
    return ModelGatewayResult(
        text="",
        model_calls=model_calls,
        status="failed",
        error=error,
    )
