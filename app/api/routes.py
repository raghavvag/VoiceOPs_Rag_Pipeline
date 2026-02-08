"""
API routes for the RAG service.
Step 1: Receive & Validate the NLP payload.
Step 2: Store call record in Supabase.
"""

from fastapi import APIRouter, HTTPException
from app.models.schemas import CallRiskInput, CallAnalysisResponse
from app.utils.id_generator import generate_call_id, generate_call_timestamp
from app.services.ingestion import store_call_record
from app.db.queries import get_call_by_id

router = APIRouter(prefix="/api/v1", tags=["RAG Pipeline"])


@router.post("/analyze-call")
async def analyze_call(payload: CallRiskInput):
    """
    Main pipeline endpoint.
    Receives structured risk JSON from NLP service,
    grounds it against knowledge base, returns assessment.

    Current implementation: Step 1 (Receive & Validate) only.
    Steps 2-8 will be wired in as services are built.
    """

    # --- Step 1: Receive & Validate ---
    # Pydantic already validated the payload at this point.
    # If we reached here, the input is valid.

    call_id = generate_call_id()
    call_timestamp = generate_call_timestamp()

    # --- Step 2: Store Call Record ---
    try:
        ingestion_result = store_call_record(
            call_id=call_id,
            call_timestamp=call_timestamp,
            payload=payload,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store call record: {str(e)}",
        )

    # TODO: Step 3 — Embed summary_for_rag (embedding.py)
    # TODO: Step 4 — Retrieve knowledge chunks (retrieval.py)
    # TODO: Step 5 — Build grounding context (context_builder.py)
    # TODO: Step 6 — LLM grounded reasoning (reasoning.py)
    # TODO: Step 7 — Store RAG output (updater.py)

    # --- Step 8: Return Response ---
    # For now, return confirmation that Steps 1-2 are complete.
    return {
        "call_id": call_id,
        "call_timestamp": call_timestamp.isoformat(),
        "status": "stored",
        "input_risk_assessment": payload.risk_assessment.model_dump(),
        "ingestion": ingestion_result,
        "message": "Steps 1-2 complete. Payload validated and stored. Pipeline steps 3-8 not yet wired.",
    }


@router.get("/call/{call_id}")
async def get_call(call_id: str):
    """
    Get a single call analysis by call_id.
    Returns the full call record including rag_output (if available).
    """
    try:
        record = get_call_by_id(call_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Call not found: {call_id}",
        )

    return record
