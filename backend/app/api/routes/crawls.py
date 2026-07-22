from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.schemas.crawls import (
    CreateCrawlRequest,
    CrawlCapabilitiesResponse,
    CrawlJobResponse,
)
from app.services.crawl_service import CrawlConfigurationError, crawl_service


router = APIRouter(prefix="/crawls", tags=["crawls"])


@router.get("/capabilities", response_model=CrawlCapabilitiesResponse)
def get_crawl_capabilities():
    return crawl_service.capabilities()


@router.post("", response_model=CrawlJobResponse, status_code=202)
def create_crawl(request: CreateCrawlRequest, background_tasks: BackgroundTasks):
    try:
        job = crawl_service.create_job(request)
    except CrawlConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    background_tasks.add_task(crawl_service.execute_job, job.id)
    return job


@router.get("", response_model=list[CrawlJobResponse])
def list_crawls():
    return crawl_service.list_jobs()


@router.get("/{job_id}", response_model=CrawlJobResponse)
def get_crawl(job_id: str):
    job = crawl_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


@router.post("/{job_id}/retry", response_model=CrawlJobResponse, status_code=202)
def retry_crawl(job_id: str, background_tasks: BackgroundTasks):
    existing = crawl_service.get_job(job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    if existing.status not in {"failed", "paused"}:
        raise HTTPException(
            status_code=409,
            detail="Only failed or paused crawl jobs can be retried.",
        )
    try:
        job = crawl_service.retry_job(job_id)
    except CrawlConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    background_tasks.add_task(crawl_service.execute_job, job.id)
    return job
