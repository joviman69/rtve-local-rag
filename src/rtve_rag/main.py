import time
import uuid
from fastapi import FastAPI
from pydantic import BaseModel
from qdrant_client import QdrantClient
from rtve_rag.citations import build_source_records, format_sources
from rtve_rag.evidence import verify_evidence
from rtve_rag.generation import generate
from rtve_rag.observability import log_event
from rtve_rag.retrieval import search
from rtve_rag.settings import get_settings

app = FastAPI(title="RTVE Local RAG", version="0.4.0")


class AskRequest(BaseModel):
    question: str
    top_k: int = 4
    program: str | None = None
    emission_date: str | None = None


class AskResponse(BaseModel):
    request_id: str
    answer: str
    has_direct_evidence: bool
    confidence: str
    verification_reason: str
    sources: list[dict]
    citations: list[str]


INSUFFICIENT_EVIDENCE_ANSWER = (
    "No encuentro evidencia suficiente en el corpus indexado para responder a esta pregunta."
)


@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "chat_model": settings.ollama_chat_model,
        "embedding_model": settings.ollama_embedding_model,
    }


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    settings = get_settings()
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    try:
        retrieval_started = time.perf_counter()
        results = search(
            request.question,
            QdrantClient(url=settings.qdrant_url),
            settings.qdrant_collection,
            settings.ollama_base_url,
            settings.ollama_embedding_model,
            request.top_k,
            request.program,
            request.emission_date,
        )
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000)

        if not results:
            log_event(
                "ask_completed",
                request_id=request_id,
                retrieval_ms=retrieval_ms,
                total_ms=round((time.perf_counter() - started) * 1000),
                source_count=0,
                evidence="insufficient",
                reason="no_retrieval_candidates",
            )
            return AskResponse(
                request_id=request_id,
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                has_direct_evidence=False,
                confidence="insufficient_evidence",
                verification_reason="no_retrieval_candidates",
                sources=[],
                citations=[],
            )

        verification = verify_evidence(
            request.question,
            results,
            settings.ollama_base_url,
            settings.ollama_chat_model,
        )
        relevant_ids = set(verification["relevant_chunk_ids"])
        evidence_results = [
            item for item in results if item.get("chunk_id") in relevant_ids
        ]

        if not verification["has_direct_evidence"] or not evidence_results:
            log_event(
                "ask_completed",
                request_id=request_id,
                retrieval_ms=retrieval_ms,
                total_ms=round((time.perf_counter() - started) * 1000),
                source_count=0,
                evidence="insufficient",
                reason=verification["reason"],
            )
            return AskResponse(
                request_id=request_id,
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                has_direct_evidence=False,
                confidence="insufficient_evidence",
                verification_reason=verification["reason"],
                sources=[],
                citations=[],
            )

        citations = format_sources(evidence_results)
        context = "\n".join(
            f"[{number}] {item.get('text', '')}"
            for number, item in enumerate(evidence_results, start=1)
        )
        answer = generate(
            "Responde en español exclusivamente con el contexto. "
            "Cita toda afirmación factual con los marcadores [n] disponibles. "
            "Si el contexto no permite responder, dilo claramente.\n"
            f"Contexto:\n{context}\n\nPregunta: {request.question}",
            settings.ollama_base_url,
            settings.ollama_chat_model,
        )
        sources = build_source_records(evidence_results)
        log_event(
            "ask_completed",
            request_id=request_id,
            retrieval_ms=retrieval_ms,
            total_ms=round((time.perf_counter() - started) * 1000),
            source_count=len(sources),
            evidence="grounded",
            reason=verification["reason"],
        )
        return AskResponse(
            request_id=request_id,
            answer=answer,
            has_direct_evidence=True,
            confidence="supported",
            verification_reason=verification["reason"],
            sources=sources,
            citations=citations,
        )
    except Exception as error:
        log_event(
            "ask_failed",
            request_id=request_id,
            total_ms=round((time.perf_counter() - started) * 1000),
            error_type=type(error).__name__,
        )
        raise
