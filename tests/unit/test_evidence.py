from rtve_rag.evidence import verify_evidence

def test_verifier_filters_unknown_chunk_ids(monkeypatch):
    monkeypatch.setattr('rtve_rag.evidence.generate',lambda *args,**kwargs:'{"has_direct_evidence": true, "relevant_chunk_ids": ["ok", "other"], "reason": "directa"}')
    decision=verify_evidence('pregunta',[{'chunk_id':'ok','text':'evidencia'}],'url','model')
    assert decision['has_direct_evidence'] is True
    assert decision['relevant_chunk_ids']==['ok']
def test_verifier_clears_ids_when_evidence_is_insufficient(monkeypatch):
    monkeypatch.setattr('rtve_rag.evidence.generate',lambda *args,**kwargs:'{"has_direct_evidence": false, "relevant_chunk_ids": ["ok"], "reason": "insuficiente"}')
    decision=verify_evidence('pregunta',[{'chunk_id':'ok','text':'evidencia'}],'url','model')
    assert decision['has_direct_evidence'] is False
    assert decision['relevant_chunk_ids']==[]
def test_verifier_fails_closed_on_invalid_json(monkeypatch):
    monkeypatch.setattr('rtve_rag.evidence.generate',lambda *args,**kwargs:'no json')
    assert verify_evidence('pregunta',[],'url','model')['has_direct_evidence'] is False
