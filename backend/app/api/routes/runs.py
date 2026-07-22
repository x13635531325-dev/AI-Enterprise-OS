from fastapi import APIRouter, HTTPException

from app.schemas.runs import CreateRunRequest, RunListItemResponse, RunResponse
from app.services.run_service import run_service


router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
def create_run(request: CreateRunRequest):
    return run_service.create_run(request)


@router.get("", response_model=list[RunListItemResponse])
def list_runs():
    return run_service.list_runs()


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str):
    run = run_service.get_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return run
