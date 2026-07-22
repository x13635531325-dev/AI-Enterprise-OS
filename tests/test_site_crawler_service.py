from app.schemas.site_crawlers import CreateSiteCrawlerTaskRequest
from app.services.site_crawler_service import (
    classify_failure,
    extract_last_json_object,
    redact_log_line,
)
from app.storage.site_crawler_repository import SiteCrawlerRepository


def test_failure_classifier_pauses_on_verification_and_quota():
    verification = classify_failure("zxxk", 2, "")
    quota = classify_failure("zxxk", 4, "")

    assert verification.pause is True
    assert verification.retryable is False
    assert verification.code == "verification_required"
    assert quota.pause is True
    assert quota.code == "quota_exceeded"


def test_failure_classifier_retries_only_transient_network_errors():
    transient = classify_failure("youtike", 1, "connection timed out")
    unknown = classify_failure("youtike", 1, "parser changed")

    assert transient.retryable is True
    assert transient.pause is False
    assert unknown.retryable is False
    assert unknown.code == "crawler_failed"


def test_log_redaction_and_result_parsing():
    line = redact_log_line("COOKIE=session-secret API_KEY=key-secret")
    output = (
        'working\n{\n  "downloaded": 3, "failed": 0, '
        '"sample": [{"source_id": 42}]\n}\n'
    )

    assert "session-secret" not in line
    assert "key-secret" not in line
    assert extract_last_json_object(output) == {
        "downloaded": 3,
        "failed": 0,
        "sample": [{"source_id": 42}],
    }


def test_repository_persists_logs_and_recovers_interrupted_task(tmp_path):
    repository = SiteCrawlerRepository(str(tmp_path / "site-crawlers.sqlite3"))
    request = CreateSiteCrawlerTaskRequest(
        adapter_id="zxxk",
        action="download",
        limit=1,
    )
    task = repository.create_task(request)
    repository.mark_running(task.id, process_id=123, attempt=1)
    repository.append_log(task.id, "started")

    recovered_count = repository.recover_interrupted_tasks()
    recovered = repository.get_task(task.id)
    logs = repository.list_logs(task.id)

    assert recovered_count == 1
    assert recovered.status == "paused"
    assert recovered.error_code == "backend_restarted"
    assert recovered.process_id is None
    assert [log.message for log in logs] == ["started"]
