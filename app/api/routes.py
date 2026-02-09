"""
API routes for the RAG service.
Step 1: Receive & Validate the NLP payload.
Step 2: Store call record in Supabase.
Step 3: Embed summary_for_rag for knowledge retrieval.
Step 4: Retrieve knowledge chunks via semantic search.
"""

import logging
from fastapi import APIRouter, HTTPException
from app.models.schemas import CallRiskInput, CallAnalysisResponse
from app.utils.id_generator import generate_call_id, generate_call_timestamp
from app.services.ingestion import store_call_record
from app.services.embedding import embed_text
from app.services.retrieval import retrieve_knowledge_chunks
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

    # --- Step 1: Receive & Validate ---
    # Pydantic already validated the payload at this point.
    # If we reached here, the input is valid.

    call_id = generate_call_id()
    call_timestamp = generate_call_timestamp()

    logger.info("═" * 60)
    logger.info("🔵 STEP 1 │ Payload validated ✓")
    logger.info(f"   call_id      : {call_id}")
    logger.info(f"   timestamp    : {call_timestamp.isoformat()}")
    logger.info(f"   risk_score   : {payload.risk_assessment.risk_score}")
    logger.info(f"   fraud_likely : {payload.risk_assessment.fraud_likelihood}")
    logger.info(f"   summary      : {payload.summary_for_rag[:80]}...")

    # --- Step 2: Store Call Record ---
    logger.info("─" * 60)
    logger.info("🟢 STEP 2 │ Storing call record in Supabase...")
    try:
        ingestion_result = store_call_record(
            call_id=call_id,
            call_timestamp=call_timestamp,
            payload=payload,
        )
        logger.info(f"   ✓ Stored in table: {ingestion_result['table']}")
    except Exception as e:
        logger.error(f"   ✗ Failed to store: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store call record: {str(e)}",
        )

    # --- Step 3: Embed summary_for_rag ---
    logger.info("─" * 60)
    logger.info("🟡 STEP 3 │ Embedding summary_for_rag via OpenAI...")
    try:
        query_embedding = embed_text(payload.summary_for_rag)
        logger.info(f"   ✓ Embedding generated — dim={len(query_embedding)}")
    except Exception as e:
        logger.error(f"   ✗ Embedding failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to embed summary: {str(e)}",
        )

    # --- Step 4: Retrieve Knowledge Chunks ---
    logger.info("─" * 60)
    logger.info("🟠 STEP 4 │ Retrieving knowledge chunks...")
    try:
        knowledge_chunks = retrieve_knowledge_chunks(query_embedding)
        logger.info(f"   ✓ fraud_patterns  : {len(knowledge_chunks['fraud_patterns'])} docs")
        logger.info(f"   ✓ compliance_docs : {len(knowledge_chunks['compliance_docs'])} docs")
        logger.info(f"   ✓ risk_heuristics : {len(knowledge_chunks['risk_heuristics'])} docs")
    except Exception as e:
        logger.error(f"   ✗ Knowledge retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve knowledge: {str(e)}",
        )

    # TODO: Step 5 — Build grounding context (context_builder.py)
    # TODO: Step 6 — LLM grounded reasoning (reasoning.py)
    # TODO: Step 7 — Store RAG output (updater.py)

    # --- Step 8: Return Response ---
    logger.info("─" * 60)
    logger.info("✅ PIPELINE │ Steps 1-4 complete — returning response")
    logger.info("═" * 60)
    # For now, return confirmation that Steps 1-4 are complete.
    return {
        "call_id": call_id,
        "call_timestamp": call_timestamp.isoformat(),
        "status": "retrieved",
        "input_risk_assessment": payload.risk_assessment.model_dump(),
        "ingestion": ingestion_result,
        "embedding_dim": len(query_embedding),
        "knowledge_chunks": {
            "fraud_patterns_count": len(knowledge_chunks["fraud_patterns"]),
            "compliance_docs_count": len(knowledge_chunks["compliance_docs"]),
            "risk_heuristics_count": len(knowledge_chunks["risk_heuristics"]),
            "details": knowledge_chunks,
        },
        "message": "Steps 1-4 complete. Payload validated, stored, embedded, and knowledge retrieved. Pipeline steps 5-8 not yet wired.",
    }


@router.post("/knowledge/seed")
async def seed_knowledge():
    """
    Seed the knowledge base from JSON files in knowledge/ directory.
    Embeds each document and upserts into knowledge_embeddings table.
    Run ONCE before using the pipeline.
    """
    logger.info("🌱 Knowledge seeding requested...")
    try:
        result = seed_knowledge_base()
        logger.info(f"   ✓ Seeded {result['documents_processed']} docs → {result['by_category']}")
    except Exception as e:
        logger.error(f"   ✗ Seeding failed: {str(e)}")
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
    logger.info(f"📋 Fetching call record: {call_id}")
    try:
        record = get_call_by_id(call_id)
    except Exception as e:
        logger.error(f"   ✗ DB error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )

    if record is None:
        logger.warning(f"   ✗ Call not found: {call_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Call not found: {call_id}",
        )

    logger.info(f"   ✓ Found call: {call_id}")
    return record
