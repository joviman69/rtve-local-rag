# Evaluación RAG

`questions.jsonl` es el conjunto de evaluación versionado. Añade una línea JSON por pregunta con esta estructura:

```json
{"id":"eval-001","question":"Pregunta verificable","program":null,"emission_date":null,"expected_chunk_ids":["rtve_..."],"notes":"Criterio de relevancia"}
```

## Criterios

- Usa preguntas con respuesta verificable en el corpus.
- Indica `expected_chunk_ids` cuando se conozcan los fragmentos que deben recuperarse.
- Conserva filtros de programa y fecha cuando la pregunta los requiera.
- Separa el conjunto de evaluación de los documentos indexados; no lo uses como datos de ingestión.

## Ejecutar

Con Qdrant y el modelo de embeddings disponibles, ejecuta:

```bash
python scripts/evaluate_retrieval.py --input eval/questions.jsonl --output eval/report.json --top-k 4
```

El proceso no llama al modelo de chat. El informe contiene `recall_at_k`, la fracción de preguntas cuyo chunk esperado aparece en los resultados, y `mrr`, que premia que el chunk esperado aparezca en posiciones más altas. `eval/report.json` es un artefacto local: no se versiona como fuente de verdad del conjunto de evaluación.
