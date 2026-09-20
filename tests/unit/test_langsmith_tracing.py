from types import SimpleNamespace
from rtve_rag.observability import LangSmithTracer


def settings(**overrides):
    values = {"langsmith_tracing": False, "langsmith_api_key": "", "langsmith_project": "test", "langsmith_environment": "test", "langsmith_content_mode": "full", "qdrant_collection": "collection", "ollama_embedding_model": "embedding", "ollama_chat_model": "chat"}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_disabled_tracer_is_noop():
    tracer = LangSmithTracer(settings(), "request-1")
    with tracer.trace("root", {"question": "hola"}) as root:
        with tracer.span("child", {"input": "value"}) as child:
            child["outputs"] = {"ok": True}
        root["outputs"] = {"ok": True}
    assert tracer.enabled is False


def test_sdk_import_failure_does_not_break(monkeypatch):
    import builtins
    original_import = builtins.__import__
    def blocked(name, *args, **kwargs):
        if name.startswith("langsmith"):
            raise ImportError("offline")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", blocked)
    tracer = LangSmithTracer(settings(langsmith_tracing=True, langsmith_api_key="key"), "request-2")
    assert tracer.enabled is False
