import re

PREFIXES = (
    r'^qué\s+información\s+(?:hay\s+)?disponible\s+sobre\s+',
    r'^qué\s+se\s+sabe\s+(?:sobre|acerca\s+de)\s+',
    r'^puedes\s+decirme\s+',
    r'^podrías\s+decirme\s+',
)
STOPWORDS = {'a', 'al', 'cual', 'cuál', 'de', 'del', 'el', 'en', 'es', 'la', 'las', 'lo', 'los', 'por', 'que', 'qué', 'se', 'sobre', 'un', 'una', 'y'}

def normalize_query(query: str) -> str:
    compact = ' '.join(query.strip().split()).strip('¿?')
    if len(re.findall(r'[^\W_]+', compact, flags=re.UNICODE)) <= 4:
        return compact
    normalized = compact.casefold()
    for pattern in PREFIXES:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    terms = [term for term in re.findall(r'[^\W_]+', normalized, flags=re.UNICODE) if term not in STOPWORDS]
    return ' '.join(terms) or compact
