from collections.abc import Callable

from app.workflows.default_chat_workflow import run_default_chat_workflow
from app.workflows.rag_workflow import run_rag_workflow
from app.workflows.task_planning_workflow import run_task_planning_workflow
from app.workflows.workflow_result import WorkflowResult


WorkflowHandler = Callable[[str], WorkflowResult]


workflow_registry: dict[str, WorkflowHandler] = {
    "default_chat_workflow": run_default_chat_workflow,
    "task_planning_workflow": run_task_planning_workflow,
    "rag_workflow": run_rag_workflow,
}


def get_workflow(workflow_name: str) -> WorkflowHandler | None:
    return workflow_registry.get(workflow_name)
