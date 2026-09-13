from rtve_rag.citations import format_source

def test_format_source_includes_provenance():
    value=format_source({'program':'telediario-1','emission_date':'2026-09-03','chunk_id':'rtve_123_es_0001','start_ms':62000})
    assert value == 'telediario-1 — 2026-09-03 — rtve_123_es_0001 — 01:02'
