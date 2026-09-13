import json
from urllib.request import Request, urlopen


def embed(texts: list[str], base_url: str, model: str) -> list[list[float]]:
    request = Request(
        f"{base_url.rstrip('/')}/api/embed",
        data=json.dumps({"model": model, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        data = json.loads(response.read())
    return data["embeddings"]
