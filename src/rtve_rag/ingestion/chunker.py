import hashlib

from rtve_rag.ingestion.models import DocumentMetadata, SubtitleChunk, SubtitleCue

def chunk_cues(cues: list[SubtitleCue], metadata: DocumentMetadata, chunk_size: int = 800) -> list[SubtitleChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser positivo")
    chunks: list[SubtitleChunk] = []
    current: list[SubtitleCue] = []
    size = 0
    def emit() -> None:
        nonlocal current, size
        if not current: return
        text = " ".join(c.text for c in current)
        position = len(chunks)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        chunks.append(SubtitleChunk(f"{metadata.document_id}_{position:04d}_{digest}", text, current[0].start_ms, current[-1].end_ms, position, metadata))
        current = []; size = 0
    for cue in cues:
        if current and size + len(cue.text) + 1 > chunk_size: emit()
        current.append(cue); size += len(cue.text) + 1
    emit()
    return chunks
