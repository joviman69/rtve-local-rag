from fastapi import FastAPI
from pydantic import BaseModel

from rtve_rag.settings import get_settings

app = FastAPI(title="RTVE Local RAG", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    chat_model: str
    embedding_model: str


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        chat_model=settings.ollama_chat_model,
        embedding_model=settings.ollama_embedding_model,
    )
