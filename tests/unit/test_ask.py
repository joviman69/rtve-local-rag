from types import SimpleNamespace
from fastapi.testclient import TestClient
import rtve_rag.main as main


def settings():
    return SimpleNamespace(
        qdrant_url="http://qdrant.test",
        qdrant_collection="rtve",
        ollama_base_url="http://ollama.test",
        ollama_embedding_model="embedding-test",
        ollama_chat_model="chat-test",
    )


def test_ask_returns_traceable_supported_response(monkeypatch):
    results = [
        {
            "chunk_id": "chunk-1",
            "program": "Telediario 1",
            "emission_date": "2026-09-03",
            "text": "Nepal mantiene labores de reconstrucción tras las inundaciones.",
            "score": 0.91,
        }
    ]
    monkeypatch.setattr(main, "get_settings", settings)
    monkeypatch.setattr(main, "search", lambda *args: results)
    monkeypatch.setattr(
        main,
        "verify_evidence",
        lambda *args: {
            "has_direct_evidence": True,
            "relevant_chunk_ids": ["chunk-1"],
            "reason": "El fragmento responde directamente.",
        },
    )
    monkeypatch.setattr(main, "generate", lambda *args: "Hay reconstrucción en Nepal. [1]")

    response = TestClient(main.app).post("/ask", json={"question": "¿Qué ocurre en Nepal?"})

    assert response.status_code == 200
    body = response.json()
    assert body["has_direct_evidence"] is True
    assert body["confidence"] == "supported"
    assert body["answer"] == "Hay reconstrucción en Nepal. [1]"
    assert body["verification_reason"] == "El fragmento responde directamente."
    assert body["sources"] == [
        {
            "source_number": 1,
            "program": "Telediario 1",
            "emission_date": "2026-09-03",
            "chunk_id": "chunk-1",
            "excerpt": "Nepal mantiene labores de reconstrucción tras las inundaciones.",
            "score": 0.91,
        }
    ]
    assert len(body["citations"]) == 1


def test_ask_abstains_when_verifier_rejects_candidates(monkeypatch):
    results = [{"chunk_id": "chunk-1", "text": "Hace calor en España."}]
    monkeypatch.setattr(main, "get_settings", settings)
    monkeypatch.setattr(main, "search", lambda *args: results)
    monkeypatch.setattr(
        main,
        "verify_evidence",
        lambda *args: {
            "has_direct_evidence": False,
            "relevant_chunk_ids": [],
            "reason": "No hay previsión para París.",
        },
    )
    monkeypatch.setattr(main, "generate", lambda *args: (_ for _ in ()).throw(AssertionError()))

    response = TestClient(main.app).post(
        "/ask", json={"question": "¿Qué tiempo hará mañana en París?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_direct_evidence"] is False
    assert body["confidence"] == "insufficient_evidence"
    assert body["verification_reason"] == "No hay previsión para París."
    assert body["sources"] == []
    assert body["citations"] == []


def test_ask_abstains_when_retrieval_returns_no_candidates(monkeypatch):
    monkeypatch.setattr(main, "get_settings", settings)
    monkeypatch.setattr(main, "search", lambda *args: [])

    response = TestClient(main.app).post("/ask", json={"question": "Pregunta sin contexto"})

    assert response.status_code == 200
    body = response.json()
    assert body["has_direct_evidence"] is False
    assert body["confidence"] == "insufficient_evidence"
    assert body["verification_reason"] == "no_retrieval_candidates"
    assert body["sources"] == []
    assert body["citations"] == []
