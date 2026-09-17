import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from qdrant_client import QdrantClient
from rtve_rag.embeddings import embed
from rtve_rag.ingestion.chunker import chunk_cues
from rtve_rag.ingestion.cli import subtitle_files
from rtve_rag.ingestion.metadata import metadata_from_path
from rtve_rag.ingestion.processor import parse_subtitle_file
from rtve_rag.vector_store import delete_chunks, ensure_collection, upsert_chunks


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "documents": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != 1 or not isinstance(state.get("documents"), dict):
        raise ValueError("Estado incremental inválido")
    return state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def batches(items: list[dict], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def run_incremental(input_path: Path, source_manifest: dict, state_path: Path, client: QdrantClient, collection: str, ollama_url: str, embedding_model: str, batch_size: int = 32, chunk_size: int = 800, overlap: int = 120, dry_run: bool = False, force: bool = False) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero")
    state = load_state(state_path)
    report = {"discovered": 0, "indexed_documents": 0, "indexed_chunks": 0, "skipped": 0, "updated": 0, "planned": 0, "errors": []}
    for path in subtitle_files(input_path):
        report["discovered"] += 1
        try:
            metadata = metadata_from_path(path, source_manifest)
            digest = file_hash(path)
            previous = state["documents"].get(metadata.document_id)
            if previous and previous.get("sha256") == digest and not force:
                report["skipped"] += 1
                continue
            chunks = chunk_cues(parse_subtitle_file(path), metadata, chunk_size, overlap)
            if not chunks:
                raise ValueError("No se generaron chunks")
            payloads = [chunk.payload() for chunk in chunks]
            if dry_run:
                report["planned"] += 1
                continue
            dimension = None
            for batch in batches(payloads, batch_size):
                vectors = embed([item["text"] for item in batch], ollama_url, embedding_model)
                if len(vectors) != len(batch) or not vectors:
                    raise ValueError("Ollama devolvió embeddings inválidos")
                if dimension is None:
                    dimension = len(vectors[0])
                    if not dimension:
                        raise ValueError("Embedding vacío")
                    ensure_collection(client, collection, dimension)
                if any(len(vector) != dimension for vector in vectors):
                    raise ValueError("Embeddings con dimensiones inconsistentes")
                upsert_chunks(client, collection, batch, vectors)
            old_ids = set(previous.get("chunk_ids", [])) if previous else set()
            new_ids = {item["chunk_id"] for item in payloads}
            delete_chunks(client, collection, sorted(old_ids - new_ids))
            state["documents"][metadata.document_id] = {"path": str(path), "sha256": digest, "chunk_ids": sorted(new_ids), "chunk_count": len(payloads), "indexed_at": datetime.now(timezone.utc).isoformat()}
            save_state(state_path, state)
            report["indexed_documents"] += 1
            report["indexed_chunks"] += len(payloads)
            if previous:
                report["updated"] += 1
        except Exception as error:
            report["errors"].append({"path": str(path), "error": str(error)})
    return report
