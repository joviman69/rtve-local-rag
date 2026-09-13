import argparse
import json
from pathlib import Path

from qdrant_client import QdrantClient

from rtve_rag.embeddings import embed
from rtve_rag.vector_store import ensure_collection, upsert_chunks

def load_chunks(path: Path) -> list[dict]:
    chunks = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not chunks: raise ValueError('El JSONL no contiene chunks')
    if any('chunk_id' not in chunk or 'text' not in chunk for chunk in chunks): raise ValueError('Cada chunk requiere chunk_id y text')
    return chunks

def main() -> None:
    parser = argparse.ArgumentParser(description='Indexa JSONL en Qdrant usando Ollama.')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--qdrant-url', default='http://localhost:6333')
    parser.add_argument('--collection', default='rtve_subtitles')
    parser.add_argument('--ollama-url', default='http://localhost:11434')
    parser.add_argument('--model', default='qwen3-embedding:0.6b')
    args = parser.parse_args()
    chunks = load_chunks(args.input)
    vectors = embed([chunk['text'] for chunk in chunks], args.ollama_url, args.model)
    if len(vectors) != len(chunks) or not vectors or any(len(vector) != len(vectors[0]) for vector in vectors): raise ValueError('Embeddings inválidos o inconsistentes')
    client = QdrantClient(url=args.qdrant_url)
    ensure_collection(client, args.collection, len(vectors[0]))
    upsert_chunks(client, args.collection, chunks, vectors)
    print(f'Indexados {len(chunks)} chunks en {args.collection}')

if __name__ == '__main__': main()
