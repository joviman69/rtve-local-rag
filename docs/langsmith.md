# LangSmith: trazas completas de RTVE Local RAG

## Propósito

LangSmith se utiliza como observabilidad detallada de consultas RAG. MLflow conserva el papel de seguimiento local de experimentos y métricas agregadas.

La integración traza `POST /ask` y sus etapas de recuperación, verificación de evidencia y generación de respuesta.

## Configuración P3

Crear o actualizar `.env` sin versionarlo:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_TU_CLAVE_PRIVADA
LANGSMITH_PROJECT=rtve-rag-tfg-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_ENVIRONMENT=development
LANGSMITH_CONTENT_MODE=full
LANGSMITH_SAMPLE_RATE=1.0
```

`LANGSMITH_API_KEY` nunca debe añadirse a Git, documentación pública, vídeos o capturas de pantalla.

## Datos enviados

El modo `full` envía a LangSmith SaaS:

- Pregunta, filtros y `top_k`.
- Candidatos de Qdrant, textos, payloads y scores.
- Pregunta y candidatos del verificador, decisión, IDs seleccionados y razón.
- Contexto validado, prompt de respuesta, modelo y respuesta final.
- Fuentes, citas y latencias de cada etapa.

Solo debe usarse con corpus autorizado para salir del equipo. En este TFG se usa con datos públicos de subtítulos de RTVE.

## Trazas

Cada consulta crea:

```text
rtve-rag.ask
├── retrieval
├── evidence_verification
└── answer_generation
```

Todas las trazas incluyen `request_id`, entorno, colección Qdrant, modelos y modo de contenido. Las respuestas se etiquetan en el log local como `grounded` o `insufficient`.

## Activación

```bash
docker compose up -d --build
curl -fsS http://127.0.0.1:8000/health | jq
```

Realizar una consulta desde la interfaz web o con:

```bash
curl -sS http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"¿Qué información hay disponible sobre Nepal?","top_k":4}' | jq
```

Abrir el proyecto configurado en LangSmith y localizar la traza `rtve-rag.ask`.

## Desactivación

Para detener el envío de trazas sin cambiar código:

```env
LANGSMITH_TRACING=false
```

Reiniciar la API:

```bash
docker compose up -d --build
```

La API sigue funcionando si LangSmith está desactivado, falta la clave o el SaaS no responde.
