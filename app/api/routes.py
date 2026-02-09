"""
API routes for the RAG service.
Steps 1-8: Full pipeline from validation to grounded assessment.
"""

import logging
from fastapi import APIRouter, HTTPException
from app.models.schemas import CallRiskInput, CallAnalysisResponse
from app.utils.id_generator import generate_call_id, generate_call_timestamp
from app.services.ingestion import store_call_record
from app.services.embedding import embed_text
from app.services.retrieval import retrieve_knowledge_chunks
from app.services.context_builder import build_grounding_context
from app.services.reasoning import run_grounded_reasoning
from app.services.updater import store_rag_output
from app.services.seeding import seed_knowledge_base
from app.db.queries import get_call_by_id, get_knowledge_count

logger = logging.getLogger("rag.routes")

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

    # --- Pre-check: Knowledge base must be seeded ---
    try:
        kb_count = get_knowledge_count()
    except Exception:
        kb_count = 0
    if kb_count == 0:
        raise HTTPException(
            status_code=503,
            detail="Knowledge base is empty. Run POST /api/v1/knowledge/seed first.",
        )

    # --- Step 1: Receive & Validate ---
    # Pydantic already validated the payload at this point.
    # If we reached here, the input is valid.

    call_id = generate_call_id()
    call_timestamp = generate_call_timestamp()

    logger.info(f"[{call_id}] STEP 1 | Validated | risk={payload.risk_assessment.risk_score} fraud={payload.risk_assessment.fraud_likelihood}")

    # --- Step 2: Store Call Record ---
    try:
        ingestion_result = store_call_record(
            call_id=call_id,
            call_timestamp=call_timestamp,
            payload=payload,
        )
        logger.info(f"[{call_id}] STEP 2 | Stored in {ingestion_result['table']}")
    except Exception as e:
        logger.error(f"[{call_id}] STEP 2 | FAILED: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store call record: {str(e)}",
        )

    # --- Step 3: Embed summary_for_rag ---
    try:
        query_embedding = embed_text(payload.summary_for_rag)
        logger.info(f"[{call_id}] STEP 3 | Embedded summary | dim={len(query_embedding)}")
    except Exception as e:
        logger.error(f"[{call_id}] STEP 3 | FAILED: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to embed summary: {str(e)}",
        )

    # --- Step 4: Retrieve Knowledge Chunks ---
    try:
        knowledge_chunks = retrieve_knowledge_chunks(query_embedding)
        logger.info(f"[{call_id}] STEP 4 | Retrieved fraud={len(knowledge_chunks['fraud_patterns'])} compliance={len(knowledge_chunks['compliance_docs'])} heuristic={len(knowledge_chunks['risk_heuristics'])}")
    except Exception as e:
        logger.error(f"[{call_id}] STEP 4 | FAILED: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve knowledge: {str(e)}",
        )

    # --- Step 5: Build Grounding Context ---
    try:
        grounding_context = build_grounding_context(
            payload=payload,
            knowledge_chunks=knowledge_chunks,
        )
        logger.info(f"[{call_id}] STEP 5 | Context built | {len(grounding_context)} chars")
    except Exception as e:
        logger.error(f"[{call_id}] STEP 5 | FAILED: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build grounding context: {str(e)}",
        )

    # --- Step 6: LLM Grounded Reasoning ---
    try:
        rag_output = run_grounded_reasoning(grounding_context)
        logger.info(f"[{call_id}] STEP 6 | LLM done | assessment={rag_output['grounded_assessment']} action={rag_output['recommended_action']}")
    except Exception as e:
        logger.error(f"[{call_id}] STEP 6 | FAILED: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM reasoning failed: {str(e)}",
        )

    # --- Step 7: Store RAG Output ---
    try:
        update_result = store_rag_output(call_id=call_id, rag_output=rag_output)
        logger.info(f"[{call_id}] STEP 7 | rag_output stored")
    except Exception as e:
        logger.error(f"[{call_id}] STEP 7 | FAILED: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store RAG output: {str(e)}",
        )

    # --- Step 8: Return Final Response ---
    logger.info(f"[{call_id}] DONE | Pipeline complete")
    return {
        "call_id": call_id,
        "call_timestamp": call_timestamp.isoformat(),
        "input_risk_assessment": payload.risk_assessment.model_dump(),
        "rag_output": rag_output,
    }


@router.post("/knowledge/seed")
async def seed_knowledge():
    """
    Seed the knowledge base from JSON files in knowledge/ directory.
    Embeds each document and upserts into knowledge_embeddings table.
    Run ONCE before using the pipeline.
    """
    logger.info("Seeding knowledge base...")
    try:
        result = seed_knowledge_base()
        logger.info(f"Seeded {result['documents_processed']} docs | {result['by_category']}")
    except Exception as e:
        logger.error(f"Seeding failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge seeding failed: {str(e)}",
        )
    return result


@router.get("/knowledge/status")
async def knowledge_status():
    """Check how many documents are in the knowledge base."""
    try:
        count = get_knowledge_count()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check knowledge base: {str(e)}",
        )
    return {"knowledge_documents": count, "ready": count > 0}


@router.get("/call/{call_id}")
async def get_call(call_id: str):
    """
    Get a single call analysis by call_id.
    Returns the full call record including rag_output (if available).
    """
    logger.info(f"Fetching call: {call_id}")
    try:
        record = get_call_by_id(call_id)
    except Exception as e:
        logger.error(f"DB error fetching {call_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )

    if record is None:
        logger.warning(f"Call not found: {call_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Call not found: {call_id}",
        )

    return record
