# RTVE Local RAG

Asistente RAG local y fundamentado en evidencia para consultar subtítulos de informativos de RTVE. La generación y los embeddings se ejecutan mediante Ollama; Qdrant almacena chunks y metadatos; FastAPI expone la API.

## Estado

El proyecto incluye ingesta, normalización temporal, chunking, indexación idempotente, recuperación semántica, generación con citas, verificación de evidencia, evaluación y despliegue local mediante Docker.

La API no responde con conocimiento externo: solo genera una respuesta cuando el verificador encuentra evidencia material en los chunks recuperados. En caso contrario devuelve una abstención explícita.

## Inicio rápido

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

## API

Consulta el corpus con `POST /ask`:

```bash
curl -sS http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "¿Qué información hay disponible sobre Nepal?",
    "top_k": 4
  }' | jq
```

La respuesta incluye el texto generado, el estado de evidencia, el motivo de verificación y fuentes trazables:

```json
{
  "request_id": "b19a1d47-3e7b-4e60-a4e4-4bcb321dcf46",
  "answer": "En Nepal continúan las labores de reconstrucción tras las inundaciones. [1]",
  "has_direct_evidence": true,
  "confidence": "supported",
  "verification_reason": "El fragmento documenta la reconstrucción tras las inundaciones.",
  "sources": [
    {
      "source_number": 1,
      "program": "Telediario 1",
      "emission_date": "2026-09-03",
      "chunk_id": "rtve_telediario-1_2026-09-03_1500_es_0028_20d3a0d95427",
      "excerpt": "...",
      "score": 0.91
    }
  ],
  "citations": [
    "Telediario 1 — 2026-09-03 — rtve_telediario-1_2026-09-03_1500_es_0028_20d3a0d95427 — 00:00"
  ]
}
```

Cuando no hay resultados o los candidatos no responden suficientemente a la pregunta, la API se abstiene y no devuelve fuentes tangenciales:

```json
{
  "request_id": "d46b7f1c-4e68-4754-ae12-1459a4a90937",
  "answer": "No encuentro evidencia suficiente en el corpus indexado para responder a esta pregunta.",
  "has_direct_evidence": false,
  "confidence": "insufficient_evidence",
  "verification_reason": "No hay previsión para París.",
  "sources": [],
  "citations": []
}
```

Los filtros opcionales permiten limitar la consulta por programa o fecha de emisión:

```bash
curl -sS http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "¿Qué ocurrió en Nepal?",
    "top_k": 4,
    "program": "telediario-1",
    "emission_date": "2026-09-03"
  }' | jq
```

## Pruebas

```bash
pytest -q
```

## Adquisición de subtítulos

El descargador original se mantiene localmente durante el scaffold. Antes de incorporar o ejecutar descargas, revisa condiciones de uso de RTVE y conserva un ritmo de petición bajo. El corpus descargado no debe subirse al repositorio.
