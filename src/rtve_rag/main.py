import uuid
from fastapi import FastAPI
from pydantic import BaseModel
from qdrant_client import QdrantClient
from rtve_rag.citations import format_sources
from rtve_rag.generation import generate
from rtve_rag.retrieval import search
from rtve_rag.settings import get_settings
app=FastAPI(title='RTVE Local RAG',version='0.2.1')
class AskRequest(BaseModel):
 question:str
 top_k:int=4
 program:str|None=None
 emission_date:str|None=None
class AskResponse(BaseModel):
 request_id:str
 answer:str
 sources:list[dict]
 citations:list[str]
@app.get('/health')
def health():
 s=get_settings(); return {'status':'ok','chat_model':s.ollama_chat_model,'embedding_model':s.ollama_embedding_model}
@app.post('/ask',response_model=AskResponse)
def ask(request:AskRequest)->AskResponse:
 s=get_settings(); request_id=str(uuid.uuid4()); results=search(request.question,QdrantClient(url=s.qdrant_url),s.qdrant_collection,s.ollama_base_url,s.ollama_embedding_model,request.top_k,request.program,request.emission_date); citations=format_sources(results)
 if not results:return AskResponse(request_id=request_id,answer='No encuentro evidencia suficiente en el corpus indexado para responder a esta pregunta.',sources=[],citations=[])
 context='\n'.join(f'[{citation}] {item["text"]}' for item,citation in zip(results,citations))
 answer=generate(f'Responde en español solo con este contexto y cita las fuentes entre corchetes.\n{context}\nPregunta: {request.question}',s.ollama_base_url,s.ollama_chat_model)
 return AskResponse(request_id=request_id,answer=answer,sources=results,citations=citations)
