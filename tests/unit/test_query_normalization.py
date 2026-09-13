from rtve_rag.query_normalization import normalize_query

def test_removes_generic_information_wrapper_and_preserves_entity():
    assert normalize_query('¿Qué información hay disponible sobre el estrecho de Ormuz?') == 'estrecho ormuz'

def test_focuses_school_calendar_question():
    assert normalize_query('¿Cuál es la fecha de inicio del año escolar?') == 'fecha inicio año escolar'

def test_preserves_entities_dates_and_short_queries():
    assert normalize_query('¿Qué anunció SEAT el 3 de septiembre?') == 'anunció seat 3 septiembre'
    assert normalize_query('estrecho de Ormuz') == 'estrecho de Ormuz'
