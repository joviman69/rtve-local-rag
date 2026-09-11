from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleCue:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    program: str
    emission_date: str
    language: str
    original_format: str
    source_url: str | None = None
    video_id: str | None = None
    corpus_version: str = "rtve_v1"
