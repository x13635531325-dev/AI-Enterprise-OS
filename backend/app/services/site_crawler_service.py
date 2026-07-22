from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, settings
from app.schemas.site_crawlers import (
    CreateSiteCrawlerTaskRequest,
    SiteCrawlerAdapterResponse,
    SiteCrawlerLogResponse,
    SiteCrawlerTaskResponse,
)
from app.site_crawlers.registry import SiteCrawlerRegistry
from app.storage.site_crawler_repository import (
    SiteCrawlerRepository,
    retry_at_after,
)


class SiteCrawlerConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FailureDecision:
    code: str
    message: str
    retryable: bool = False
    pause: bool = False


class SiteCrawlerService:
    def __init__(
        self,
        repository: SiteCrawlerRepository | None = None,
        registry: SiteCrawlerRegistry | None = None,
        app_settings: Settings | None = None,
    ):
        self.repository = repository or SiteCrawlerRepository()
        self.settings = app_settings or settings
        self.registry = registry or SiteCrawlerRegistry(self.settings)
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._processes_lock = threading.Lock()

    def list_adapters(self) -> list[SiteCrawlerAdapterResponse]:
        return [adapter.response() for adapter in self.registry.list()]

    def create_task(
        self, request: CreateSiteCrawlerTaskRequest
    ) -> SiteCrawlerTaskResponse:
        adapter = self.registry.get(request.adapter_id)
        if adapter is None:
            raise SiteCrawlerConfigurationError(
                f"Unknown site crawler adapter: {request.adapter_id}"
            )
        if request.action not in adapter.actions:
            raise SiteCrawlerConfigurationError(
                f"{adapter.name} does not support action {request.action}."
            )
        if not adapter.configured:
            raise SiteCrawlerConfigurationError(adapter.response().configuration_detail)
        return self.repository.create_task(request)

    def get_task(self, task_id: str) -> SiteCrawlerTaskResponse | None:
        return self.repository.get_task(task_id)

    def list_tasks(self) -> list[SiteCrawlerTaskResponse]:
        return self.repository.list_tasks()

    def list_logs(
        self, task_id: str, after_id: int = 0
    ) -> list[SiteCrawlerLogResponse]:
        return self.repository.list_logs(task_id, after_id=after_id)

    def retry_task(self, task_id: str) -> SiteCrawlerTaskResponse | None:
        return self.repository.requeue(task_id)

    def recover_interrupted_tasks(self) -> int:
        return self.repository.recover_interrupted_tasks()

    def cancel_task(self, task_id: str) -> SiteCrawlerTaskResponse | None:
        task = self.repository.get_task(task_id)
        if task is None:
            return None
        if task.status not in {"queued", "running", "retrying"}:
            return task
        with self._processes_lock:
            process = self._processes.get(task_id)
        if process is not None and process.poll() is None:
            process.terminate()
        self.repository.append_log(task_id, "用户已停止任务。", "warning")
        self.repository.mark_cancelled(task_id)
        return self.repository.get_task(task_id)

    def execute_task(self, task_id: str) -> None:
        task = self.repository.get_task(task_id)
        if task is None or task.status != "queued":
            return
        adapter = self.registry.get(task.adapter_id)
        if adapter is None or not adapter.configured or adapter.root is None:
            self.repository.mark_failed(
                task_id,
                "adapter_unavailable",
                "The configured site crawler is no longer available.",
            )
            return

        command = adapter.build_command(task.request)
        for attempt in range(1, task.max_attempts + 1):
            current = self.repository.get_task(task_id)
            if current is None or current.status == "cancelled":
                return
            self.repository.append_log(
                task_id,
                f"启动 {adapter.name} {task.action}，第 {attempt}/{task.max_attempts} 次尝试。",
            )
            try:
                exit_code, output, result = self._run_process(
                    task_id,
                    command,
                    cwd=str(adapter.root),
                    attempt=attempt,
                )
            except Exception as exc:
                exit_code = -1
                output = str(exc)
                result = {}
                self.repository.append_log(task_id, output, "error")

            current = self.repository.get_task(task_id)
            if current is None or current.status == "cancelled":
                return
            if exit_code == 0:
                self.repository.mark_completed(task_id, result)
                self.repository.append_log(task_id, "任务执行完成。")
                return

            decision = classify_failure(task.adapter_id, exit_code, output)
            self.repository.append_log(task_id, decision.message, "error")
            if decision.pause:
                self.repository.mark_paused(
                    task_id, decision.code, decision.message
                )
                return
            if not decision.retryable or attempt >= task.max_attempts:
                self.repository.mark_failed(
                    task_id, decision.code, decision.message
                )
                return

            delay = self.settings.site_crawler_retry_base_delay_seconds * (
                2 ** (attempt - 1)
            )
            retry_at = retry_at_after(delay)
            self.repository.mark_retrying(
                task_id, decision.code, decision.message, retry_at
            )
            self.repository.append_log(
                task_id,
                f"将在 {delay:g} 秒后自动重试。",
                "warning",
            )
            if self._wait_for_retry(task_id, delay):
                return

    def _run_process(
        self,
        task_id: str,
        command: list[str],
        *,
        cwd: str,
        attempt: int,
    ) -> tuple[int, str, dict[str, Any]]:
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        with self._processes_lock:
            self._processes[task_id] = process
        self.repository.mark_running(task_id, process.pid, attempt)

        output_lines: list[str] = []
        try:
            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = redact_log_line(raw_line.rstrip())
                    if not line:
                        continue
                    output_lines.append(line)
                    if len(output_lines) > 10_000:
                        output_lines.pop(0)
                    self.repository.append_log(task_id, line)
            exit_code = process.wait()
        finally:
            with self._processes_lock:
                self._processes.pop(task_id, None)

        output = "\n".join(output_lines)
        return exit_code, output, extract_last_json_object(output)

    def _wait_for_retry(self, task_id: str, delay: float) -> bool:
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline:
            current = self.repository.get_task(task_id)
            if current is None or current.status == "cancelled":
                return True
            time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        return False


