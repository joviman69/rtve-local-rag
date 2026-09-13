import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from qdrant_client import QdrantClient
from rtve_rag.evaluation import score_case, summarize, threshold_failures
from rtve_rag.query_normalization import normalize_query
from rtve_rag.retrieval import search
from rtve_rag.settings import get_settings

def unit_interval(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 1: raise argparse.ArgumentTypeError('El umbral debe estar entre 0 y 1.')
    return number

def main() -> None:
    parser = argparse.ArgumentParser(description='Evaluate RAG retrieval without calling the chat model.')
    parser.add_argument('--input', default='eval/questions.jsonl'); parser.add_argument('--output', default='eval/report.json'); parser.add_argument('--top-k', type=int, default=4)
    parser.add_argument('--min-recall', type=unit_interval); parser.add_argument('--min-mrr', type=unit_interval); parser.add_argument('--min-negative-accuracy', type=unit_interval); parser.add_argument('--normalize-query', action='store_true')
    args = parser.parse_args()
    cases = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    settings = get_settings(); client = QdrantClient(url=settings.qdrant_url); scored = []
    for case in cases:
        retrieval_query = normalize_query(case['question']) if args.normalize_query else case['question']
        results = search(case['question'], client, settings.qdrant_collection, settings.ollama_base_url, settings.ollama_embedding_model, args.top_k, case.get('program'), case.get('emission_date'), normalize=args.normalize_query)
        score = score_case(case, results)
        score['question'] = case['question']
        score['retrieval_query'] = retrieval_query
        scored.append(score)
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'input': args.input, 'top_k': args.top_k, 'query_normalization': args.normalize_query, 'embedding_model': settings.ollama_embedding_model, 'collection': settings.qdrant_collection, **summarize(scored)}
    failures = threshold_failures(report, args.min_recall, args.min_mrr, args.min_negative_accuracy)
    report['thresholds'] = {'min_recall': args.min_recall, 'min_mrr': args.min_mrr, 'min_negative_accuracy': args.min_negative_accuracy, 'passed': not failures, 'failures': failures}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('evaluated_cases', 'positive_cases', 'negative_cases', 'recall_at_k', 'mrr', 'negative_accuracy', 'total_accuracy')}, ensure_ascii=False))
    if failures: print(json.dumps({'threshold_failures': failures}, ensure_ascii=False), file=sys.stderr); raise SystemExit(1)

if __name__ == '__main__': main()
