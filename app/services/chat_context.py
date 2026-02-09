"""
Chat context builder — assembles retrieved knowledge, call history,
conversation history, and the current question into a structured
prompt for the chatbot LLM.
"""

import logging

logger = logging.getLogger("rag.chat_context")

MAX_HISTORY_MESSAGES = 10


def build_chat_context(
    question: str,
    knowledge_docs: list[dict],
    call_docs: list[dict],
    conversation_history: list[dict],
) -> str:
    """
    Build a structured context string for the chatbot LLM.

    Args:
        question: The user's current question.
        knowledge_docs: Retrieved knowledge documents from vector search.
        call_docs: Retrieved call records from vector search.
        conversation_history: Previous messages [{role, content}, ...].

    Returns:
        A formatted context string ready for the LLM.
    """
    sections = []

    # --- Section 1: Retrieved Knowledge ---
    if knowledge_docs:
        lines = ["=== RETRIEVED KNOWLEDGE ==="]
        for i, doc in enumerate(knowledge_docs, 1):
            sim = doc.get("similarity", 0)
            cat = doc.get("category", "unknown")
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")
            doc_id = doc.get("doc_id", "?")
            lines.append(f"[{i}] ({cat}, sim={sim:.2f}) [{doc_id}] {title}")
            lines.append(f"    {content}")
            lines.append("")
        sections.append("\n".join(lines))

    # --- Section 2: Call History ---
    if call_docs:
        lines = ["=== MATCHED CALL ANALYSES ==="]
        for i, call in enumerate(call_docs, 1):
            cid = call.get("call_id", "?")
            risk = call.get("risk_score", "?")
            fraud = call.get("fraud_likelihood", "?")
            assessment = call.get("grounded_assessment", "pending")
            sim = call.get("similarity", 0)
            summary = call.get("summary_for_rag", "")
            lines.append(f"[{i}] {cid} | risk={risk} | fraud={fraud} | assessment={assessment} | sim={sim:.2f}")
            lines.append(f"    {summary}")
            lines.append("")
        sections.append("\n".join(lines))

    # --- Section 3: Conversation History (last N messages) ---
    history = conversation_history[-MAX_HISTORY_MESSAGES:]
    if history:
        lines = ["=== CONVERSATION HISTORY ==="]
        for msg in history:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        lines.append("")
        sections.append("\n".join(lines))

    # --- Section 4: Current Question ---
    sections.append(f"=== CURRENT QUESTION ===\n{question}")

    context = "\n\n".join(sections)
    logger.info(f"Chat context built | {len(context)} chars | knowledge={len(knowledge_docs)} calls={len(call_docs)} history={len(history)}")
    return context
