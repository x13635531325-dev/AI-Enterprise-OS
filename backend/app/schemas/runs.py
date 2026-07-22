from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


RunStatus = Literal["queued", "running", "completed", "failed"]
StepStatus = Literal["pending", "running", "completed", "failed"]
TraceStatus = Literal["running", "completed", "failed"]
ModelCallStatus = Literal["completed", "failed", "skipped"]
ToolCallStatus = Literal["completed", "failed"]
ModelErrorType = Literal[
    "timeout",
    "rate_limit",
    "provider_error",
    "invalid_request",
    "circuit_open",
]
CircuitState = Literal["closed", "open"]
ModelHealthStatus = Literal["healthy", "open"]


class CreateRunRequest(BaseModel):
    input: str = Field(min_length=1)
    workflow_name: str = "default_chat_workflow"


class StepResponse(BaseModel):
    id: str
    name: str
    status: StepStatus
    output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelCallResponse(BaseModel):
    id: str
    provider: str
    model: str
    task_type: str
    attempt: int = 1
    status: ModelCallStatus
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float = 0
    output: str | None = None
    circuit_state: CircuitState = "closed"
    error_type: ModelErrorType | None = None
    retryable: bool = False
    error: str | None = None


class ToolExecutionResponse(BaseModel):
    tool_call_id: str
    tool_name: str
    status: ToolCallStatus
    arguments: dict
    output: str | None = None
    error: str | None = None
    latency_ms: int


class SpanResponse(BaseModel):
    id: str
    name: str
    status: StepStatus
    latency_ms: int
    output: str | None = None
    error: str | None = None
    model_calls: list[ModelCallResponse] = Field(default_factory=list)
    tool_calls: list[ToolExecutionResponse] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceResponse(BaseModel):
    id: str
    status: TraceStatus
    spans: list[SpanResponse]


class CitationResponse(BaseModel):
    index: int
    document_id: str
    document_title: str
    chunk_id: str
    excerpt: str


class RunMetricsResponse(BaseModel):
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: int = 0
    total_cost_usd: float = 0
    model_call_count: int = 0
    failed_model_call_count: int = 0
    retryable_failure_count: int = 0
    short_circuit_count: int = 0
    retry_count: int = 0
    tool_call_count: int = 0
    failed_tool_call_count: int = 0


class RunResponse(BaseModel):
    id: str
    workflow_name: str
    input: str
    status: RunStatus
    output: str | None = None
    created_at: str | None = None
    steps: list[StepResponse]
    trace: TraceResponse | None = None
    citations: list[CitationResponse] = Field(default_factory=list)
    metrics: RunMetricsResponse = Field(default_factory=RunMetricsResponse)


class RunListItemResponse(BaseModel):
    id: str
    workflow_name: str
    input: str
    status: RunStatus
    output: str | None = None
    created_at: str
    metrics: RunMetricsResponse


class ModelHealthResponse(BaseModel):
    key: str
    provider: str
    model: str
    status: ModelHealthStatus
    circuit_state: CircuitState
    failure_count: int
    failure_threshold: int
    task_types: list[str]
    fallback_model: str | None = None


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"
