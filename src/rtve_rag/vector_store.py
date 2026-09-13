import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


def ensure_collection(client: QdrantClient, collection: str, dimension: int) -> None:
    if not client.collection_exists(collection):
        client.create_collection(collection_name=collection, vectors_config=VectorParams(size=dimension, distance=Distance.COSINE))

def upsert_chunks(client: QdrantClient, collection: str, chunks: list[dict], vectors: list[list[float]]) -> None:
    if len(chunks) != len(vectors): raise ValueError("chunks y vectors deben tener la misma longitud")
    points = [PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["chunk_id"])), vector=vector, payload=chunk) for chunk, vector in zip(chunks, vectors)]
    client.upsert(collection_name=collection, points=points, wait=True)
