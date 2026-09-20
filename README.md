# RTVE Local RAG

Asistente RAG local para consultar subtítulos de informativos de RTVE. El proyecto transforma subtítulos en fragmentos con metadatos temporales, los indexa vectorialmente en Qdrant y responde preguntas mediante Ollama. La API FastAPI devuelve respuestas fundamentadas en evidencias y publica trazas de cada consulta en LangSmith cuando la observabilidad está activada.

## Arquitectura

```text
Subtítulos RTVE
  -> ingesta, normalización y chunking temporal
  -> embeddings: qwen3-embedding:0.6b (Ollama local en WSL)
  -> Qdrant
  -> recuperación semántica + filtros por programa/fecha
  -> verificación de evidencia
  -> qwen3:8b (Ollama local en WSL)
  -> FastAPI /ask + citas
  -> LangSmith: trazas de la ejecución
```

### Componentes

| Componente | Función | Ejecución |
|---|---|---|
| FastAPI (`api`) | Expone el endpoint `/ask`, coordina recuperación, verificación y generación | Docker Compose, puerto 8000 |
| Qdrant | Almacena vectores y metadatos de los chunks | Docker Compose, puerto 6333 |
| Ollama | Genera embeddings y respuestas | Servicio local de WSL (`ollama.service`) |
| `qwen3-embedding:0.6b` | Modelo usado para indexar y consultar semánticamente | Ollama local |
| `qwen3:8b` | Modelo de generación de respuestas | Ollama local |
| LangSmith | Observabilidad de la ejecución RAG | Servicio SaaS opcional |
| MLflow | Tracking de experimentos/artefactos, si se configura correctamente | Docker Compose, puerto 5000 |

## Requisitos

- Docker Engine o Docker Desktop con integración WSL.
- Docker Compose v2.
- WSL con `systemd` habilitado.
- Ollama instalado en WSL.
- Modelos `qwen3-embedding:0.6b` y `qwen3:8b` disponibles en la instancia de Ollama de WSL.
- Python y entorno virtual local si se usarán los scripts de ingesta desde el host.

## Configuración inicial

### 1. Arrancar Ollama local

Comprueba el servicio:

```bash
sudo systemctl enable --now ollama
systemctl status ollama --no-pager
```

Para que los contenedores Docker puedan llegar a Ollama en WSL, el servicio debe escuchar fuera de `127.0.0.1`:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo ss -ltnp 'sport = :11434'
```

La última orden debe mostrar `*:11434` o `0.0.0.0:11434`.

### 2. Instalar y verificar modelos

```bash
ollama pull qwen3-embedding:0.6b
ollama pull qwen3:8b
ollama list
```

Comprueba la API local:

```bash
curl -fsS http://127.0.0.1:11434/api/tags | jq -r '.models[].name'
```

### 3. Configurar `.env`

Crea el archivo desde el ejemplo si todavía no existe:

```bash
cp .env.example .env
```

Docker debe apuntar a la IP actual de WSL, no a `host.docker.internal` si este nombre resuelve al Ollama de Windows:

```bash
WSL_IP="$(ip -4 route get 1.1.1.1 | awk '{for (i=1; i<=NF; i++) if ($i == "src") print $(i+1)}')"
sed -i "s|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://${WSL_IP}:11434|" .env
```

Variables relevantes:

```env
OLLAMA_BASE_URL=http://IP_DE_WSL:11434
QDRANT_URL=http://qdrant:6333
MLFLOW_TRACKING_URI=http://mlflow:5000
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=rtve-rag-local-dev
LANGSMITH_ENVIRONMENT=development
LANGSMITH_CONTENT_MODE=full
LANGSMITH_SAMPLE_RATE=1.0
```

No añadas `.env` al repositorio ni imprimas claves en consola.

## Activar el stack

### Arranque normal

```bash
cd ~/repo/rtve-local-rag
sudo systemctl start ollama
docker compose up -d
```

### Primer arranque o tras cambios de imagen

```bash
cd ~/repo/rtve-local-rag
sudo systemctl start ollama
docker compose up -d --build
```

### Comprobaciones de salud

```bash
docker compose ps
curl -fsS http://localhost:6333/collections | jq
curl -fsS http://localhost:8000/openapi.json | jq -r '.paths | keys[]'
curl -fsS http://127.0.0.1:11434/api/tags | jq -r '.models[].name'
```

Comprueba desde `api` la conectividad hacia Ollama y Qdrant:

```bash
docker compose exec -T api python - <<'PY'
import json
from urllib.request import urlopen
from rtve_rag.settings import get_settings

s = get_settings()
for name, url in {
    "qdrant": f"{s.qdrant_url.rstrip('/')}/collections",
    "ollama": f"{s.ollama_base_url.rstrip('/')}/api/tags",
}.items():
    with urlopen(url, timeout=20) as response:
        print(json.dumps({"service": name, "status": response.status}))
PY
```

## Usar la API

Consulta las rutas disponibles:

```bash
curl -fsS http://localhost:8000/openapi.json | jq -r '.paths | keys[]'
```

Ejemplo de consulta:

```bash
curl -sS -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "¿Qué información aportan los informativos indexados sobre la evolución de la inflación?",
    "top_k": 5
  }' | jq
