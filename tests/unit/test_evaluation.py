from rtve_rag.evaluation import score_case, summarize, threshold_failures

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

def test_threshold_failures_only_reports_unmet_minimums():
    report = {'recall_at_k': 0.75, 'mrr': 0.5}
    assert threshold_failures(report, 0.7, 0.5) == {}
    assert threshold_failures(report, 0.8, 0.6) == {'recall_at_k': {'actual': 0.75, 'minimum': 0.8}, 'mrr': {'actual': 0.5, 'minimum': 0.6}}
