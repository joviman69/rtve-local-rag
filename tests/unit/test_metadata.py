import json
from pathlib import Path

from rtve_rag.ingestion.metadata import find_manifest_entry, load_manifest

def test_load_and_find_manifest_entry(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"123:es:srt": {"video_id": "123", "html_url": "https://example.test/video", "path": "data/raw/telediario-1_2026-09-03_1500_es.srt"}}), encoding="utf-8")
    entry = find_manifest_entry(load_manifest(manifest_path), Path("telediario-1_2026-09-03_1500_es.srt"))
    assert entry["video_id"] == "123"
    assert entry["html_url"] == "https://example.test/video"
