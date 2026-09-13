from rtve_rag.evaluation import score_case, summarize, threshold_failures

def test_positive_and_negative_cases_are_scored_separately():
    positive = score_case({'id':'p','expected_chunk_ids':['a']}, [{'chunk_id':'a'}])
    negative = score_case({'id':'n','expected_evidence':False,'expected_chunk_ids':[]}, [])
    summary = summarize([positive, negative])
    assert summary['recall_at_k'] == 1
    assert summary['mrr'] == 1
    assert summary['negative_accuracy'] == 1
    assert summary['total_accuracy'] == 1

def test_negative_case_with_results_is_incorrect_and_can_fail_threshold():
    negative = score_case({'id':'n','expected_evidence':False,'expected_chunk_ids':[]}, [{'chunk_id':'a'}])
    report = summarize([negative])
    assert negative['correct'] is False
    assert threshold_failures(report, None, None, 1) == {'negative_accuracy': {'actual': 0.0, 'minimum': 1}}
