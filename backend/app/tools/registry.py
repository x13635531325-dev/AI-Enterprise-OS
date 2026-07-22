from typing import Any

from app.schemas.runs import ToolExecutionResponse
from app.tools.base import Tool, failed_tool_result
from app.tools.calculator import calculator_tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool

    def definitions(self) -> list[dict[str, Any]]:
        return [tool.to_api_schema() for tool in self._tools.values()]

    def execute(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResponse:
        tool = self._tools.get(tool_name)

        if tool is None:
            return failed_tool_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments=arguments,
                error=f"Unknown tool: {tool_name}",
            )

        return tool.execute(tool_call_id, arguments)


tool_registry = ToolRegistry()
tool_registry.register(calculator_tool)
