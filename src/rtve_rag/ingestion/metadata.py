import json
import re
from pathlib import Path

from rtve_rag.ingestion.models import DocumentMetadata

_FILENAME = re.compile(r"(?P<program>.+?)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{4})(?:_(?P<video>\d+))?_(?P<language>[a-z]{2}(?:-[a-z]{2})?)\.(?P<format>srt|vtt)$")

def load_manifest(path: Path) -> dict[str, dict]:
    if not path.exists(): return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError("El manifest debe ser un objeto JSON")
    return data

def find_manifest_entry(manifest: dict[str, dict], subtitle_path: Path) -> dict:
    return next((entry for entry in manifest.values() if Path(str(entry.get("path", ""))).name == subtitle_path.name), {})

def metadata_from_path(path: Path, manifest: dict[str, dict], corpus_version: str = "rtve_v1") -> DocumentMetadata:
    match = _FILENAME.match(path.name)
    if match is None: raise ValueError(f"Nombre no reconocido: {path.name}")
    values = match.groupdict(); entry = find_manifest_entry(manifest, path)
    video_id = values["video"] or entry.get("video_id")
    document_id = f"rtve_{video_id}_{values['language']}" if video_id else f"rtve_{values['program']}_{values['date']}_{values['time']}_{values['language']}"
    return DocumentMetadata(document_id, values["program"], values["date"], values["language"], values["format"], entry.get("html_url"), video_id, corpus_version)
