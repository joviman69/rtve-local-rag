import json
from rtve_rag.generation import generate


def verify_evidence(question: str, results: list[dict], base_url: str, model: str) -> dict:
    allowed = {item.get("chunk_id") for item in results}
    context = "\n\n".join(
        "\n".join(
            [
                f"ID: {item.get('chunk_id')}",
                f"FECHA_DE_EMISIÓN: {item.get('emission_date') or item.get('date') or 'no_disponible'}",
                f"TEXTO: {item.get('text', '')}",
            ]
        )
        for item in results
    )
    prompt = f'''Revisa exclusivamente el contexto documental y decide si contiene evidencia suficiente para responder materialmente a la pregunta.

Reglas:
- Hay evidencia directa si uno o más fragmentos aportan un hecho, evento, cifra, estado o tendencia que responda materialmente a la pregunta.
- Para preguntas amplias como "qué información hay", "actualidad" o "últimas noticias", basta con uno o más hechos sustantivos y relevantes sobre la entidad. No exijas una biografía, una cobertura exhaustiva ni varios asuntos independientes.
- Para tendencias o evolución, expresiones como "sube", "baja", "continúa", "se mantiene", "récord" y comparaciones temporales son evidencia directa cuando responden a la pregunta.
- Para expresiones temporales como "reciente", "hoy", "ayer" o "últimos tiempos", usa FECHA_DE_EMISIÓN como referencia documental. No rechaces una noticia pertinente solo porque el texto no repita literalmente "reciente".
- Comprueba todos los elementos específicos de la pregunta antes de aceptar evidencia. Si pregunta por una ubicación, país, ciudad, persona, organización, fecha, año, cifra, relación o evento concreto, el contexto debe mencionarlo explícitamente o permitir resolverlo sin ambigüedad con los metadatos proporcionados.
- No aceptes información de otra ubicación como respuesta. Por ejemplo, una previsión meteorológica en España no responde a una pregunta sobre la previsión de París.
- FECHA_DE_EMISIÓN solo sirve para resolver referencias temporales relativas; no sustituye una ubicación, entidad, año o dato específico ausente del contexto.
- Rechaza si el contexto no aporta una respuesta material, si solo hay una coincidencia superficial, si necesitarías conocimiento externo, si exigiría un cálculo no respaldado, o si falta el dato exacto solicitado.
- Si has_direct_evidence es false, relevant_chunk_ids debe ser una lista vacía.
- Incluye únicamente IDs presentes en el contexto y necesarios para sostener la decisión.

Devuelve exclusivamente JSON válido con esta forma:
{{"has_direct_evidence": true|false, "relevant_chunk_ids": ["id"], "reason": "explicación breve"}}

Pregunta: {question}

Contexto:
{context}'''
    try:
        decision = json.loads(generate(prompt, base_url, model, response_format="json"))
    except (json.JSONDecodeError, TypeError):
        return {
            "has_direct_evidence": False,
            "relevant_chunk_ids": [],
            "reason": "invalid_verifier_output",
        }

    has_evidence = bool(decision.get("has_direct_evidence"))
    ids = [
        chunk_id
        for chunk_id in decision.get("relevant_chunk_ids", [])
        if chunk_id in allowed
    ] if has_evidence else []

    return {
        "has_direct_evidence": has_evidence and bool(ids),
        "relevant_chunk_ids": ids,
        "reason": str(decision.get("reason", "")),
    }