def classify_failure(adapter_id: str, exit_code: int, output: str) -> FailureDecision:
    text = output.lower()
    if adapter_id == "zxxk":
        if exit_code in {2, 5}:
            return FailureDecision(
                "verification_required",
                "站点要求验证或扫码，任务已暂停，请完成人工验证后重试。",
                pause=True,
            )
        if exit_code == 4:
            return FailureDecision(
                "quota_exceeded",
                "站点当日下载额度已用完，任务已暂停。",
                pause=True,
            )
        if exit_code == 3:
            return FailureDecision(
                "import_failed",
                "文件已下载，但 OSS 或数据库导入失败。",
                retryable=True,
            )

    if re.search(r"登录失效|请先登录|login expired|unauthorized", text):
        return FailureDecision(
            "authentication_required",
            "站点登录态已失效，请重新登录后重试。",
            pause=True,
        )
    if re.search(r"验证码|人机验证|安全验证|captcha|waf|access denied", text):
        return FailureDecision(
            "verification_required",
            "检测到站点验证或风控，任务已暂停，不会继续高频重试。",
            pause=True,
        )
    if re.search(r"额度|限额|quota|upgrade vip", text):
        return FailureDecision(
            "quota_exceeded",
            "站点账号配额已用完，任务已暂停。",
            pause=True,
        )
    if re.search(
        r"timeout|timed out|connection|connect|temporarily unavailable|"
        r"http 5\d\d|network|reset by peer",
        text,
    ):
        return FailureDecision(
            "transient_network_error",
            "网络或站点临时异常，可以自动退避重试。",
            retryable=True,
        )
    if exit_code == -1:
        return FailureDecision(
            "process_start_failed",
            "爬虫进程无法启动，请检查项目路径和虚拟环境。",
        )
    return FailureDecision(
        "crawler_failed",
        f"爬虫退出码为 {exit_code}，未识别为可安全自动修复的错误。",
    )


def extract_last_json_object(output: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    result: dict[str, Any] = {}
    result_size = 0
    for index, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, end = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and end >= result_size:
            result = value
            result_size = end
    return result


def redact_log_line(line: str) -> str:
    return re.sub(
        r"(?i)(api[_-]?key|access[_-]?key|secret|password|cookie|token)"
        r"(\s*[:=]\s*)([^\s,;]+)",
        r"\1\2[REDACTED]",
        line,
    )


site_crawler_service = SiteCrawlerService()
