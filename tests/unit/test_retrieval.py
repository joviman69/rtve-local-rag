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
def test_search_filters_points_below_min_score(monkeypatch):
    class ThresholdClient:
        def query_points(self, **kwargs):
            points=[type('Point',(),{'score':0.26,'payload':{'chunk_id':'low'}})(),type('Point',(),{'score':0.27,'payload':{'chunk_id':'boundary'}})(),type('Point',(),{'score':0.9,'payload':{'chunk_id':'high'}})()]
            return type('Result',(),{'points':points})()
    monkeypatch.setattr('rtve_rag.retrieval.embed',lambda *_:[[0.1,0.2]])
    assert [item['chunk_id'] for item in search('consulta',ThresholdClient(),'test',min_score=0.27)] == ['boundary','high']
    assert len(search('consulta',ThresholdClient(),'test')) == 3
