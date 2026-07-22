from typing import Literal

from pydantic import BaseModel

from app.tools.base import Tool


class CalculatorInput(BaseModel):
    operation: Literal["add", "subtract", "multiply", "divide"]
    left: float
    right: float


def calculate(arguments: CalculatorInput) -> dict[str, float | str]:
    if arguments.operation == "add":
        result = arguments.left + arguments.right
    elif arguments.operation == "subtract":
        result = arguments.left - arguments.right
    elif arguments.operation == "multiply":
        result = arguments.left * arguments.right
    else:
        if arguments.right == 0:
            raise ValueError("Cannot divide by zero.")
        result = arguments.left / arguments.right

    return {
        "operation": arguments.operation,
        "left": arguments.left,
        "right": arguments.right,
        "result": result,
    }


calculator_tool = Tool(
    name="calculator",
    description="Perform one safe arithmetic operation on two numbers.",
    input_model=CalculatorInput,
    handler=calculate,
)
