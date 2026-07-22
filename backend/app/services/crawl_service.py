from importlib.metadata import version
from pathlib import Path

from app.core.config import Settings, settings
from app.crawling.pipeline import CrawlOutputPipeline
from app.crawling.scrapling_runner import build_scrapling_spider
from app.schemas.crawls import (
    CreateCrawlRequest,
    CrawlCapabilitiesResponse,
    CrawlDestinationStatus,
    CrawlJobResponse,
)
from app.storage.crawl_repository import CrawlRepository


class CrawlConfigurationError(RuntimeError):
    pass


class CrawlService:
    def __init__(
        self,
        repository: CrawlRepository | None = None,
        app_settings: Settings | None = None,
    ):
        self.repository = repository or CrawlRepository()
        self.settings = app_settings or settings

    def create_job(self, request: CreateCrawlRequest) -> CrawlJobResponse:
        self._validate_destinations(request)
        return self.repository.create_job(request)

    def list_jobs(self) -> list[CrawlJobResponse]:
        return self.repository.list_jobs()

    def get_job(self, job_id: str) -> CrawlJobResponse | None:
        return self.repository.get_job(job_id)

    def retry_job(self, job_id: str) -> CrawlJobResponse | None:
        job = self.repository.get_job(job_id)
        if job is not None:
            self._validate_destinations(job.request)
        return self.repository.requeue(job_id)

    def recover_interrupted_jobs(self) -> int:
        return self.repository.recover_interrupted_jobs()

    def execute_job(self, job_id: str) -> None:
        job = self.repository.get_job(job_id)
        if job is None or job.status != "queued":
            return
        self.repository.mark_running(job_id)
        pipeline = CrawlOutputPipeline(
            settings=self.settings,
            repository=self.repository,
            request=job.request,
        )
        try:
            checkpoint_dir = Path(self.settings.crawl_checkpoint_dir) / job_id
            spider = build_scrapling_spider(
                job_id=job_id,
                request=job.request,
                item_handler=lambda page: pipeline.process_page(job_id, page),
                checkpoint_dir=checkpoint_dir,
            )
            result = spider.start()
            if spider.delivery_errors:
                raise RuntimeError(spider.delivery_errors[0])
            stats = result.stats.to_dict()
            if result.paused:
                self.repository.mark_paused(job_id, stats)
            else:
                self.repository.mark_completed(job_id, stats)
        except Exception as exc:
            self.repository.mark_failed(job_id, f"{type(exc).__name__}: {exc}")

    def capabilities(self) -> CrawlCapabilitiesResponse:
        return CrawlCapabilitiesResponse(
            scrapling_version=version("scrapling"),
            destinations=[
                CrawlDestinationStatus(
                    name="local",
                    configured=True,
                    detail="Local file storage is ready.",
                ),
                CrawlDestinationStatus(
                    name="oss",
                    configured=self.settings.oss_is_configured,
                    detail=(
                        "Alibaba Cloud OSS V2 is ready."
                        if self.settings.oss_is_configured
                        else "Set OSS credentials in backend/.env."
                    ),
                ),
                CrawlDestinationStatus(
                    name="mysql",
                    configured=self.settings.mysql_is_configured,
                    detail=(
                        "MySQL is ready."
                        if self.settings.mysql_is_configured
                        else "Set MySQL connection fields in backend/.env."
                    ),
                ),
            ],
            fetch_modes=["http", "dynamic", "stealth"],
            bucket_aliases=self.settings.oss_bucket_aliases,
        )

    def _validate_destinations(self, request: CreateCrawlRequest) -> None:
        if request.destinations.oss.enabled and not self.settings.oss_is_configured:
            raise CrawlConfigurationError(
                "Alibaba Cloud OSS is enabled but its credentials are not configured."
            )
        if request.destinations.mysql.enabled and not self.settings.mysql_is_configured:
            raise CrawlConfigurationError(
                "MySQL is enabled but its server connection is not configured."
            )


crawl_service = CrawlService()
