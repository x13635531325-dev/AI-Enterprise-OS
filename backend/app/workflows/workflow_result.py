from pydantic import BaseModel, Field

from app.schemas.runs import CitationResponse, SpanResponse, StepResponse


class WorkflowResult(BaseModel):
    steps: list[StepResponse]
    spans: list[SpanResponse]
    citations: list[CitationResponse] = Field(default_factory=list)

    @property
    def status(self) -> str:
        if any(step.status == "failed" for step in self.steps):
            return "failed"

        return "completed"
