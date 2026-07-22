from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

from app.core.config import Settings
from app.crawling.models import ArtifactLocation


class AliyunOssSink:
    def __init__(
        self,
        settings: Settings,
        bucket_alias: str,
        client: Any | None = None,
        request_factory: Callable[..., Any] | None = None,
    ):
        self.settings = settings
        self.bucket_alias = bucket_alias
        self.bucket = settings.oss_bucket_aliases[bucket_alias]
        self.public_base_url = settings.oss_public_base_urls[bucket_alias]
        self._client = client
        self._request_factory = request_factory

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> ArtifactLocation:
        key = _normalize_object_key(object_key)
        client, request_factory = self._ensure_client()
        result = client.put_object(
            request_factory(
                bucket=self.bucket,
                key=key,
                body=data,
                content_type=content_type,
            )
        )
        public_url = None
        if self.public_base_url:
            public_url = f"{self.public_base_url.rstrip('/')}/{quote(key, safe='/')}"
        return ArtifactLocation(
            uri=f"oss://{self.bucket}/{key}",
            public_url=public_url,
            etag=getattr(result, "etag", None),
        )

    def _ensure_client(self) -> tuple[Any, Callable[..., Any]]:
        if self._client is not None and self._request_factory is not None:
            return self._client, self._request_factory
        if not self.settings.oss_is_configured:
            raise RuntimeError("Alibaba Cloud OSS credentials are not configured.")

        import alibabacloud_oss_v2 as oss

        credentials_provider = oss.credentials.StaticCredentialsProvider(
            access_key_id=self.settings.oss_access_key_id.get_secret_value(),
            access_key_secret=self.settings.oss_access_key_secret.get_secret_value(),
            security_token=(
                self.settings.oss_security_token.get_secret_value()
                if self.settings.oss_security_token
                else None
            ),
        )
        config = oss.config.load_default()
        config.credentials_provider = credentials_provider
        config.region = self.settings.oss_region
        config.endpoint = self.settings.oss_endpoint
        self._client = oss.Client(config)
        self._request_factory = oss.PutObjectRequest
        return self._client, self._request_factory


def _normalize_object_key(value: str) -> str:
    normalized = str(PurePosixPath(value.replace("\\", "/"))).lstrip("/")
    if not normalized or normalized == "." or ".." in PurePosixPath(normalized).parts:
        raise ValueError("Invalid OSS object key.")
    if len(normalized.encode("utf-8")) > 1023:
        raise ValueError("OSS object key exceeds 1,023 bytes.")
    return normalized
