import json
from pathlib import Path

from rtve_rag.ingestion.metadata import load_manifest, metadata_from_path

def test_metadata_uses_manifest_video_and_url(tmp_path: Path) -> None:
    subtitle = tmp_path / "telediario-1_2026-09-03_1500_es.srt"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"123:es:srt": {"video_id": "123", "html_url": "https://example.test/video", "path": str(subtitle)}}), encoding="utf-8")
    metadata = metadata_from_path(subtitle, load_manifest(manifest_path))
    assert metadata.document_id == "rtve_123_es"
    assert metadata.source_url == "https://example.test/video"
