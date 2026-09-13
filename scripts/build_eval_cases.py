import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

def post_ask(endpoint, payload):
    request = Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type':'application/json; charset=utf-8'}, method='POST')
    with urlopen(request, timeout=240) as response: return json.loads(response.read().decode('utf-8'))
def next_id(output):
    values=[]
    if output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            if line.strip():
                match=re.fullmatch(r'eval-(\d+)', json.loads(line).get('id',''))
                if match: values.append(int(match.group(1)))
    return max(values, default=0)+1
def indexes(value, size):
    if not value.strip(): return []
    selected=sorted({int(item.strip()) for item in value.split(',')})
    if any(item < 1 or item > size for item in selected): raise ValueError('Índice fuera de rango.')
    return selected
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--questions', required=True); parser.add_argument('--output', default='eval/questions.jsonl'); parser.add_argument('--endpoint', default='http://127.0.0.1:8000/ask'); parser.add_argument('--top-k', type=int, default=4); parser.add_argument('--program'); parser.add_argument('--emission-date'); args=parser.parse_args()
    output=Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); number=next_id(output)
    questions=[line.strip() for line in Path(args.questions).read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
    for question in questions:
        response=post_ask(args.endpoint, {'question':question,'top_k':args.top_k,'program':args.program,'emission_date':args.emission_date}); sources=response.get('sources',[])
        print(f'\nPREGUNTA: {question}\n\n{response.get("answer", "")}\n\nFUENTES:')
        for index, source in enumerate(sources, 1): print(f'[{index}] {source.get("chunk_id")}\n    {" ".join(source.get("text", "").split())[:360]}')
        while True:
            try: selected=indexes(input('Índices con evidencia correcta (ej. 1,3; Enter = caso negativo): '), len(sources)); break
            except ValueError as error: print(error)
        notes=input('Notas de relevancia o motivo del negativo (opcional): ').strip()
        case={'id':f'eval-{number:03d}','question':question,'program':args.program,'emission_date':args.emission_date,'expected_evidence':bool(selected),'expected_chunk_ids':[sources[item-1]['chunk_id'] for item in selected],'notes':notes}
        with output.open('a', encoding='utf-8') as file: file.write(json.dumps(case, ensure_ascii=False)+'\n')
        print(f'Guardado {case["id"]} ({"positivo" if selected else "negativo"}).'); number+=1
if __name__ == '__main__': main()
