from app.schemas.runs import (
    CreateRunRequest,
    RunListItemResponse,
    RunMetricsResponse,
    RunResponse,
    SpanResponse,
    StepResponse,
    TraceResponse,
    new_id,
)
from app.storage.run_repository import RunRepository
from app.workflows.workflow_registry import get_workflow


class RunService:
    def __init__(self):
        self.repository = RunRepository()

    def create_run(self, request: CreateRunRequest) -> RunResponse:
        run_id = new_id("run")
        workflow = get_workflow(request.workflow_name)

        if workflow is None:
            steps = [
                StepResponse(
                    id=new_id("step"),
                    name="select_workflow",
                    status="failed",
                    output=f"Unknown workflow: {request.workflow_name}",
                )
            ]
            trace = TraceResponse(
                id=new_id("trace"),
                status="failed",
                spans=[
                    SpanResponse(
                        id=new_id("span"),
                        name="select_workflow",
                        status="failed",
                        latency_ms=0,
                        error=f"Unknown workflow: {request.workflow_name}",
                    )
                ],
            )

            run = RunResponse(
                id=run_id,
                workflow_name=request.workflow_name,
                input=request.input,
                status="failed",
                output=None,
                steps=steps,
                trace=trace,
                metrics=_build_metrics(trace),
            )

            return self.repository.save_run(run)

        workflow_result = workflow(request.input)
        steps = workflow_result.steps
        trace = TraceResponse(
            id=new_id("trace"),
            status=workflow_result.status,
            spans=workflow_result.spans,
        )

        run = RunResponse(
            id=run_id,
            workflow_name=request.workflow_name,
            input=request.input,
            status=workflow_result.status,
            output=steps[-1].output,
            steps=steps,
            trace=trace,
            citations=workflow_result.citations,
            metrics=_build_metrics(trace),
        )

        return self.repository.save_run(run)

    def get_run(self, run_id: str) -> RunResponse | None:
        return self.repository.get_run(run_id)

    def list_runs(self) -> list[RunListItemResponse]:
        return self.repository.list_runs()

    def reset(self) -> None:
        self.repository.reset()


run_service = RunService()


def _build_metrics(trace: TraceResponse) -> RunMetricsResponse:
    model_calls = [
        model_call
        for span in trace.spans
        for model_call in span.model_calls
    ]
    total_input_tokens = sum(model_call.input_tokens for model_call in model_calls)
    total_output_tokens = sum(model_call.output_tokens for model_call in model_calls)
    tool_calls = [
        tool_call
        for span in trace.spans
        for tool_call in span.tool_calls
    ]

    return RunMetricsResponse(
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_tokens=total_input_tokens + total_output_tokens,
        total_latency_ms=sum(span.latency_ms for span in trace.spans),
        total_cost_usd=round(
            sum(model_call.cost_usd for model_call in model_calls),
            6,
        ),
        model_call_count=len(model_calls),
        failed_model_call_count=sum(
            1 for model_call in model_calls if model_call.status == "failed"
        ),
        retryable_failure_count=sum(
            1
            for model_call in model_calls
            if model_call.status == "failed" and model_call.retryable
        ),
        short_circuit_count=sum(
            1 for model_call in model_calls if model_call.status == "skipped"
        ),
        retry_count=sum(1 for model_call in model_calls if model_call.attempt > 1),
        tool_call_count=len(tool_calls),
        failed_tool_call_count=sum(
            1 for tool_call in tool_calls if tool_call.status == "failed"
        ),
    )
