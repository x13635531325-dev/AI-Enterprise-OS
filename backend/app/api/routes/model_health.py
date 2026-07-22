from fastapi import APIRouter

from app.gateways.circuit_breaker import circuit_breaker
from app.gateways.circuit_breaker import model_circuit_key
from app.gateways.model_router import list_model_routes
from app.schemas.runs import ModelHealthResponse


router = APIRouter(prefix="/model-health", tags=["model-health"])


@router.get("", response_model=list[ModelHealthResponse])
def list_model_health():
    grouped_routes = {}

    for task_type, model_config in list_model_routes():
        key = model_circuit_key(model_config)
        grouped_routes.setdefault(key, {"model_config": model_config, "task_types": []})
        grouped_routes[key]["task_types"].append(task_type)

    health_items = []

    for key, route in grouped_routes.items():
        model_config = route["model_config"]
        state = circuit_breaker.get_state(key)
        circuit_state = "open" if state.is_open else "closed"

        health_items.append(
            ModelHealthResponse(
                key=key,
                provider=model_config.provider,
                model=model_config.model,
                status="open" if state.is_open else "healthy",
                circuit_state=circuit_state,
                failure_count=state.failure_count,
                failure_threshold=model_config.circuit_breaker_failure_threshold,
                task_types=route["task_types"],
                fallback_model=(
                    model_config.fallback.model
                    if model_config.fallback is not None
                    else None
                ),
            )
        )

    return health_items
