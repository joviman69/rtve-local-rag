from rtve_rag.vector_store import ensure_collection

class Client:
    def __init__(self): self.created = False
    def collection_exists(self, _: str) -> bool: return self.created
    def create_collection(self, **_: object) -> None: self.created = True

def test_collection_created_once() -> None:
    client = Client()
    ensure_collection(client, "test", 3)
    ensure_collection(client, "test", 3)
    assert client.created
