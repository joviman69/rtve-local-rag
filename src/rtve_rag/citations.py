def timestamp(ms: int | None) -> str:
    if ms is None:
        return "sin marca temporal"
    seconds = ms // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def format_source(source: dict) -> str:
    return (
        f"{source.get('program', 'RTVE')} — "
        f"{source.get('emission_date', 'sin fecha')} — "
        f"{source.get('chunk_id', 'sin chunk')} — "
        f"{timestamp(source.get('start_ms'))}"
    )


def format_sources(sources: list[dict]) -> list[str]:
    return [format_source(source) for source in sources]


def build_source_records(sources: list[dict], excerpt_length: int = 320) -> list[dict]:
    records = []
    for number, source in enumerate(sources, start=1):
        text = " ".join(str(source.get("text", "")).split())
        records.append(
            {
                "source_number": number,
                "program": source.get("program", "RTVE"),
                "emission_date": source.get("emission_date"),
                "chunk_id": source.get("chunk_id", "sin chunk"),
                "excerpt": text[:excerpt_length],
                "score": source.get("score"),
            }
        )
    return records
