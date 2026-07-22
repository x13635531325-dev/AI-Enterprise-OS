from app.gateways.model_gateway import generate_text
from app.schemas.runs import SpanResponse, StepResponse, new_id
from app.workflows.workflow_result import WorkflowResult


def run_task_planning_workflow(user_input: str) -> WorkflowResult:
    task_plan = generate_text(user_input, task_type="task_plan")
    plan_summary = generate_text(user_input, task_type="plan_summary")

    steps = [
        StepResponse(
            id=new_id("step"),
            name="receive_user_input",
            status="completed",
            output=user_input,
        ),
        StepResponse(
            id=new_id("step"),
            name="create_task_plan",
            status=task_plan.status,
            output=task_plan.text,
            metadata=task_plan.metadata,
        ),
        StepResponse(
            id=new_id("step"),
            name="summarize_plan",
            status=plan_summary.status,
            output=plan_summary.text,
            metadata=plan_summary.metadata,
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
            name="create_task_plan",
            status=task_plan.status,
            latency_ms=task_plan.latency_ms,
            output=task_plan.text,
            error=task_plan.error,
            model_calls=task_plan.model_calls,
            tool_calls=task_plan.tool_calls,
        ),
        SpanResponse(
            id=new_id("span"),
            name="summarize_plan",
            status=plan_summary.status,
            latency_ms=plan_summary.latency_ms,
            output=plan_summary.text,
            error=plan_summary.error,
            model_calls=plan_summary.model_calls,
            tool_calls=plan_summary.tool_calls,
        ),
    ]

    return WorkflowResult(steps=steps, spans=spans)
