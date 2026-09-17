import json
from rtve_rag.generation import generate

def verify_evidence(question:str, results:list[dict], base_url:str, model:str)->dict:
    allowed={item.get('chunk_id') for item in results}
    context='\n'.join(f'ID: {item.get("chunk_id")}\nTEXTO: {item.get("text", "")}' for item in results)
    prompt=f'Revisa solo el contexto. ¿Responde directamente a la pregunta? Devuelve JSON con has_direct_evidence, relevant_chunk_ids y reason. No uses conocimiento externo. Pregunta: {question}\nContexto:\n{context}'
    try: decision=json.loads(generate(prompt,base_url,model,response_format='json'))
    except (json.JSONDecodeError, TypeError): return {'has_direct_evidence':False,'relevant_chunk_ids':[],'reason':'invalid_verifier_output'}
    has_evidence=bool(decision.get('has_direct_evidence'))
    ids=[item for item in decision.get('relevant_chunk_ids',[]) if item in allowed] if has_evidence else []
    return {'has_direct_evidence':has_evidence and bool(ids),'relevant_chunk_ids':ids,'reason':str(decision.get('reason',''))}
