import json
import logging
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("rtve_rag")


def log_event(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


class LangSmithTracer:
    def __init__(self, settings: Any, request_id: str):
        self.settings = settings
        self.request_id = request_id
        self.root = None
        self.enabled = bool(
            getattr(settings, "langsmith_tracing", False)
            and getattr(settings, "langsmith_api_key", "")
        )
        self._run_tree = None
        if self.enabled:
            try:
                from langsmith.run_trees import RunTree
                self._run_tree = RunTree
            except Exception as error:
                self.enabled = False
                log_event("langsmith_disabled", request_id=request_id, error_type=type(error).__name__)

    def _extra(self) -> dict:
        return {"metadata": {"request_id": self.request_id, "environment": self.settings.langsmith_environment, "content_mode": self.settings.langsmith_content_mode, "collection": self.settings.qdrant_collection, "embedding_model": self.settings.ollama_embedding_model, "chat_model": self.settings.ollama_chat_model}, "tags": ["service:rtve-local-rag", "endpoint:ask", f"environment:{self.settings.langsmith_environment}", f"content-mode:{self.settings.langsmith_content_mode}"]}

    @contextmanager
    def trace(self, name: str, inputs: dict):
        state: dict = {}
        if not self.enabled:
            yield state
            return
        try:
            self.root = self._run_tree(name=name, run_type="chain", inputs=inputs, project_name=self.settings.langsmith_project, extra=self._extra())
            self.root.post()
        except Exception as error:
            self.root = None
            log_event("langsmith_trace_failed", request_id=self.request_id, error_type=type(error).__name__)
        try:
            yield state
        finally:
            if self.root is not None:
                try:
                    self.root.end(outputs=state.get("outputs", {}))
                    self.root.patch()
                except Exception as error:
                    log_event("langsmith_trace_close_failed", request_id=self.request_id, error_type=type(error).__name__)

    @contextmanager
    def span(self, name: str, inputs: dict, run_type: str = "chain"):
        state: dict = {}
        run = None
        if self.enabled and self.root is not None:
            try:
                run = self.root.create_child(name=name, run_type=run_type, inputs=inputs)
                run.post()
            except Exception as error:
                log_event("langsmith_span_failed", request_id=self.request_id, span=name, error_type=type(error).__name__)
        try:
            yield state
        finally:
            if run is not None:
                try:
                    run.end(outputs=state.get("outputs", {}))
                    run.patch()
                except Exception as error:
                    log_event("langsmith_span_close_failed", request_id=self.request_id, span=name, error_type=type(error).__name__)
