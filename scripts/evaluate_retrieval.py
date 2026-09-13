import argparse
import json
from pathlib import Path
from qdrant_client import QdrantClient
from rtve_rag.evaluation import score_case, summarize
from rtve_rag.retrieval import search
from rtve_rag.settings import get_settings

def main() -> None:
    parser = argparse.ArgumentParser(description='Evaluate RAG retrieval without calling the chat model.')
    parser.add_argument('--input', default='eval/questions.jsonl')
    parser.add_argument('--output', default='eval/report.json')
    parser.add_argument('--top-k', type=int, default=4)
    args = parser.parse_args()
    cases = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    scored = []
    for case in cases:
        results = search(case['question'], client, settings.qdrant_collection, settings.ollama_base_url, settings.ollama_embedding_model, args.top_k, case.get('program'), case.get('emission_date'))
        scored.append(score_case(case, results))
    report = {'input': args.input, 'top_k': args.top_k, **summarize(scored)}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('evaluated_cases', 'hits', 'recall_at_k', 'mrr')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