```

Si el endpoint acepta filtros, añádelos al mismo JSON con `program` y/o `emission_date` según el contrato OpenAPI.

## LangSmith

El proyecto incorpora un tracer propio basado en `langsmith.run_trees.RunTree`. Para cada petición `/ask` crea una raíz `rtve-rag.ask` y spans para `retrieval`, `evidence_verification` y `answer_generation`.

### Activar

En `.env`:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_TU_CLAVE_PRIVADA
LANGSMITH_PROJECT=rtve-rag-local-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_ENVIRONMENT=development
LANGSMITH_CONTENT_MODE=full
```

Después:

```bash
docker compose up -d --force-recreate api
```

Lanza una consulta y abre el proyecto `rtve-rag-local-dev` en LangSmith. Debe aparecer un trace `rtve-rag.ask`.

### Desactivar

En `.env`:

```env
LANGSMITH_TRACING=false
```

Luego recrea la API:

```bash
docker compose up -d --force-recreate api
```

### Privacidad

Con la implementación actual, el tracer puede enviar a LangSmith la pregunta, candidatos recuperados, contexto, prompt, evidencias y respuesta. `LANGSMITH_CONTENT_MODE` se registra como metadato; no elimina contenido automáticamente. No actives trazas con material confidencial sin una política de redacción previa.

## Nuevas ingestas

El repositorio incluye scripts para ingesta completa, ingesta incremental e indexación:

```text
scripts/ingest.py
scripts/ingest_incremental.py
scripts/index_chunks.py
```

Antes de ejecutar una ingesta, consulta siempre los argumentos de la versión instalada:

```bash
python scripts/ingest.py --help
python scripts/ingest_incremental.py --help
python scripts/index_chunks.py --help
```

Flujo recomendado:

1. Descarga o coloca los subtítulos de RTVE en el directorio de entrada que requiera la CLI.
2. Ejecuta la ingesta para producir chunks JSONL con metadatos y timestamps.
3. Ejecuta el indexador para generar embeddings e insertar o actualizar los puntos en Qdrant.
4. Para nuevas tandas de subtítulos, usa la ingesta incremental: está diseñada para evitar reprocesar elementos ya indexados.
5. Valida la colección Qdrant y lanza consultas de control antes de dar por concluida la carga.

Ejemplo de patrón operativo —reemplaza los marcadores por los argumentos exactos mostrados por `--help`—:

```bash
python scripts/ingest.py <ruta_de_subtitulos> <opciones_de_salida>
python scripts/index_chunks.py <ruta_jsonl_de_chunks> <opciones_de_coleccion>

# Para cargas posteriores:
python scripts/ingest_incremental.py <ruta_de_subtitulos_nuevos> <opciones>
```

No mezcles en una misma colección embeddings de modelos distintos. Si cambias el modelo de embeddings o su dimensión, crea una colección nueva o reindexa el corpus completo.

## Evaluación

El proyecto incluye utilidades para evaluar recuperación, rangos y verificación de evidencia:

```bash
python scripts/evaluate_retrieval.py --help
python scripts/evaluate_evidence_verifier.py --help
python scripts/analyze_evaluation_ranks.py --help
```

Usa un conjunto de preguntas estable y compara en LangSmith:

- Relevancia de los chunks recuperados.
- Cobertura de la evidencia.
- Respuestas con y sin evidencia suficiente.
- Latencia por recuperación, verificación y generación.
- Impacto de `top_k`, filtros y prompt.

## Desactivar el stack

Detén solo los contenedores, preservando volúmenes de Qdrant:

```bash
docker compose stop
```

Para detener y eliminar los contenedores y la red, preservando por defecto los volúmenes nombrados:

```bash
docker compose down
```

Detén Ollama si no se va a utilizar:

```bash
sudo systemctl stop ollama
```

No ejecutes `docker compose down -v` salvo que desees borrar explícitamente los volúmenes del stack, incluido el almacenamiento vectorial de Qdrant.

## Resolución de problemas

### La API no llega a Ollama

```bash
WSL_IP="$(ip -4 route get 1.1.1.1 | awk '{for (i=1; i<=NF; i++) if ($i == "src") print $(i+1)}')"
echo "$WSL_IP"
curl -fsS "http://${WSL_IP}:11434/api/tags" | jq
```

Si la IP de WSL cambió, actualiza `OLLAMA_BASE_URL` en `.env` y recrea `api`.

### Error `model ... not found`

Instala el modelo en la misma instancia de Ollama a la que apunta `OLLAMA_BASE_URL`:

```bash
ollama pull qwen3-embedding:0.6b
ollama pull qwen3:8b
```

### Error de dimensión en Qdrant

Comprueba que el modelo de consulta es el mismo que el usado durante la indexación. El embedding validado de `qwen3-embedding:0.6b` tiene dimensión 1024 en esta instalación.

### No aparecen trazas en LangSmith

```bash
docker compose logs --tail=250 api \
  | grep -iE 'langsmith_disabled|langsmith_trace_failed|langsmith_trace_close_failed|langsmith_span_failed|langsmith_span_close_failed' \
  || true
```

Confirma que `LANGSMITH_TRACING=true`, que la clave está configurada y que la API fue recreada.
