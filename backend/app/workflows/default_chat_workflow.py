from app.gateways.model_gateway import generate_text
from app.schemas.runs import SpanResponse, StepResponse, new_id
from app.workflows.workflow_result import WorkflowResult


def run_default_chat_workflow(user_input: str) -> WorkflowResult:
    reply = generate_text(user_input, task_type="chat")

    steps = [
        StepResponse(
            id=new_id("step"),
            name="receive_user_input",
            status="completed",
            output=user_input,
        ),
        StepResponse(
            id=new_id("step"),
            name="generate_ai_reply",
            status=reply.status,
            output=reply.text,
            metadata=reply.metadata,
        ),
    ]

    spans = [
        SpanResponse(
            id=new_id("span"),
            name="receive_user_input",
            status="completed",
            latency_ms=5,
            output=user_input,
        ),
        SpanResponse(
            id=new_id("span"),
            name="generate_ai_reply",
            status=reply.status,
            latency_ms=reply.latency_ms,
            output=reply.text,
            error=reply.error,
            model_calls=reply.model_calls,
            tool_calls=reply.tool_calls,
        ),
    ]

    return WorkflowResult(steps=steps, spans=spans)
