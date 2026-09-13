import argparse
import json
from pathlib import Path

from rtve_rag.ingestion.chunker import chunk_cues
from rtve_rag.ingestion.metadata import load_manifest, metadata_from_path
from rtve_rag.ingestion.processor import parse_subtitle_file

def main() -> None:
    parser = argparse.ArgumentParser(description="Convierte subtítulos en JSONL de chunks.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus-version", default="rtve_v1")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest) if args.manifest else {}
    metadata = metadata_from_path(args.input, manifest, args.corpus_version)
    chunks = chunk_cues(parse_subtitle_file(args.input), metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(chunk.payload(), ensure_ascii=False) + "\n" for chunk in chunks), encoding="utf-8")

if __name__ == "__main__": main()
