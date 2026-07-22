from pathlib import Path
import json

from app.core.config import Settings
from app.schemas.site_crawlers import CreateSiteCrawlerTaskRequest
from app.site_crawlers.adapters import ExternalSiteCrawlerAdapter
from app.site_crawlers.registry import SiteCrawlerRegistry


def _adapter(tmp_path: Path, adapter_id: str = "zxxk") -> ExternalSiteCrawlerAdapter:
    executable_name = f"{adapter_id}-scrapling.exe"
    executable = tmp_path / ".venv" / "Scripts" / executable_name
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test")
    return ExternalSiteCrawlerAdapter(
        id=adapter_id,
        name=adapter_id,
        description="test",
        root=tmp_path,
        executable_name=executable_name,
        actions=("probe", "download"),
        capabilities=("download",),
    )


def test_adapter_builds_download_command_from_validated_parameters(tmp_path):
    adapter = _adapter(tmp_path)
    request = CreateSiteCrawlerTaskRequest(
        adapter_id="zxxk",
        action="download",
        limit=20,
        max_pages=50,
        max_verify_failures=2,
    )

    command = adapter.build_command(request)

    assert command[0].endswith("zxxk-scrapling.exe")
    assert command[1:] == [
        "download",
        "--limit",
        "20",
        "--max-pages",
        "50",
        "--max-verify-failures",
        "2",
    ]


def test_youtike_ignores_zxxk_only_verify_parameter(tmp_path):
    adapter = _adapter(tmp_path, "youtike")
    request = CreateSiteCrawlerTaskRequest(
        adapter_id="youtike",
        action="download",
        max_verify_failures=2,
    )

    assert "--max-verify-failures" not in adapter.build_command(request)


def test_registry_loads_trusted_site_manifest(tmp_path):
    crawler_root = tmp_path / "crawler"
    executable = crawler_root / ".venv" / "Scripts" / "school-scrapling.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test")
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "school.json").write_text(
        json.dumps(
            {
                "id": "school",
                "name": "School",
                "description": "School paper crawler",
                "root": str(crawler_root),
                "executable_name": "school-scrapling.exe",
                "actions": ["probe", "download"],
                "capabilities": ["OSS upload"],
            }
        ),
        encoding="utf-8",
    )

    registry = SiteCrawlerRegistry(
        Settings(_env_file=None, site_crawler_manifest_dir=manifest_dir)
    )

    adapter = registry.get("school")
    assert adapter is not None
    assert adapter.configured is True
    assert adapter.actions == ("probe", "download")
