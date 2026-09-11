from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://ollama:11434"
    ollama_chat_model: str = "qwen3:8b"
    ollama_embedding_model: str = "qwen3-embedding:0.6b"
    ollama_num_ctx: int = 8192
    ollama_temperature: float = 0.2
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "rtve_subtitles"
    mlflow_tracking_uri: str = "http://mlflow:5000"
    mlflow_experiment_name: str = "rtve-rag-local"
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "rtve-rag-local-dev"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
