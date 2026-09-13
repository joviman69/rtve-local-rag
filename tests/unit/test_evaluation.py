from rtve_rag.evaluation import score_case, summarize

def test_score_case_reports_first_rank_hit():
    score = score_case({'id':'one','expected_chunk_ids':['a']}, [{'chunk_id':'a'}, {'chunk_id':'b'}])
    assert score['rank'] == 1
    assert score['reciprocal_rank'] == 1

def test_score_case_reports_later_rank_and_miss():
    second = score_case({'id':'two','expected_chunk_ids':['b']}, [{'chunk_id':'a'}, {'chunk_id':'b'}])
    missing = score_case({'id':'three','expected_chunk_ids':['z']}, [{'chunk_id':'a'}])
    summary = summarize([second, missing])
    assert second['rank'] == 2
    assert summary['recall_at_k'] == 0.5
    assert summary['mrr'] == 0.25
