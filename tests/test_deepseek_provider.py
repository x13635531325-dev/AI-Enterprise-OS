from types import SimpleNamespace

from pydantic import SecretStr

from app.core.config import settings
from app.gateways.model_router import ModelConfig
from app.gateways.providers import deepseek_provider


class FakeCompletions:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.responses)


def _response(content, tool_calls, input_tokens, output_tokens):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
        ),
    )


def test_deepseek_provider_executes_tool_loop(monkeypatch):
    tool_call = SimpleNamespace(
        id="call_test",
        function=SimpleNamespace(
            name="calculator",
            arguments='{"operation":"multiply","left":12,"right":8}',
        ),
    )
    completions = FakeCompletions(
        [
            _response("", [tool_call], 100, 20),
            _response("12 multiplied by 8 is 96.", None, 130, 12),
        ]
    )
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    monkeypatch.setattr(
        deepseek_provider,
        "OpenAI",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(settings, "deepseek_api_key", SecretStr("test-key"))
    monkeypatch.setattr(settings, "deepseek_thinking_enabled", False)

    model_config = ModelConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        latency_ms=0,
        input_cost_per_1m_tokens_usd=0.14,
        output_cost_per_1m_tokens_usd=0.28,
    )
    result = deepseek_provider.call_deepseek_model(
        model_config=model_config,
        prompt="Calculate 12 times 8.",
        task_type="chat",
    )

    assert result.text == "12 multiplied by 8 is 96."
    assert len(result.requests) == 2
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].status == "completed"
    assert '"result": 96.0' in result.tool_calls[0].output
    assert completions.requests[1]["messages"][-1]["role"] == "tool"
