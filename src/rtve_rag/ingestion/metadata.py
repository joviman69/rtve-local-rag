import json
from pathlib import Path

def load_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("El manifest debe ser un objeto JSON")
    return data

def find_manifest_entry(manifest: dict[str, dict], subtitle_path: Path) -> dict:
    for entry in manifest.values():
        if Path(str(entry.get("path", ""))).name == subtitle_path.name:
            return entry
    return {}
