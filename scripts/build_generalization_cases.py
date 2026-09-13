import argparse
import json
from pathlib import Path
from rtve_rag.generation import generate
from rtve_rag.settings import get_settings

def load_cases(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    return [case for case in cases if case.get('expected_evidence', bool(case.get('expected_chunk_ids'))) and case.get('expected_chunk_ids')]

def parse_variants(text: str) -> list[str]:
    start, end = text.find('['), text.rfind(']')
    if start < 0 or end < start:
        raise ValueError('Ollama no devolvió una lista JSON.')
    variants = json.loads(text[start:end + 1])
    if not isinstance(variants, list) or not all(isinstance(item, str) for item in variants):
        raise ValueError('La salida no contiene una lista de preguntas.')
    return variants

def make_prompt(question: str, count: int) -> str:
    return f'''Reformula la pregunta española siguiente en {count} variantes naturales y semánticamente equivalentes. Conserva todas las entidades, fechas, restricciones y el significado factual. No respondas la pregunta, no añadas hechos y no uses información externa. Devuelve exclusivamente un array JSON de strings, sin Markdown.\n\nPregunta original: {question}'''

def main() -> None:
    parser = argparse.ArgumentParser(description='Generate human-reviewed paraphrases for retrieval generalization evaluation.')
    parser.add_argument('--input', default='eval/questions.jsonl')
    parser.add_argument('--output', default='eval/generalization.jsonl')
    parser.add_argument('--variants-per-case', type=int, default=3)
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()
    if args.variants_per_case < 1:
        raise SystemExit('variants-per-case debe ser mayor que cero.')
    cases = load_cases(Path(args.input))
    if args.limit is not None:
        cases = cases[:args.limit]
    settings = get_settings()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    saved = 0
    for case in cases:
        try:
            variants = parse_variants(generate(make_prompt(case['question'], args.variants_per_case), settings.ollama_base_url, settings.ollama_chat_model))
        except (ValueError, json.JSONDecodeError) as error:
            print(f"No se generaron variantes para {case['id']}: {error}")
            continue
        seen = {case['question'].casefold()}
        for index, question in enumerate(variants, start=1):
            question = question.strip()
            if not question or question.casefold() in seen:
                continue
            seen.add(question.casefold())
            print(f"\nOriginal: {case['question']}\nVariante: {question}")
            approved = input('¿Preserva exactamente la intención y las entidades? [s/N]: ').strip().lower()
            if approved not in {'s', 'si', 'sí', 'y', 'yes'}:
                print('Variante descartada.')
                continue
            record = {'id': f"{case['id']}-g{index}", 'parent_id': case['id'], 'question': question, 'program': case.get('program'), 'emission_date': case.get('emission_date'), 'expected_evidence': True, 'expected_chunk_ids': case['expected_chunk_ids'], 'notes': f"Paráfrasis revisada de {case['id']}."}
            with output.open('a', encoding='utf-8') as file:
                file.write(json.dumps(record, ensure_ascii=False) + '\n')
            saved += 1
            print(f"Guardado: {record['id']}")
    print(json.dumps({'source_cases': len(cases), 'approved_variants': saved, 'output': str(output)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
