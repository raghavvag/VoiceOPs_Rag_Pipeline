"""
Retrieval service — Step 4: Retrieve Knowledge Chunks.
Uses the query embedding from Step 3 to perform semantic search
against the knowledge_embeddings table in Supabase via pgvector.

Retrieves three categories:
  4A — Fraud patterns
  4B — Compliance guidance
  4C — Risk heuristics
"""

import os
import logging
from app.db.queries import search_knowledge

logger = logging.getLogger("rag.retrieval")


def retrieve_knowledge_chunks(query_embedding: list[float]) -> dict:
    """
    Perform semantic search against the curated knowledge base.
    Searches across three categories with configurable limits.

    Args:
        query_embedding: 1536-dim embedding vector from Step 3.

    Returns:
        {
            "fraud_patterns": [ { doc_id, title, content, similarity }, ... ],
            "compliance_docs": [ ... ],
            "risk_heuristics": [ ... ],
        }

    Raises:
        RuntimeError: If any knowledge retrieval fails.
    """
    fraud_limit = int(os.getenv("FRAUD_PATTERN_RETRIEVAL_LIMIT", "3"))
    compliance_limit = int(os.getenv("COMPLIANCE_RETRIEVAL_LIMIT", "2"))
    heuristic_limit = int(os.getenv("RISK_HEURISTIC_RETRIEVAL_LIMIT", "2"))

    logger.info(f"   Retrieval limits → fraud={fraud_limit}, compliance={compliance_limit}, heuristic={heuristic_limit}")

    try:
        # 4A — Fraud Pattern Retrieval
        logger.info("   4A │ Searching fraud_pattern...")
        fraud_patterns = search_knowledge(
            query_embedding=query_embedding,
            category="fraud_pattern",
            limit=fraud_limit,
        )
        for doc in fraud_patterns:
            logger.info(f"      → [{doc['doc_id']}] {doc['title']} (sim={doc['similarity']:.4f})")

        # 4B — Compliance Guidance Retrieval
        logger.info("   4B │ Searching compliance...")
        compliance_docs = search_knowledge(
            query_embedding=query_embedding,
            category="compliance",
            limit=compliance_limit,
        )
        for doc in compliance_docs:
            logger.info(f"      → [{doc['doc_id']}] {doc['title']} (sim={doc['similarity']:.4f})")

        # 4C — Risk Heuristic Retrieval
        logger.info("   4C │ Searching risk_heuristic...")
        risk_heuristics = search_knowledge(
            query_embedding=query_embedding,
            category="risk_heuristic",
            limit=heuristic_limit,
        )
        for doc in risk_heuristics:
            logger.info(f"      → [{doc['doc_id']}] {doc['title']} (sim={doc['similarity']:.4f})")

    except Exception as e:
        logger.error(f"   ✗ Knowledge retrieval failed: {str(e)}")
        raise RuntimeError(f"Knowledge retrieval failed: {str(e)}")

    total = len(fraud_patterns) + len(compliance_docs) + len(risk_heuristics)
    logger.info(f"   ✓ Total knowledge chunks retrieved: {total}")

    return {
        "fraud_patterns": fraud_patterns,
        "compliance_docs": compliance_docs,
        "risk_heuristics": risk_heuristics,
    }
