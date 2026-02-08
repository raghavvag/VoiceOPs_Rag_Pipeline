"""
API routes for the RAG service.
Step 1: Receive & Validate the NLP payload.
"""

from fastapi import APIRouter, HTTPException
from app.models.schemas import CallRiskInput, CallAnalysisResponse
from app.utils.id_generator import generate_call_id, generate_call_timestamp

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

    # TODO: Step 2 — Store call record (ingestion.py)
    # TODO: Step 3 — Embed summary_for_rag (embedding.py)
    # TODO: Step 4 — Retrieve knowledge chunks (retrieval.py)
    # TODO: Step 5 — Build grounding context (context_builder.py)
    # TODO: Step 6 — LLM grounded reasoning (reasoning.py)
    # TODO: Step 7 — Store RAG output (updater.py)

    # --- Step 8: Return Response ---
    # For now, return a placeholder confirming validation passed.
    return {
        "call_id": call_id,
        "call_timestamp": call_timestamp.isoformat(),
        "status": "validated",
        "input_risk_assessment": payload.risk_assessment.model_dump(),
        "message": "Step 1 complete. Payload validated. Pipeline steps 2-8 not yet wired.",
    }


@router.get("/call/{call_id}")
async def get_call(call_id: str):
    """
    Get a single call analysis by call_id.
    Will be implemented after Supabase is connected.
    """
    # TODO: Query call_analyses table
    raise HTTPException(status_code=501, detail="Not implemented yet — requires Supabase connection.")
