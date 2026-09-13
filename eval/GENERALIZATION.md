# Evaluación de generalización

Este flujo mide si retrieval conserva el mismo chunk relevante cuando la pregunta se formula de otra manera. No sustituye al conjunto de evaluación principal.

## Generar variantes revisadas

Parte de casos positivos que ya tienen ground truth en `eval/questions.jsonl`:

```bash
python scripts/build_generalization_cases.py --input eval/questions.jsonl --output eval/generalization.jsonl --variants-per-case 3
```

El script usa el modelo de chat local para proponer paráfrasis, pero exige aprobación humana antes de guardarlas. Rechaza una variante si altera entidades, fechas, filtros, alcance o presuposiciones de la pregunta original.

## Medir retrieval

```bash
python scripts/evaluate_retrieval.py --input eval/generalization.jsonl --output eval/generalization-report.json --top-k 4
```

Compara `recall_at_k` y `mrr` de este informe con el informe del conjunto base. Una caída indica sensibilidad a la formulación; investiga embeddings, chunking o recuperación híbrida antes de cambiar el modelo de chat.
