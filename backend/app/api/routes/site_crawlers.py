from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.schemas.site_crawlers import (
    CreateSiteCrawlerTaskRequest,
    SiteCrawlerAdapterResponse,
    SiteCrawlerLogResponse,
    SiteCrawlerTaskResponse,
)
from app.services.site_crawler_service import (
    SiteCrawlerConfigurationError,
    site_crawler_service,
)


router = APIRouter(tags=["site-crawlers"])


@router.get("/site-crawlers", response_model=list[SiteCrawlerAdapterResponse])
def list_site_crawlers():
    return site_crawler_service.list_adapters()


@router.post(
    "/site-crawler-tasks",
    response_model=SiteCrawlerTaskResponse,
    status_code=202,
)
def create_site_crawler_task(
    request: CreateSiteCrawlerTaskRequest,
    background_tasks: BackgroundTasks,
):
    try:
        task = site_crawler_service.create_task(request)
    except SiteCrawlerConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(site_crawler_service.execute_task, task.id)
    return task


@router.get(
    "/site-crawler-tasks",
    response_model=list[SiteCrawlerTaskResponse],
)
def list_site_crawler_tasks():
    return site_crawler_service.list_tasks()


@router.get(
    "/site-crawler-tasks/{task_id}",
    response_model=SiteCrawlerTaskResponse,
)
def get_site_crawler_task(task_id: str):
    task = site_crawler_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Site crawler task not found")
    return task


@router.get(
    "/site-crawler-tasks/{task_id}/logs",
    response_model=list[SiteCrawlerLogResponse],
)
def list_site_crawler_logs(
    task_id: str,
    after_id: int = Query(default=0, ge=0),
):
    if site_crawler_service.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Site crawler task not found")
    return site_crawler_service.list_logs(task_id, after_id=after_id)


@router.post(
    "/site-crawler-tasks/{task_id}/retry",
    response_model=SiteCrawlerTaskResponse,
    status_code=202,
)
def retry_site_crawler_task(task_id: str, background_tasks: BackgroundTasks):
    existing = site_crawler_service.get_task(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Site crawler task not found")
    if existing.status not in {"paused", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Task cannot be retried yet")
    task = site_crawler_service.retry_task(task_id)
    background_tasks.add_task(site_crawler_service.execute_task, task.id)
    return task


@router.post(
    "/site-crawler-tasks/{task_id}/cancel",
    response_model=SiteCrawlerTaskResponse,
)
def cancel_site_crawler_task(task_id: str):
    task = site_crawler_service.cancel_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Site crawler task not found")
    return task
