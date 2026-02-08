"""
Database query functions for the RAG service.
All Supabase table operations live here.
"""

from app.db.supabase_client import get_supabase_client


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

    result = client.table("call_analyses").insert(row).execute()

    # Supabase Python client v2 returns data in result.data
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
