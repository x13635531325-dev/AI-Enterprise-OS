import json
from pathlib import Path

from pydantic import ValidationError

from app.core.config import Settings, settings
from app.site_crawlers.adapters import (
    ExternalSiteCrawlerAdapter,
    SiteCrawlerManifest,
)


class SiteCrawlerRegistry:
    def __init__(self, app_settings: Settings | None = None):
        current = app_settings or settings
        self._adapters = {
            "zxxk": ExternalSiteCrawlerAdapter(
                id="zxxk",
                name="学科网",
                description="安徽试卷专用爬虫，支持登录态、XHR 列表、真实文件下载和自动入库。",
                root=_resolved(current.zxxk_crawler_root),
                executable_name="zxxk-scrapling.exe",
                actions=("probe", "inspect", "login", "download"),
                capabilities=(
                    "持久登录会话",
                    "WAF/验证检测",
                    "ZIP 下载与解压",
                    "文件哈希去重",
                    "OSS 上传",
                    "业务数据库入库",
                ),
            ),
            "youtike": ExternalSiteCrawlerAdapter(
                id="youtike",
                name="优题课",
                description="优题课试卷专用爬虫，支持额度感知、已入库跳过和下载后自动导入。",
                root=_resolved(current.youtike_crawler_root),
                executable_name="youtike-scrapling.exe",
                actions=("probe", "download"),
                capabilities=(
                    "Cookie 会话",
                    "年份/地区筛选",
                    "额度感知",
                    "source_id 去重",
                    "OSS 上传",
                    "业务数据库入库",
                ),
            ),
        }
        self.load_errors: list[str] = []
        self._load_manifests(current.site_crawler_manifest_dir)

    def list(self) -> list[ExternalSiteCrawlerAdapter]:
        return list(self._adapters.values())

    def get(self, adapter_id: str) -> ExternalSiteCrawlerAdapter | None:
        return self._adapters.get(adapter_id)

    def _load_manifests(self, manifest_dir: Path) -> None:
        directory = manifest_dir.expanduser().resolve()
        if not directory.is_dir():
            return
        for manifest_path in sorted(directory.glob("*.json")):
            if manifest_path.name.endswith(".disabled.json"):
                continue
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = SiteCrawlerManifest.model_validate(payload)
                if manifest.id in self._adapters:
                    raise ValueError(f"Duplicate adapter id: {manifest.id}")
                self._adapters[manifest.id] = manifest.adapter()
            except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
                self.load_errors.append(f"{manifest_path.name}: {exc}")


def _resolved(path: Path | None) -> Path | None:
    return path.expanduser().resolve() if path else None
