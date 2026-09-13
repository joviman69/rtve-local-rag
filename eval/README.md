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

## Medición inicial

Para cada pregunta, registra al menos si uno de los `expected_chunk_ids` aparece entre los primeros `top_k` resultados (recall@k) y si la respuesta cita únicamente fuentes devueltas por recuperación.
