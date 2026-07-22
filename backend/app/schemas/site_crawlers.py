from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


SiteCrawlerAction = Literal["probe", "inspect", "login", "download"]
SiteCrawlerTaskStatus = Literal[
    "queued",
    "running",
    "retrying",
    "completed",
    "paused",
    "failed",
    "cancelled",
]


class SiteCrawlerAdapterResponse(BaseModel):
    id: str
    name: str
    description: str
    configured: bool
    configuration_detail: str
    actions: list[SiteCrawlerAction]
    capabilities: list[str]


class CreateSiteCrawlerTaskRequest(BaseModel):
    adapter_id: str = Field(min_length=1, max_length=64)
    action: SiteCrawlerAction = "download"
    limit: int | None = Field(default=None, ge=1, le=10_000)
    max_pages: int | None = Field(default=None, ge=1, le=10_000)
    max_verify_failures: int | None = Field(default=None, ge=1, le=10)
    max_attempts: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def validate_action_parameters(self):
        if self.action != "download" and any(
            value is not None
            for value in (self.limit, self.max_pages, self.max_verify_failures)
        ):
            raise ValueError("Download limits can only be used with the download action.")
        return self


class SiteCrawlerTaskResponse(BaseModel):
    id: str
    adapter_id: str
    action: SiteCrawlerAction
    status: SiteCrawlerTaskStatus
    request: CreateSiteCrawlerTaskRequest
    attempts: int = 0
    max_attempts: int
    process_id: int | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    retry_at: str | None = None


class SiteCrawlerLogResponse(BaseModel):
    id: int
    task_id: str
    level: Literal["info", "warning", "error"]
    message: str
    created_at: str
