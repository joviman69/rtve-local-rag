import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from qdrant_client import QdrantClient
from rtve_rag.evaluation import score_case, summarize
from rtve_rag.evidence import verify_evidence
from rtve_rag.retrieval import search
from rtve_rag.settings import get_settings

def main():
    parser=argparse.ArgumentParser(description='Evaluate local evidence verification.')
    parser.add_argument('--input',required=True); parser.add_argument('--output',required=True); parser.add_argument('--top-k',type=int,default=4); parser.add_argument('--min-score',type=float,default=0.30); args=parser.parse_args()
    cases=[json.loads(line) for line in Path(args.input).read_text(encoding='utf-8').splitlines() if line.strip()]
    settings=get_settings(); client=QdrantClient(url=settings.qdrant_url); scored=[]
    for case in cases:
        results=search(case['question'],client,settings.qdrant_collection,settings.ollama_base_url,settings.ollama_embedding_model,args.top_k,case.get('program'),case.get('emission_date'),min_score=args.min_score)
        started=time.perf_counter()
        decision=verify_evidence(case['question'],results,settings.ollama_base_url,settings.ollama_chat_model) if results else {'has_direct_evidence':False,'relevant_chunk_ids':[],'reason':'no_candidates'}
        verification_ms=round((time.perf_counter()-started)*1000)
        verified=[item for item in results if item.get('chunk_id') in set(decision['relevant_chunk_ids'])]
        score=score_case(case,verified)
        score.update({'question':case['question'],'candidate_chunk_ids':[item.get('chunk_id') for item in results],'verifier':decision,'verification_ms':verification_ms})
        scored.append(score)
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'input':args.input,'top_k':args.top_k,'min_score':args.min_score,'verifier_model':settings.ollama_chat_model,**summarize(scored)}
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('evaluated_cases','positive_cases','negative_cases','recall_at_k','mrr','negative_accuracy','total_accuracy')},ensure_ascii=False))
if __name__=='__main__': main()
