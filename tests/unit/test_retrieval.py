from rtve_rag.retrieval import search

class Point:
    score=0.9
    payload={'chunk_id':'one','text':'resultado'}
class Client:
    def query_points(self, **kwargs):
        self.kwargs=kwargs
        return type('Result',(),{'points':[Point()]})()
def test_search_returns_payload_and_score(monkeypatch):
    monkeypatch.setattr('rtve_rag.retrieval.embed',lambda *_:[[0.1,0.2]])
    result=search('consulta',Client(),'test',program='td1')
    assert result[0]['score']==0.9
    assert result[0]['chunk_id']=='one'
