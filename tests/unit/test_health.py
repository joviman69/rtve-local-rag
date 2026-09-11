from fastapi.testclient import TestClient

from rtve_rag.main import app


def test_health_returns_configured_models() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["chat_model"]
    assert body["embedding_model"]
