import json

from app.tools.registry import tool_registry


def test_tool_registry_exposes_calculator_schema():
    definitions = tool_registry.definitions()

    assert len(definitions) == 1
    assert definitions[0]["type"] == "function"
    assert definitions[0]["function"]["name"] == "calculator"
    assert definitions[0]["function"]["parameters"]["type"] == "object"


def test_calculator_tool_executes_valid_arguments():
    result = tool_registry.execute(
        tool_call_id="tool_call_1",
        tool_name="calculator",
        arguments={"operation": "multiply", "left": 12, "right": 8},
    )

    assert result.status == "completed"
    assert json.loads(result.output)["result"] == 96


def test_calculator_tool_rejects_invalid_arguments():
    result = tool_registry.execute(
        tool_call_id="tool_call_2",
        tool_name="calculator",
        arguments={"operation": "divide", "left": 10, "right": 0},
    )

    assert result.status == "failed"
    assert result.error == "Cannot divide by zero."


def test_registry_rejects_unknown_tool():
    result = tool_registry.execute(
        tool_call_id="tool_call_3",
        tool_name="delete_everything",
        arguments={},
    )

    assert result.status == "failed"
    assert result.error == "Unknown tool: delete_everything"
