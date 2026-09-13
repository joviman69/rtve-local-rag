from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rtve_rag.embeddings import embed
from rtve_rag.query_normalization import normalize_query

def search(query:str, client:QdrantClient, collection:str, ollama_url:str='http://localhost:11434', model:str='qwen3-embedding:0.6b', top_k:int=4, program:str|None=None, emission_date:str|None=None, language:str|None=None, normalize:bool=False)->list[dict]:
    filters=[]
    for key,value in {'program':program,'emission_date':emission_date,'language':language}.items():
        if value: filters.append(FieldCondition(key=key, match=MatchValue(value=value)))
    retrieval_query=normalize_query(query) if normalize else query
    vector=embed([retrieval_query],ollama_url,model)[0]
    result=client.query_points(collection_name=collection,query=vector,query_filter=Filter(must=filters) if filters else None,limit=top_k).points
    return [dict(point.payload, score=point.score) for point in result]
