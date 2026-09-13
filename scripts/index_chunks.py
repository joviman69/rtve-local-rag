import argparse
import json
from pathlib import Path
from qdrant_client import QdrantClient
from rtve_rag.embeddings import embed
from rtve_rag.settings import get_settings
from rtve_rag.vector_store import ensure_collection, upsert_chunks

def positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('batch-size debe ser mayor que cero.')
    return number

def load_chunks(path: Path) -> list[dict]:
    chunks = []
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        chunk = json.loads(line)
        if not chunk.get('chunk_id') or not chunk.get('text', '').strip():
            raise ValueError(f'Chunk inválido en línea {line_number}: requiere chunk_id y text.')
        chunks.append(chunk)
    if not chunks:
        raise ValueError(f'No hay chunks indexables en {path}.')
    return chunks

def batches(items: list[dict], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]

def main() -> None:
    parser = argparse.ArgumentParser(description='Create a Qdrant collection and index chunk JSONL with Ollama embeddings.')
    parser.add_argument('--input', default='data/processed/chunks.jsonl')
    parser.add_argument('--collection', default=None)
    parser.add_argument('--batch-size', type=positive_integer, default=32)
    parser.add_argument('--recreate', action='store_true', help='Delete an existing collection before indexing.')
    args = parser.parse_args()
    settings = get_settings()
    collection = args.collection or settings.qdrant_collection
    chunks = load_chunks(Path(args.input))
    client = QdrantClient(url=settings.qdrant_url)
    if client.collection_exists(collection):
        if not args.recreate:
            raise SystemExit(f'La colección {collection!r} ya existe. Usa --recreate para borrarla e indexar desde cero.')
        client.delete_collection(collection)
        print(f'Colección eliminada: {collection}')
    indexed = 0
    dimension = None
    for batch in batches(chunks, args.batch_size):
        vectors = embed([chunk['text'] for chunk in batch], settings.ollama_base_url, settings.ollama_embedding_model)
        if len(vectors) != len(batch) or not vectors:
            raise ValueError('Ollama devolvió un número de embeddings distinto al esperado.')
        if dimension is None:
            dimension = len(vectors[0])
            if not dimension:
                raise ValueError('El primer embedding está vacío.')
            ensure_collection(client, collection, dimension)
        if any(len(vector) != dimension for vector in vectors):
            raise ValueError('Ollama devolvió embeddings con dimensiones inconsistentes.')
        upsert_chunks(client, collection, batch, vectors)
        indexed += len(batch)
        print(f'Indexados {indexed}/{len(chunks)} chunks')
    print(json.dumps({'collection': collection, 'indexed_chunks': indexed, 'vector_dimension': dimension, 'embedding_model': settings.ollama_embedding_model}, ensure_ascii=False))

if __name__ == '__main__':
    main()
