from time import perf_counter

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from app.core.config import settings
from app.gateways.model_router import ModelConfig
from app.gateways.providers.base import (
    ProviderError,
    ProviderRequestResult,
    ProviderResult,
)


TASK_INSTRUCTIONS = {
    "chat": "Answer the user's request clearly and directly.",
    "task_plan": "Create a practical, ordered execution plan for the user's task.",
    "plan_summary": "Summarize the task plan into a concise execution overview.",
}


def call_openai_model(
    model_config: ModelConfig,
    prompt: str,
    task_type: str,
) -> ProviderResult:
    if settings.openai_api_key is None:
        raise ProviderError(
            message="OPENAI_API_KEY is not configured.",
            error_type="invalid_request",
            retryable=False,
        )

    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.model_request_timeout_seconds,
    )
    started_at = perf_counter()

    try:
        response = client.responses.create(
            model=model_config.model,
            instructions=TASK_INSTRUCTIONS.get(task_type),
            input=prompt,
            store=False,
        )
    except APITimeoutError as error:
        raise _provider_error(error, "timeout", True, started_at) from error
    except RateLimitError as error:
        raise _provider_error(error, "rate_limit", True, started_at) from error
    except APIConnectionError as error:
        raise _provider_error(error, "provider_error", True, started_at) from error
    except (BadRequestError, AuthenticationError, PermissionDeniedError) as error:
        raise _provider_error(error, "invalid_request", False, started_at) from error
    except APIStatusError as error:
        retryable = error.status_code >= 500
        raise _provider_error(error, "provider_error", retryable, started_at) from error
    except OpenAIError as error:
        raise _provider_error(error, "provider_error", False, started_at) from error

    usage = response.usage

    return ProviderResult(
        text=response.output_text,
        requests=[
            ProviderRequestResult(
                text=response.output_text,
                input_tokens=usage.input_tokens if usage is not None else 0,
                output_tokens=usage.output_tokens if usage is not None else 0,
                latency_ms=_elapsed_ms(started_at),
            )
        ],
    )


def _provider_error(
    error: Exception,
    error_type: str,
    retryable: bool,
    started_at: float,
) -> ProviderError:
    return ProviderError(
        message=str(error),
        error_type=error_type,
        retryable=retryable,
        latency_ms=_elapsed_ms(started_at),
    )


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))
