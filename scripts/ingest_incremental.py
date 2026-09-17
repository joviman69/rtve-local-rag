import argparse
import json
from pathlib import Path
from qdrant_client import QdrantClient
from rtve_rag.ingestion.incremental import run_incremental
from rtve_rag.ingestion.metadata import load_manifest
from rtve_rag.settings import get_settings


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Debe ser mayor que cero")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta incremental e idempotente de subtítulos RTVE.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--state", type=Path, default=Path("data/processed/ingestion-state.json"))
    parser.add_argument("--collection")
    parser.add_argument("--batch-size", type=positive, default=32)
    parser.add_argument("--chunk-size", type=positive, default=800)
    parser.add_argument("--overlap", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.overlap < 0 or args.overlap >= args.chunk_size:
        parser.error("overlap debe ser mayor o igual que cero y menor que chunk-size")
    settings = get_settings()
    report = run_incremental(args.input, load_manifest(args.source_manifest) if args.source_manifest else {}, args.state, QdrantClient(url=settings.qdrant_url), args.collection or settings.qdrant_collection, settings.ollama_base_url, settings.ollama_embedding_model, args.batch_size, args.chunk_size, args.overlap, args.dry_run, args.force)
    print(json.dumps(report, ensure_ascii=False))
    if args.strict and report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
