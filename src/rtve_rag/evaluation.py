def score_case(case: dict, results: list[dict]) -> dict:
    expected = set(case.get('expected_chunk_ids', []))
    rank = next((index for index, result in enumerate(results, 1) if result.get('chunk_id') in expected), None)
    return {'id': case['id'], 'expected_chunk_ids': sorted(expected), 'retrieved_chunk_ids': [item.get('chunk_id') for item in results], 'rank': rank, 'hit': rank is not None, 'reciprocal_rank': 0 if rank is None else 1 / rank}

def summarize(scored_cases: list[dict]) -> dict:
    total = len(scored_cases)
    return {'evaluated_cases': total, 'hits': sum(item['hit'] for item in scored_cases), 'recall_at_k': 0 if not total else sum(item['hit'] for item in scored_cases) / total, 'mrr': 0 if not total else sum(item['reciprocal_rank'] for item in scored_cases) / total, 'cases': scored_cases}

def threshold_failures(report: dict, min_recall: float | None, min_mrr: float | None) -> dict:
    failures = {}
    if min_recall is not None and report['recall_at_k'] < min_recall:
        failures['recall_at_k'] = {'actual': report['recall_at_k'], 'minimum': min_recall}
    if min_mrr is not None and report['mrr'] < min_mrr:
        failures['mrr'] = {'actual': report['mrr'], 'minimum': min_mrr}
    return failures
