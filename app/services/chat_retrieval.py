"""
Chat retrieval service — searches knowledge base + call history
using vector similarity for the chatbot endpoint.
"""

import logging
from app.db.queries import search_knowledge, search_calls

logger = logging.getLogger("rag.chat_retrieval")


def retrieve_for_chat(
    query_embedding: list[float],
    search_knowledge_flag: bool = True,
    search_calls_flag: bool = False,
    categories: list[str] | None = None,
    knowledge_limit: int = 5,
    calls_limit: int = 3,
) -> dict:
    """
    Retrieve relevant documents for chatbot context.

    Args:
        query_embedding: 1536-dim vector of the user's question.
        search_knowledge_flag: Whether to search knowledge_embeddings.
        search_calls_flag: Whether to search past call_analyses.
        categories: Knowledge categories to search.
        knowledge_limit: Max knowledge docs per category.
        calls_limit: Max call records to retrieve.

    Returns:
        {
            "knowledge_docs": [ { doc_id, category, title, content, similarity }, ... ],
            "call_docs": [ { call_id, call_timestamp, summary_for_rag, risk_score, ... }, ... ],
        }
    """
    if categories is None:
        categories = ["fraud_pattern", "compliance", "risk_heuristic"]

    knowledge_docs = []
    call_docs = []

    # --- Knowledge base vector search ---
    if search_knowledge_flag:
        for cat in categories:
            try:
                results = search_knowledge(query_embedding, cat, knowledge_limit)
                knowledge_docs.extend(results)
            except Exception as e:
                logger.warning(f"Knowledge search failed for {cat}: {str(e)}")

        # Sort all knowledge docs by similarity descending, take top N
        knowledge_docs.sort(key=lambda d: d.get("similarity", 0), reverse=True)
        knowledge_docs = knowledge_docs[:knowledge_limit]
        logger.info(f"Knowledge search: {len(knowledge_docs)} docs retrieved")

    # --- Call history vector search ---
    if search_calls_flag:
        try:
            call_docs = search_calls(query_embedding, calls_limit)
            logger.info(f"Call search: {len(call_docs)} calls retrieved")
        except Exception as e:
            logger.warning(f"Call search failed: {str(e)}")

    return {
        "knowledge_docs": knowledge_docs,
        "call_docs": call_docs,
    }
