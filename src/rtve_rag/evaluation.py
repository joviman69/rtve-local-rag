def expects_evidence(case: dict) -> bool:
    return case.get('expected_evidence', bool(case.get('expected_chunk_ids', [])))

def score_case(case: dict, results: list[dict]) -> dict:
    expected = set(case.get('expected_chunk_ids', []))
    positive = expects_evidence(case)
    rank = next((index for index, result in enumerate(results, 1) if result.get('chunk_id') in expected), None) if positive else None
    correct = rank is not None if positive else not results
    return {'id': case['id'], 'expected_evidence': positive, 'expected_chunk_ids': sorted(expected), 'retrieved_chunk_ids': [item.get('chunk_id') for item in results], 'rank': rank, 'hit': rank is not None, 'abstained': not results, 'correct': correct, 'reciprocal_rank': 0 if rank is None else 1 / rank}

def summarize(scored_cases: list[dict]) -> dict:
    positives = [item for item in scored_cases if item['expected_evidence']]
    negatives = [item for item in scored_cases if not item['expected_evidence']]
    return {'evaluated_cases': len(scored_cases), 'positive_cases': len(positives), 'negative_cases': len(negatives), 'hits': sum(item['hit'] for item in positives), 'recall_at_k': 0 if not positives else sum(item['hit'] for item in positives) / len(positives), 'mrr': 0 if not positives else sum(item['reciprocal_rank'] for item in positives) / len(positives), 'negative_correct': sum(item['correct'] for item in negatives), 'negative_accuracy': 0 if not negatives else sum(item['correct'] for item in negatives) / len(negatives), 'total_accuracy': 0 if not scored_cases else sum(item['correct'] for item in scored_cases) / len(scored_cases), 'cases': scored_cases}

def threshold_failures(report: dict, min_recall: float | None, min_mrr: float | None, min_negative_accuracy: float | None = None) -> dict:
    failures = {}
    if min_recall is not None and report['recall_at_k'] < min_recall: failures['recall_at_k'] = {'actual': report['recall_at_k'], 'minimum': min_recall}
    if min_mrr is not None and report['mrr'] < min_mrr: failures['mrr'] = {'actual': report['mrr'], 'minimum': min_mrr}
    if min_negative_accuracy is not None and report['negative_accuracy'] < min_negative_accuracy: failures['negative_accuracy'] = {'actual': report['negative_accuracy'], 'minimum': min_negative_accuracy}
    return failures
