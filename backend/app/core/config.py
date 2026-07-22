from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_provider: Literal["mock", "openai", "deepseek"] = "mock"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_input_cost_per_1m_tokens_usd: float = Field(default=0.14, ge=0)
    deepseek_output_cost_per_1m_tokens_usd: float = Field(default=0.28, ge=0)
    deepseek_thinking_enabled: bool = False
    max_tool_rounds: int = Field(default=4, ge=1, le=10)
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_local_files_only: bool = False
    hybrid_rrf_k: int = Field(default=60, ge=1)
    hybrid_candidate_multiplier: int = Field(default=4, ge=1, le=20)
    vector_min_similarity: float = Field(default=0.50, ge=-1, le=1)
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_local_files_only: bool = False
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_input_cost_per_1m_tokens_usd: float = Field(default=0.75, ge=0)
    openai_output_cost_per_1m_tokens_usd: float = Field(default=4.50, ge=0)
    model_request_timeout_seconds: float = Field(default=30, gt=0)
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    crawl_checkpoint_dir: Path = BACKEND_DIR / "data" / "crawl_checkpoints"
    crawl_local_storage_dir: Path = BACKEND_DIR / "data" / "crawl_exports"
    zxxk_crawler_root: Path | None = None
    youtike_crawler_root: Path | None = None
    site_crawler_manifest_dir: Path = BACKEND_DIR / "site_crawler_manifests"
    site_crawler_retry_base_delay_seconds: float = Field(default=5, ge=0, le=300)

    oss_access_key_id: SecretStr | None = None
    oss_access_key_secret: SecretStr | None = None
    oss_security_token: SecretStr | None = None
    oss_region: str = "cn-beijing"
    oss_endpoint: str = "https://oss-cn-beijing.aliyuncs.com"
    oss_default_bucket: str = "xuefangedufile"
    oss_content_bucket: str = "xuefangedu"
    oss_review_bucket: str = "xuefang-jiaoyan"
    oss_default_public_base_url: str | None = None
    oss_content_public_base_url: str | None = None
    oss_review_public_base_url: str | None = None

    mysql_host: str | None = None
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    mysql_user: str | None = None
    mysql_password: SecretStr | None = None
    mysql_database: str | None = None
    mysql_connect_timeout_seconds: int = Field(default=10, ge=1, le=120)
    mysql_ssl_ca: Path | None = None

    @field_validator(
        "openai_api_key",
        "deepseek_api_key",
        "oss_access_key_id",
        "oss_access_key_secret",
        "oss_security_token",
        "mysql_password",
        mode="before",
    )
    @classmethod
    def empty_api_key_is_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator(
        "mysql_ssl_ca",
        "zxxk_crawler_root",
        "youtike_crawler_root",
        mode="before",
    )
    @classmethod
    def empty_path_is_none(cls, value: str | Path | None) -> str | Path | None:
        return value or None

    @property
    def cors_allow_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]

    @property
    def oss_bucket_aliases(self) -> dict[str, str]:
        return {
            "default": self.oss_default_bucket,
            "content": self.oss_content_bucket,
            "review": self.oss_review_bucket,
        }

    @property
    def oss_public_base_urls(self) -> dict[str, str | None]:
        return {
            "default": self.oss_default_public_base_url,
            "content": self.oss_content_public_base_url,
            "review": self.oss_review_public_base_url,
        }

    @property
    def oss_is_configured(self) -> bool:
        return bool(self.oss_access_key_id and self.oss_access_key_secret)

    @property
    def mysql_is_configured(self) -> bool:
        return bool(
            self.mysql_host
            and self.mysql_user
            and self.mysql_password
            and self.mysql_database
        )


settings = Settings()
