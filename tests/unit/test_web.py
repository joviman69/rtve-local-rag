from fastapi.testclient import TestClient
from rtve_rag.main import app


def test_web_interface_is_served():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "RTVE Local RAG" in response.text
    assert 'id="ask-form"' in response.text
    assert "fetch('/ask'" in response.text
    assert "Fuentes verificadas" in response.text
