from dataclasses import dataclass, field

from app.schemas.runs import ModelErrorType, ToolExecutionResponse


@dataclass(frozen=True)
class ProviderRequestResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(frozen=True)
class ProviderResult:
    text: str
    requests: list[ProviderRequestResult]
    tool_calls: list[ToolExecutionResponse] = field(default_factory=list)

    @property
    def input_tokens(self) -> int:
        return sum(request.input_tokens for request in self.requests)

    @property
    def output_tokens(self) -> int:
        return sum(request.output_tokens for request in self.requests)

    @property
    def latency_ms(self) -> int:
        return sum(request.latency_ms for request in self.requests)


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        error_type: ModelErrorType,
        retryable: bool,
        latency_ms: int = 0,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.latency_ms = latency_ms
