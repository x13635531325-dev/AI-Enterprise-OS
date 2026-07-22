from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.core.config import Settings
from app.crawling.models import ArtifactLocation


class LocalFileSink:
    def __init__(self, settings: Settings, directory: str):
        self.root = Path(settings.crawl_local_storage_dir).resolve()
        self.directory = PurePosixPath(directory)

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> ArtifactLocation:
        del content_type
        target = self._resolve_target(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex[:8]}.tmp")
        try:
            temporary.write_bytes(data)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return ArtifactLocation(uri=target.as_uri())

    def _resolve_target(self, object_key: str) -> Path:
        relative = Path(*self.directory.parts, *PurePosixPath(object_key).parts)
        target = (self.root / relative).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Local artifact path escapes the configured root.") from exc
        return target
