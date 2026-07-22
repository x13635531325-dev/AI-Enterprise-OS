from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.model_health import router as model_health_router
from app.api.routes.crawls import router as crawls_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.runs import router as runs_router
from app.api.routes.site_crawlers import router as site_crawlers_router
from app.core.config import settings
from app.services.crawl_service import crawl_service
from app.services.site_crawler_service import site_crawler_service


@asynccontextmanager
async def lifespan(_app: FastAPI):
    crawl_service.recover_interrupted_jobs()
    site_crawler_service.recover_interrupted_tasks()
    yield


app = FastAPI(
    title="AI Enterprise OS API",
    description="Run-first backend API for AI workflow execution.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ai-enterprise-os-api",
        "version": app.version,
    }


app.include_router(runs_router, prefix="/api")
app.include_router(model_health_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(crawls_router, prefix="/api")
app.include_router(site_crawlers_router, prefix="/api")
