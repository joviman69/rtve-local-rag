from rtve_rag.ingestion.chunker import chunk_cues
from rtve_rag.ingestion.models import DocumentMetadata, SubtitleCue

def test_chunk_keeps_provenance_and_time_range() -> None:
    metadata = DocumentMetadata("demo", "td1", "2026-09-11", "es", "vtt")
    chunk = chunk_cues([SubtitleCue(0, 1000, "uno"), SubtitleCue(1000, 2000, "dos")], metadata)[0]
    assert chunk.start_ms == 0
    assert chunk.end_ms == 2000
    assert chunk.metadata.document_id == "demo"
