import json
from time import perf_counter
from typing import Any

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
from app.tools.base import failed_tool_result
from app.tools.registry import tool_registry


TASK_INSTRUCTIONS = {
    "chat": (
        "Answer the user's request clearly and directly. "
        "Use an available tool whenever it can provide an exact result, "
        "especially for arithmetic; do not calculate arithmetic yourself."
    ),
    "task_plan": "Create a practical, ordered execution plan for the user's task.",
    "plan_summary": "Summarize the task plan into a concise execution overview.",
    "rag_answer": (
        "Answer only from the supplied enterprise knowledge context. "
        "Use source markers such as [1]. If the context is insufficient, "
        "say that the available knowledge does not contain the answer."
    ),
}


def call_deepseek_model(
    model_config: ModelConfig,
    prompt: str,
    task_type: str,
) -> ProviderResult:
    if settings.deepseek_api_key is None:
        raise ProviderError(
            message="DEEPSEEK_API_KEY is not configured.",
            error_type="invalid_request",
            retryable=False,
        )

    client = OpenAI(
        api_key=settings.deepseek_api_key.get_secret_value(),
        base_url=settings.deepseek_base_url,
        timeout=settings.model_request_timeout_seconds,
    )
    started_at = perf_counter()
    request_results = []
    tool_results = []
    messages: list[Any] = [
        {
            "role": "system",
            "content": TASK_INSTRUCTIONS.get(
                task_type,
                "Complete the user's request.",
            ),
        },
        {"role": "user", "content": prompt},
    ]
    request_options = {
        "extra_body": {
            "thinking": {
                "type": (
                    "enabled"
                    if settings.deepseek_thinking_enabled
                    else "disabled"
                )
            }
        }
    }

    if settings.deepseek_thinking_enabled:
        request_options["reasoning_effort"] = "high"

    for _ in range(settings.max_tool_rounds):
        request_started_at = perf_counter()

        try:
            response = client.chat.completions.create(
                model=model_config.model,
                messages=messages,
                tools=tool_registry.definitions(),
                stream=False,
                **request_options,
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
        message = response.choices[0].message
        text = message.content or ""
        request_results.append(
            ProviderRequestResult(
                text=text,
                input_tokens=usage.prompt_tokens if usage is not None else 0,
                output_tokens=usage.completion_tokens if usage is not None else 0,
                latency_ms=_elapsed_ms(request_started_at),
            )
        )

        if not message.tool_calls:
            return ProviderResult(
                text=text,
                requests=request_results,
                tool_calls=tool_results,
            )

        messages.append(message)

        for tool_call in message.tool_calls:
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as error:
                tool_result = failed_tool_result(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.function.name,
                    arguments={},
                    error=f"Invalid tool arguments: {error}",
                )
            else:
                tool_result = tool_registry.execute(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.function.name,
                    arguments=arguments,
                )

            tool_results.append(tool_result)
            tool_content = (
                tool_result.output
                if tool_result.status == "completed"
                else json.dumps(
                    {"error": tool_result.error},
                    ensure_ascii=False,
                )
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_content,
                }
            )

    raise ProviderError(
        message=f"Maximum tool rounds exceeded: {settings.max_tool_rounds}",
        error_type="provider_error",
        retryable=False,
        latency_ms=_elapsed_ms(started_at),
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
