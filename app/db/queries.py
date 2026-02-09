"""
Database query functions for the RAG service.
All Supabase table operations live here.
"""

import logging
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger("rag.queries")


# ============================================================
# call_analyses table operations
# ============================================================

def insert_call_record(
    call_id: str,
    call_timestamp: str,
    call_context: dict,
    speaker_analysis: dict,
    nlp_insights: dict,
    risk_signals: dict,
    risk_assessment: dict,
    summary_for_rag: str,
) -> dict:
    """
    Insert a new call record into call_analyses.
    rag_output is left NULL — populated later in Step 7 by updater.py.

    Returns: {"inserted": True, "call_id": "...", "table": "call_analyses"}
    Raises: Exception if Supabase insert fails.
    """
    client = get_supabase_client()

    row = {
        "call_id": call_id,
        "call_timestamp": call_timestamp,
        "call_context": call_context,
        "speaker_analysis": speaker_analysis,
        "nlp_insights": nlp_insights,
        "risk_signals": risk_signals,
        "risk_assessment": risk_assessment,
        "summary_for_rag": summary_for_rag,
        # rag_output intentionally omitted — NULL until Step 7
    }

    logger.info(f"DB INSERT call_analyses ({call_id})")
    result = client.table("call_analyses").insert(row).execute()

    if not result.data:
        raise RuntimeError(f"Supabase insert returned no data for call_id={call_id}")

    return {
        "inserted": True,
        "call_id": call_id,
        "table": "call_analyses",
    }


def get_call_by_id(call_id: str) -> dict | None:
    """
    Fetch a single call record by call_id.
    Returns the row as a dict, or None if not found.
    """
    client = get_supabase_client()

    result = (
        client.table("call_analyses")
        .select("*")
        .eq("call_id", call_id)
        .execute()
    )

    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def update_rag_output(call_id: str, rag_output: dict) -> dict:
    """
    Update the rag_output column for an existing call record (Step 7).
    Returns: {"updated": True, "call_id": "...", "table": "call_analyses", "field": "rag_output"}
    """
    client = get_supabase_client()

    result = (
        client.table("call_analyses")
        .update({"rag_output": rag_output})
        .eq("call_id", call_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Supabase update returned no data for call_id={call_id}")

    return {
        "updated": True,
        "call_id": call_id,
        "table": "call_analyses",
        "field": "rag_output",
    }


# ============================================================
# knowledge_embeddings table operations
# ============================================================

def search_knowledge(
    query_embedding: list[float],
    category: str,
    limit: int = 3,
) -> list[dict]:
    """
    Perform vector similarity search against knowledge_embeddings
    using the match_knowledge RPC function defined in init.sql.

    Args:
        query_embedding: 1536-dim query vector from Step 3.
        category: One of 'fraud_pattern', 'compliance', 'risk_heuristic'.
        limit: Max number of results to return.

    Returns:
        List of dicts with doc_id, title, content, similarity.
    """
    client = get_supabase_client()

    logger.info(f"DB RPC match_knowledge (category={category}, limit={limit})")
    result = client.rpc(
        "match_knowledge",
        {
            "query_embedding": query_embedding,
            "match_category": category,
            "match_limit": limit,
        },
    ).execute()

    if not result.data:
        return []

    return result.data


def upsert_knowledge_doc(
    doc_id: str,
    category: str,
    title: str,
    content: str,
    embedding: list[float],
    metadata: dict | None = None,
) -> dict:
    """
    Insert or update a knowledge document with its embedding.
    Used during knowledge base seeding.

    Returns: {"upserted": True, "doc_id": "...", "table": "knowledge_embeddings"}
    """
    client = get_supabase_client()

    row = {
        "doc_id": doc_id,
        "category": category,
        "title": title,
        "content": content,
        "embedding": embedding,
        "metadata": metadata or {},
    }

    result = (
        client.table("knowledge_embeddings")
        .upsert(row)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Supabase upsert failed for doc_id={doc_id}")

    return {
        "upserted": True,
        "doc_id": doc_id,
        "table": "knowledge_embeddings",
    }


def get_knowledge_count() -> int:
    """Return total number of documents in knowledge_embeddings."""
    client = get_supabase_client()
    result = client.table("knowledge_embeddings").select("doc_id", count="exact").execute()
    return result.count or 0


# ============================================================
# chat operations (chatbot vector search)
# ============================================================

def update_call_embedding(call_id: str, embedding: list[float]) -> None:
    """
    Store the summary_for_rag embedding in call_analyses.
    Called after Step 3 of the main pipeline so chatbot can vector-search calls.
    """
    client = get_supabase_client()
    logger.info(f"DB UPDATE summary_embedding ({call_id})")
    client.table("call_analyses").update(
        {"summary_embedding": embedding}
    ).eq("call_id", call_id).execute()


def search_calls(
    query_embedding: list[float],
    limit: int = 3,
) -> list[dict]:
    """
    Vector similarity search against call_analyses via match_calls RPC.
    Returns past calls ranked by semantic similarity to the query.
    """
    client = get_supabase_client()
    logger.info(f"DB RPC match_calls (limit={limit})")
    result = client.rpc(
        "match_calls",
        {
            "query_embedding": query_embedding,
            "match_limit": limit,
        },
    ).execute()
    return result.data if result.data else []
