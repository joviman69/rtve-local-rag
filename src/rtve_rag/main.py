import time
import uuid
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from qdrant_client import QdrantClient
from rtve_rag.citations import build_source_records, format_sources
from rtve_rag.evidence import verify_evidence
from rtve_rag.generation import generate
from rtve_rag.observability import LangSmithTracer, log_event
from rtve_rag.retrieval import search
from rtve_rag.settings import get_settings

app = FastAPI(title="RTVE Local RAG", version="0.5.0")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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


INSUFFICIENT_EVIDENCE_ANSWER = "No encuentro evidencia suficiente en el corpus indexado para responder a esta pregunta."


@app.get("/", include_in_schema=False)
def web_interface():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "chat_model": settings.ollama_chat_model, "embedding_model": settings.ollama_embedding_model}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    settings = get_settings()
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    tracer = LangSmithTracer(settings, request_id)
    trace_inputs = {"question": request.question, "top_k": request.top_k, "program": request.program, "emission_date": request.emission_date}
    with tracer.trace("rtve-rag.ask", trace_inputs) as root:
        try:
            retrieval_started = time.perf_counter()
            with tracer.span("retrieval", {"question": request.question, "top_k": request.top_k, "program": request.program, "emission_date": request.emission_date, "collection": settings.qdrant_collection}, "retriever") as span:
                results = search(request.question, QdrantClient(url=settings.qdrant_url), settings.qdrant_collection, settings.ollama_base_url, settings.ollama_embedding_model, request.top_k, request.program, request.emission_date)
                retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000)
                span["outputs"] = {"results": results, "candidate_count": len(results), "retrieval_ms": retrieval_ms}
            if not results:
                response = AskResponse(request_id=request_id, answer=INSUFFICIENT_EVIDENCE_ANSWER, has_direct_evidence=False, confidence="insufficient_evidence", verification_reason="no_retrieval_candidates", sources=[], citations=[])
                root["outputs"] = response.model_dump()
                log_event("ask_completed", request_id=request_id, retrieval_ms=retrieval_ms, total_ms=round((time.perf_counter() - started) * 1000), source_count=0, evidence="insufficient", reason="no_retrieval_candidates")
                return response
            verification_started = time.perf_counter()
            with tracer.span("evidence_verification", {"question": request.question, "candidates": results, "model": settings.ollama_chat_model}, "chain") as span:
                verification = verify_evidence(request.question, results, settings.ollama_base_url, settings.ollama_chat_model)
                verification_ms = round((time.perf_counter() - verification_started) * 1000)
                span["outputs"] = {"verification": verification, "verification_ms": verification_ms}
            relevant_ids = set(verification["relevant_chunk_ids"])
            evidence_results = [item for item in results if item.get("chunk_id") in relevant_ids]
            if not verification["has_direct_evidence"] or not evidence_results:
                response = AskResponse(request_id=request_id, answer=INSUFFICIENT_EVIDENCE_ANSWER, has_direct_evidence=False, confidence="insufficient_evidence", verification_reason=verification["reason"], sources=[], citations=[])
                root["outputs"] = response.model_dump()
                log_event("ask_completed", request_id=request_id, retrieval_ms=retrieval_ms, verification_ms=verification_ms, total_ms=round((time.perf_counter() - started) * 1000), source_count=0, evidence="insufficient", reason=verification["reason"])
                return response
            citations = format_sources(evidence_results)
            context = "\n".join(f"[{number}] {item.get('text', '')}" for number, item in enumerate(evidence_results, start=1))
            prompt = "Responde en español exclusivamente con el contexto. Cita toda afirmación factual con los marcadores [n] disponibles. Si el contexto no permite responder, dilo claramente.\n" f"Contexto:\n{context}\n\nPregunta: {request.question}"
            generation_started = time.perf_counter()
            with tracer.span("answer_generation", {"prompt": prompt, "context": context, "model": settings.ollama_chat_model, "sources": evidence_results}, "llm") as span:
                answer = generate(prompt, settings.ollama_base_url, settings.ollama_chat_model)
                generation_ms = round((time.perf_counter() - generation_started) * 1000)
                span["outputs"] = {"answer": answer, "generation_ms": generation_ms}
            sources = build_source_records(evidence_results)
            response = AskResponse(request_id=request_id, answer=answer, has_direct_evidence=True, confidence="supported", verification_reason=verification["reason"], sources=sources, citations=citations)
            root["outputs"] = response.model_dump()
            log_event("ask_completed", request_id=request_id, retrieval_ms=retrieval_ms, verification_ms=verification_ms, generation_ms=generation_ms, total_ms=round((time.perf_counter() - started) * 1000), source_count=len(sources), evidence="grounded", reason=verification["reason"])
            return response
        except Exception as error:
            root["outputs"] = {"error_type": type(error).__name__}
            log_event("ask_failed", request_id=request_id, total_ms=round((time.perf_counter() - started) * 1000), error_type=type(error).__name__)
            raise
