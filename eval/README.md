# Evaluación RAG

`questions.jsonl` contiene una línea JSON por pregunta.

```json
{"id":"eval-001","question":"Pregunta verificable","program":null,"emission_date":null,"expected_evidence":true,"expected_chunk_ids":["rtve_..."],"notes":"Criterio de relevancia"}
```

Para un caso negativo, usa `expected_evidence:false` y una lista vacía de chunks. Un negativo aprueba solo si retrieval no devuelve resultados; esto mide abstención del retrieval, no la calidad de la respuesta del LLM.

## Crear casos

```bash
python scripts/build_eval_cases.py --questions eval/candidate_questions.txt --output eval/questions.jsonl --top-k 4
```

Pulsa Enter en la selección de fuentes para guardar un caso negativo.

## Ejecutar

```bash
python scripts/evaluate_retrieval.py --input eval/questions.jsonl --output eval/report.json --top-k 4 --min-recall 0.80 --min-mrr 0.60 --min-negative-accuracy 0.80
```

Los casos positivos alimentan `recall_at_k` y `mrr`. Los negativos alimentan `negative_accuracy`. `total_accuracy` agrupa ambos tipos. El proceso escribe el informe y termina con código 1 si un umbral configurado no se cumple.
