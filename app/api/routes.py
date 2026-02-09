"""
API routes for the RAG service.
Steps 1-8: Full pipeline from validation to grounded assessment.
"""

import logging
import math
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    CallRiskInput, CallAnalysisResponse,
    ChatRequest, ChatResponse, ChatSource, ChatMetadata,
    DashboardStats, RecentActivityItem, PatternCount, StatusUpdate, PaginationMeta,
)
from app.utils.id_generator import generate_call_id, generate_call_timestamp
from app.services.ingestion import store_call_record
from app.services.embedding import embed_text
from app.services.retrieval import retrieve_knowledge_chunks
from app.services.context_builder import build_grounding_context
from app.services.reasoning import run_grounded_reasoning
from app.services.updater import store_rag_output
from app.services.seeding import seed_knowledge_base
from app.services.chat_retrieval import retrieve_for_chat, extract_call_ids, lookup_calls_by_id
from app.services.chat_context import build_chat_context
from app.services.chat_reasoning import run_chat_reasoning
from app.db.queries import (
    get_call_by_id, get_knowledge_count, update_call_embedding,
    get_dashboard_stats, get_recent_activity, get_top_patterns,
    get_active_cases, update_call_status, get_calls_paginated,
)

def status_from_risk_score(score: int) -> str:
    """Derive initial case status from NLP risk_score."""
    if score < 30:
        return "resolved"
    elif score <= 50:
        return "in_review"
    else:
        return "escalated"

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

    # --- Step 3b: Store embedding for chatbot vector search ---
    try:
        update_call_embedding(call_id, query_embedding)
    except Exception as e:
        logger.warning(f"[{call_id}] STEP 3b | Embedding storage failed (non-fatal): {str(e)}")

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

    # --- Step 7b: Set initial status from risk_score ---
    try:
        initial_status = status_from_risk_score(payload.risk_assessment.risk_score)
        update_call_status(call_id, initial_status)
        logger.info(f"[{call_id}] STEP 7b | status={initial_status} (risk_score={payload.risk_assessment.risk_score})")
    except Exception as e:
        logger.warning(f"[{call_id}] STEP 7b | Status update failed (non-fatal): {str(e)}")

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


