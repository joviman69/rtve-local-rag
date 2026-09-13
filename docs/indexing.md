# Indexación local

Con Ollama y Qdrant activos, indexa un JSONL procesado:

```bash
python -m rtve_rag.ingestion.indexer --input data/processed/rtve_17211243_es.jsonl
```

Opciones principales: `--qdrant-url`, `--collection`, `--ollama-url` y `--model`. La colección se crea usando la dimensión real del primer embedding y los puntos se actualizan mediante IDs deterministas.
