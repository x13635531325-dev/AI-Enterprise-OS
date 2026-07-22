from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check_returns_service_metadata():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-enterprise-os-api",
        "version": "0.1.0",
    }


def test_cors_preflight_allows_local_frontend_origin():
    response = client.options(
        "/api/runs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
