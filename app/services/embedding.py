"""
Embedding service — Step 3: Embed summary_for_rag.
Calls OpenAI embedding API to convert the summary text into a 1536-dim vector.
This vector is used to QUERY the knowledge base (not stored permanently).
"""

import os
import logging
from openai import OpenAI

logger = logging.getLogger("rag.embedding")


_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    """Lazy-initialized OpenAI client singleton."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY must be set in .env file. "
            "Get it from platform.openai.com → API Keys."
        )

    _client = OpenAI(api_key=api_key)
    return _client


def embed_text(text: str) -> list[float]:
    """
    Generate an embedding vector for the given text.

    Args:
        text: The summary_for_rag string from the NLP payload.

    Returns:
        A list of 1536 floats (embedding vector).

    Raises:
        RuntimeError: If the OpenAI API call fails.
    """
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    client = _get_openai_client()

    logger.info(f"   Calling OpenAI embeddings (model={model})...")
    logger.info(f"   Text: \"{text[:60]}...\"")

    try:
        response = client.embeddings.create(
            input=text,
            model=model,
        )
        embedding = response.data[0].embedding
        logger.info(f"   ✓ Embedding received — {len(embedding)} dimensions")
        return embedding
    except Exception as e:
        logger.error(f"   ✗ OpenAI API error: {str(e)}")
        raise RuntimeError(f"OpenAI embedding failed: {str(e)}")
