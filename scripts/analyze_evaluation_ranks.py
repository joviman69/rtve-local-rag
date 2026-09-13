import argparse
import json
from pathlib import Path

def load_jsonl(path: Path, key: str) -> dict[str, dict]:
    items = {}
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if key not in item:
            raise ValueError(f'Falta {key!r} en {path}, línea {line_number}.')
        items[item[key]] = item
    return items

def show_chunk(label: str, chunk: dict | None, max_chars: int) -> None:
    if chunk is None:
        print(f'{label}: no encontrado en chunks.jsonl')
        return
    text = ' '.join(chunk.get('text', '').split())
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + '…'
    print(f'{label}: {chunk.get("chunk_id")}')
    print(f'  programa={chunk.get("program")} fecha={chunk.get("emission_date")} inicio={chunk.get("start_ms")}ms fin={chunk.get("end_ms")}ms')
    print(f'  texto: {text}')

def main() -> None:
    parser = argparse.ArgumentParser(description='Show expected and retrieved chunk text for evaluation ranks.')
    parser.add_argument('--dataset', default='eval/generalization.jsonl')
    parser.add_argument('--report', default='eval/generalization-report.json')
    parser.add_argument('--chunks', default='data/processed/chunks.jsonl')
    parser.add_argument('--rank', type=int, default=3)
    parser.add_argument('--max-chars', type=int, default=1200)
    parser.add_argument('--full-text', action='store_true')
    args = parser.parse_args()
    if args.rank < 1:
        raise SystemExit('rank debe ser mayor que cero.')
    cases = load_jsonl(Path(args.dataset), 'id')
    chunks = load_jsonl(Path(args.chunks), 'chunk_id')
    report = json.loads(Path(args.report).read_text(encoding='utf-8'))
    max_chars = 0 if args.full_text else args.max_chars
    matches = [score for score in report['cases'] if score.get('expected_evidence') and score.get('rank') == args.rank]
    if not matches:
        print(f'No hay casos positivos con rango {args.rank}.')
        return
    for score in matches:
        case = cases.get(score['id'], {})
        expected = set(score['expected_chunk_ids'])
        print('\n' + '=' * 100)
        print(f"ID: {score['id']} | caso base: {case.get('parent_id', 'n/a')} | rango: {score['rank']}")
        print(f"Pregunta: {case.get('question', 'no encontrada')}")
        print('\nCHUNKS ESPERADOS')
        for chunk_id in score['expected_chunk_ids']:
            show_chunk('ESPERADO', chunks.get(chunk_id), max_chars)
        print('\nCHUNKS RECUPERADOS')
        for index, chunk_id in enumerate(score['retrieved_chunk_ids'], start=1):
            label = f'RECUPERADO #{index}' + (' [ESPERADO]' if chunk_id in expected else '')
            show_chunk(label, chunks.get(chunk_id), max_chars)
    print(f'\nCasos analizados: {len(matches)}')

if __name__ == '__main__':
    main()
