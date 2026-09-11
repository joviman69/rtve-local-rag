# Arquitectura

La primera versión separa adquisición, procesamiento, indexación, recuperación, generación y evaluación.

```text
Subtítulos SRT/VTT → normalización con tiempos → chunks + metadatos
→ embeddings locales Ollama → Qdrant → recuperación → Ollama → respuesta con citas
```

FastAPI expone la API. MLflow registra experimentos locales. LangSmith se permite solo en desarrollo y debe poder desactivarse por configuración.
