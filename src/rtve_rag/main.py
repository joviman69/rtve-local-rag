from fastapi import FastAPI
from pydantic import BaseModel
from qdrant_client import QdrantClient
from rtve_rag.generation import generate
from rtve_rag.retrieval import search
from rtve_rag.settings import get_settings

app=FastAPI(title='RTVE Local RAG',version='0.2.0')
class AskRequest(BaseModel):
    question:str
    top_k:int=4
    program:str|None=None
    emission_date:str|None=None
class AskResponse(BaseModel):
    answer:str
    sources:list[dict]
@app.get('/health')
def health():
    s=get_settings(); return {'status':'ok','chat_model':s.ollama_chat_model,'embedding_model':s.ollama_embedding_model}
@app.post('/ask',response_model=AskResponse)
def ask(request:AskRequest)->AskResponse:
    s=get_settings(); results=search(request.question,QdrantClient(url=s.qdrant_url),s.qdrant_collection,s.ollama_base_url,s.ollama_embedding_model,request.top_k,request.program,request.emission_date)
    if not results: return AskResponse(answer='No encuentro evidencia suficiente en el corpus indexado para responder a esta pregunta.',sources=[])
    context='\n\n'.join(f"[{r['chunk_id']}] {r['text']}\nFuente: {r.get('program')} — {r.get('emission_date')}" for r in results)
    prompt=f'Responde en español únicamente con el contexto. Si no basta, indícalo. Cita los IDs entre corchetes.\n\nContexto:\n{context}\n\nPregunta: {request.question}\nRespuesta:'
    return AskResponse(answer=generate(prompt,s.ollama_base_url,s.ollama_chat_model),sources=results)