# ============================================================
# Chatbot Endpoint
# ============================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Knowledge query chatbot.
    Accepts a natural language question, searches knowledge base + call history
    via vector similarity, and returns a grounded answer with citations.
    """
    # --- Pre-check: Knowledge base must be seeded ---
    if request.filters.search_knowledge:
        try:
            kb_count = get_knowledge_count()
        except Exception:
            kb_count = 0
        if kb_count == 0:
            raise HTTPException(
                status_code=503,
                detail="Knowledge base is empty. Run POST /api/v1/knowledge/seed first.",
            )

    logger.info(f"CHAT | Question: {request.question[:80]}...")

    # --- Detect call IDs in question for direct lookup ---
    mentioned_call_ids = extract_call_ids(request.question)
    direct_lookups = []
    if mentioned_call_ids:
        direct_lookups = lookup_calls_by_id(mentioned_call_ids)
        logger.info(f"CHAT | Direct call lookup: {len(direct_lookups)}/{len(mentioned_call_ids)} found")

    # --- Step 1: Embed the question ---
    try:
        query_embedding = embed_text(request.question)
        logger.info(f"CHAT | Embedded question | dim={len(query_embedding)}")
    except Exception as e:
        logger.error(f"CHAT | Embedding failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to embed question: {str(e)}")

    # --- Step 2: Retrieve relevant documents ---
    try:
        retrieved = retrieve_for_chat(
            query_embedding=query_embedding,
            search_knowledge_flag=request.filters.search_knowledge,
            search_calls_flag=request.filters.search_calls,
            categories=request.filters.categories,
            knowledge_limit=request.filters.knowledge_limit,
            calls_limit=request.filters.calls_limit,
        )
        logger.info(f"CHAT | Retrieved knowledge={len(retrieved['knowledge_docs'])} calls={len(retrieved['call_docs'])}")
    except Exception as e:
        logger.error(f"CHAT | Retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

    # Merge direct lookups into call_docs (avoid duplicates)
    existing_call_ids = {c.get("call_id") for c in retrieved["call_docs"]}
    for lookup in direct_lookups:
        if lookup["call_id"] not in existing_call_ids:
            retrieved["call_docs"].append(lookup)

    # --- Step 3: Build chat context ---
    history_dicts = [msg.model_dump() for msg in request.conversation_history]
    chat_ctx = build_chat_context(
        question=request.question,
        knowledge_docs=retrieved["knowledge_docs"],
        call_docs=retrieved["call_docs"],
        conversation_history=history_dicts,
    )

    # --- Step 4: LLM answer generation ---
    try:
        llm_result = run_chat_reasoning(chat_ctx)
        logger.info(f"CHAT | LLM done | {llm_result['tokens_used']} tokens")
    except Exception as e:
        logger.error(f"CHAT | LLM failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM reasoning failed: {str(e)}")

    # --- Step 5: Build sources list ---
    sources = []
    referenced_ids = set(llm_result.get("source_ids", []))

    for doc in retrieved["knowledge_docs"]:
        sources.append(ChatSource(
            type="knowledge",
            doc_id=doc.get("doc_id", ""),
            category=doc.get("category", ""),
            title=doc.get("title", ""),
            similarity=round(doc.get("similarity", 0), 4),
        ))

    for call in retrieved["call_docs"]:
        sources.append(ChatSource(
            type="call",
            doc_id=call.get("call_id", ""),
            category="call_analysis",
            title=f"Risk={call.get('risk_score', '?')} | {call.get('fraud_likelihood', '?')}",
            similarity=round(call.get("similarity", 0), 4),
        ))

    # --- Step 6: Return response ---
    return ChatResponse(
        answer=llm_result["answer"],
        sources=sources,
        metadata=ChatMetadata(
            knowledge_docs_searched=len(retrieved["knowledge_docs"]),
            calls_searched=len(retrieved["call_docs"]),
            model=llm_result["model"],
            tokens_used=llm_result["tokens_used"],
        ),
    )


# ============================================================
# Dashboard Endpoints
# ============================================================

@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats():
    """KPI numbers for the hero stats row + risk distribution."""
    try:
        stats = get_dashboard_stats()
    except Exception as e:
        logger.error(f"DASHBOARD | stats failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

    return DashboardStats(
        total_calls=stats.get("total_calls", 0),
        total_calls_today=stats.get("total_calls_today", 0),
        high_risk_count=stats.get("high_risk_count", 0),
        medium_risk_count=stats.get("medium_risk_count", 0),
        low_risk_count=stats.get("low_risk_count", 0),
        avg_risk_score=stats.get("avg_risk_score") or 0.0,
        resolution_rate=stats.get("resolution_rate") or 0.0,
        status_breakdown=stats.get("status_breakdown") or {},
    )


@router.get("/dashboard/recent-activity")
async def dashboard_recent_activity(
    limit: int = Query(default=5, ge=1, le=20),
):
    """Last N calls with outcomes for the activity timeline."""
    try:
        items = get_recent_activity(limit)
    except Exception as e:
        logger.error(f"DASHBOARD | recent-activity failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch recent activity: {str(e)}")
    return {"recent_activity": items}


@router.get("/dashboard/top-patterns")
async def dashboard_top_patterns(
    limit: int = Query(default=10, ge=1, le=20),
):
    """Aggregated pattern frequency across all calls."""
    try:
        patterns = get_top_patterns(limit)
    except Exception as e:
        logger.error(f"DASHBOARD | top-patterns failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch patterns: {str(e)}")
    return {"patterns": patterns}


@router.get("/dashboard/active-cases")
async def dashboard_active_cases(
    limit: int = Query(default=3, ge=1, le=10),
):
    """Top N highest-risk unresolved cases."""
    try:
        cases, total_active = get_active_cases(limit)
    except Exception as e:
        logger.error(f"DASHBOARD | active-cases failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch active cases: {str(e)}")
    return {"active_cases": cases, "total_active": total_active}


@router.get("/dashboard/health")
async def dashboard_health():
    """System health indicator for dashboard status badge."""
    db_ok = False
    kb_count = 0
    embedding_ok = False

    # Check database
    try:
        kb_count = get_knowledge_count()
        db_ok = True
    except Exception:
        pass

    # Check embedding service
    try:
        embed_text("health check")
        embedding_ok = True
    except Exception:
        pass

    overall = "healthy" if (db_ok and kb_count > 0 and embedding_ok) else "degraded"
    return {
        "status": overall,
        "components": {
            "database": db_ok,
            "knowledge_base": {"ready": kb_count > 0, "doc_count": kb_count},
            "embedding_service": embedding_ok,
        },
    }


# ============================================================
# Case Management Endpoints
# ============================================================

@router.patch("/call/{call_id}/status")
async def patch_call_status(call_id: str, body: StatusUpdate):
    """Update case status (e.g., mark as resolved after review)."""
    logger.info(f"PATCH status | {call_id} → {body.status}")

    # Check call exists
    existing = get_call_by_id(call_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Call not found: {call_id}")

    try:
        update_call_status(call_id, body.status)
    except Exception as e:
        logger.error(f"PATCH status failed for {call_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

    return {"call_id": call_id, "status": body.status, "updated": True}


@router.get("/calls")
async def list_calls(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    status: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    sort: str = Query(default="recent"),
):
    """Paginated call listing with optional filters."""
    # Validate filter values
    valid_statuses = {"open", "in_review", "escalated", "resolved"}
    if status and status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status. Allowed: {valid_statuses}")

    valid_risks = {"high_risk", "medium_risk", "low_risk"}
    if risk and risk not in valid_risks:
        raise HTTPException(status_code=422, detail=f"Invalid risk. Allowed: {valid_risks}")

    try:
        calls, total = get_calls_paginated(
            page=page, limit=limit,
            status_filter=status, risk_filter=risk, sort=sort,
        )
    except Exception as e:
        logger.error(f"GET /calls failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch calls: {str(e)}")

    total_pages = math.ceil(total / limit) if total > 0 else 1
    return {
        "calls": calls,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
        },
    }
