"""OpenAI embedding wrapper.

Uses text-embedding-3-small (1536 dims).  The client is created lazily so
the module can be imported without an API key present at import time.
"""

from openai import AsyncOpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM   = 1536

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    return _client


async def embed_text(text: str) -> list[float]:
    """Embed a single string and return its vector."""
    response = await _get_client().embeddings.create(
        input=text,
        model=EMBEDDING_MODEL,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings in one API call (preserves order)."""
    if not texts:
        return []
    response = await _get_client().embeddings.create(
        input=texts,
        model=EMBEDDING_MODEL,
    )
    # API returns in the same order as input; sort defensively by index
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
