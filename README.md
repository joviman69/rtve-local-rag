# RTVE Local RAG

Asistente RAG local y fundamentado en evidencia para consultar subtítulos de informativos de RTVE. La generación y los embeddings se ejecutarán mediante Ollama; Qdrant almacenará chunks y metadatos; FastAPI expondrá la API.

## Estado

El repositorio contiene el scaffold de la fase de preparación. La siguiente fase implementará la ingesta, normalización con tiempos, chunking e indexación idempotente.

## Principios

- No se envía el corpus completo al LLM.
- Toda respuesta factual debe incluir fuentes del corpus.
- Los secretos están fuera de Git: copia `.env.example` a `.env`.
- `data/raw`, subtítulos descargados, resultados y trazas locales no se versionan.

## Arranque de la base

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

La API inicial solo expone salud. La ingesta y RAG se añadirán de forma incremental y con pruebas.

## Adquisición de subtítulos

El descargador original se mantiene localmente durante el scaffold. Antes de incorporar o ejecutar descargas, revisa condiciones de uso de RTVE y conserva un ritmo de petición bajo. El corpus descargado no debe subirse al repositorio.
