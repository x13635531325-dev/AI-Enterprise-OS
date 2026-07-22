import json
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas.runs import ToolExecutionResponse


ToolHandler = Callable[[BaseModel], Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler

    def to_api_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }

    def execute(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResponse:
        started_at = perf_counter()

        try:
            validated_arguments = self.input_model.model_validate(arguments)
            value = self.handler(validated_arguments)
        except (ValidationError, ValueError) as error:
            return ToolExecutionResponse(
                tool_call_id=tool_call_id,
                tool_name=self.name,
                status="failed",
                arguments=arguments,
                error=str(error),
                latency_ms=_elapsed_ms(started_at),
            )

        return ToolExecutionResponse(
            tool_call_id=tool_call_id,
            tool_name=self.name,
            status="completed",
            arguments=arguments,
            output=_serialize_output(value),
            latency_ms=_elapsed_ms(started_at),
        )


def failed_tool_result(
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    error: str,
) -> ToolExecutionResponse:
    return ToolExecutionResponse(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        status="failed",
        arguments=arguments,
        error=error,
        latency_ms=0,
    )


def _serialize_output(value: Any) -> str:
    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False)


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))
