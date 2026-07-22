from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from pydantic import BaseModel, Field, field_validator
from app.schemas.site_crawlers import (
    CreateSiteCrawlerTaskRequest,
    SiteCrawlerAction,
    SiteCrawlerAdapterResponse,
)


@dataclass(frozen=True)
class ExternalSiteCrawlerAdapter:
    id: str
    name: str
    description: str
    root: Path | None
    executable_name: str
    actions: tuple[SiteCrawlerAction, ...]
    capabilities: tuple[str, ...]

    @property
    def executable(self) -> Path | None:
        if self.root is None:
            return None
        executable = self.root / ".venv" / "Scripts" / self.executable_name
        return executable if executable.is_file() else None

    @property
    def configured(self) -> bool:
        return bool(self.root and self.root.is_dir() and self.executable)

    def response(self) -> SiteCrawlerAdapterResponse:
        if self.configured:
            detail = f"已连接：{self.root}"
        elif self.root is None:
            detail = "未配置爬虫项目路径"
        else:
            detail = f"未找到可执行文件：{self.root}"
        return SiteCrawlerAdapterResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            configured=self.configured,
            configuration_detail=detail,
            actions=list(self.actions),
            capabilities=list(self.capabilities),
        )

    def build_command(self, request: CreateSiteCrawlerTaskRequest) -> list[str]:
        if request.action not in self.actions:
            raise ValueError(f"Adapter {self.id} does not support {request.action}.")
        executable = self.executable
        if executable is None:
            raise RuntimeError(f"Adapter {self.id} is not configured.")

        command = [str(executable), request.action]
        if request.action != "download":
            return command
        if request.limit is not None:
            command.extend(["--limit", str(request.limit)])
        if request.max_pages is not None:
            command.extend(["--max-pages", str(request.max_pages)])
        if request.max_verify_failures is not None and self.id == "zxxk":
            command.extend(
                ["--max-verify-failures", str(request.max_verify_failures)]
            )
        return command


class SiteCrawlerManifest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    root: Path
    executable_name: str = Field(min_length=1, max_length=120)
    actions: list[SiteCrawlerAction] = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
            raise ValueError("Adapter id must be a lowercase safe identifier.")
        return value

    @field_validator("executable_name")
    @classmethod
    def validate_executable_name(cls, value: str) -> str:
        if Path(value).name != value or not value.lower().endswith(".exe"):
            raise ValueError("Executable name must be a Windows .exe basename.")
        return value

    def adapter(self) -> ExternalSiteCrawlerAdapter:
        return ExternalSiteCrawlerAdapter(
            id=self.id,
            name=self.name,
            description=self.description,
            root=self.root.expanduser().resolve(),
            executable_name=self.executable_name,
            actions=tuple(dict.fromkeys(self.actions)),
            capabilities=tuple(dict.fromkeys(self.capabilities)),
        )
