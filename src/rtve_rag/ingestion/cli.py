import argparse
import json
from pathlib import Path

from rtve_rag.ingestion.chunker import chunk_cues
from rtve_rag.ingestion.models import DocumentMetadata
from rtve_rag.ingestion.processor import parse_subtitle_file

def main() -> None:
    parser = argparse.ArgumentParser(description="Convierte subtítulos en JSONL de chunks.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--program", default="telediario-1")
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    metadata = DocumentMetadata(f"rtve_{args.program}_{args.date}", args.program, args.date, "es", args.input.suffix.lstrip("."))
    chunks = chunk_cues(parse_subtitle_file(args.input), metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(chunk.payload(), ensure_ascii=False) + "\n" for chunk in chunks), encoding="utf-8")

if __name__ == "__main__": main()
