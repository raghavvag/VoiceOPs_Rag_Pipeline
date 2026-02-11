# VoiceOps RAG Pipeline — Hackathon Pitch

---

## One Liner

> We built a **Retrieval-Augmented Generation pipeline** that takes raw call risk signals, grounds them against a curated knowledge base of fraud patterns, compliance rules, and risk heuristics — and layers on **Backboard AI** for full reasoning traceability — turning black-box scores into **explainable, auditable, and defensible** risk assessments.

---

## The Problem

Financial institutions process thousands of collection calls daily. NLP models can extract intent, sentiment, and risk scores — but these are **raw numbers without context**.

| Pain Point | Impact |
|---|---|
| A risk score of 78 means nothing without knowing *why* | Analysts waste time investigating blindly |
| Regulators demand explainability — "the AI said so" isn't acceptable | Compliance violations, fines |
| Compliance teams can't audit what they can't understand | No traceability = no trust |
| Fraud patterns evolve, but hardcoded rules don't | Missed detections, stale systems |
| No cross-call learning — each call is analyzed in isolation | Repeat fraud patterns go unnoticed |

---

## Our Solution

A **3-layer intelligent system** that sits between the NLP service and the frontend:

```
Layer 1: RAG Pipeline           — Ground risk signals against knowledge base
Layer 2: Backboard AI Audit     — Store full reasoning trace for every call
Layer 3: Intelligent Chatbot    — Query knowledge, calls, and cross-call memory
```

Instead of just saying **"risk = 78"**, we say:

> *"This call matches the 'Conditional Promise with Contradiction' pattern (fp_001). The customer's conditional repayment language combined with detected statement contradictions correlates with a 73% non-payment rate. Recommend escalation to compliance per RBI verbal commitment guidelines."*

And a judge or compliance officer can then ask:

> *"Why was this call flagged as high risk?"*

And get a full reasoning chain — what signals the AI saw, what knowledge it matched, and how it reached its conclusion.

---

## System Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │               CALL AUDIO                     │
                    └──────────────────┬───────────────────────────┘
                                       │
                    ┌──────────────────▼───────────────────────────┐
                    │            NLP SERVICE                        │
                    │  (speech-to-text, intent, sentiment, risk)    │
                    └──────────────────┬───────────────────────────┘
                                       │  Structured JSON
                                       │  (risk signals)
              ┌────────────────────────▼────────────────────────┐
              │          RAG PIPELINE (this repo)                │
              │                                                  │
              │   ┌──────────┐  ┌─────────────┐  ┌───────────┐ │
              │   │ Validate  │→ │  Embed &     │→ │ Retrieve  │ │
              │   │ (Pydantic)│  │  Store in DB │  │ Knowledge │ │
              │   └──────────┘  └─────────────┘  └─────┬─────┘ │
              │                                         │       │
              │   ┌──────────────────────┐              │       │
              │   │  Build Grounding     │◀─────────────┘       │
              │   │  Context             │                      │
              │   └──────────┬───────────┘                      │
              │              │                                   │
              │   ┌──────────▼───────────┐  ┌────────────────┐  │
              │   │  Backboard AI        │  │  GPT-4o-mini   │  │
              │   │  (log signals+context)│→ │  Reasoning     │  │
              │   └──────────────────────┘  └────────┬───────┘  │
              │                                      │          │
              │   ┌──────────────────────┐           │          │
              │   │  Backboard AI        │◀──────────┘          │
              │   │  (log LLM output)    │                      │
              │   └──────────────────────┘                      │
              │              │                                   │
              │   ┌──────────▼───────────┐                      │
              │   │  Store output +      │                      │
              │   │  Auto-set status     │                      │
              │   └──────────┬───────────┘                      │
              └──────────────┼──────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────────────────┐
          │                  │                               │
   ┌──────▼──────┐   ┌──────▼──────────┐   ┌───────────────▼──┐
   │  Supabase   │   │   Backboard AI  │   │    OpenAI API    │
   │  PostgreSQL │   │   Memory Layer  │   │  Embed + Reason  │
   │  + pgvector │   │   Audit Threads │   └──────────────────┘
   └──────┬──────┘   └────────┬────────┘
          │                   │
   ┌──────▼───────────────────▼──────────────────┐
   │              FRONTEND                        │
   │  Dashboard ─ Chatbot ─ Audit Trail Viewer    │
   └──────────────────────────────────────────────┘
```

---

## How It Works — Complete 10-Step Pipeline

Every call goes through this pipeline when `POST /api/v1/analyze-call` is called:

### Step 1: Validate Input
Pydantic validates all 20+ fields from the NLP service. Invalid data → 422 error with details.

```
Input:  risk_score=78, sentiment=stressed, contradictions=true
Result: ✅ Validated — proceed
```

### Step 2: Store Raw Record
Store the full call data in Supabase `call_analyses` table with a unique call_id.

```
call_id:     call_2026_02_10_cff45c
DB table:    call_analyses
Fields saved: call_context, nlp_insights, risk_signals, risk_assessment, etc.
```

### Step 3: Embed Summary
Convert `summary_for_rag` into a 1536-dimension vector using OpenAI `text-embedding-3-small`.

```
Input:  "Customer made a conditional repayment promise..."
Output: [0.0123, -0.0456, 0.0789, ...] (1536 floats)
```

This embedding is stored in Supabase so the chatbot can vector-search past calls later.

### Step 4: Retrieve Knowledge (Vector Search)
Cosine similarity search against 3 knowledge categories using pgvector:

```
Query embedding vs knowledge base:
├── Fraud Patterns:     3 matched (fp_001: 0.73, fp_005: 0.63, fp_004: 0.57)
├── Compliance Rules:   2 matched (comp_002: 0.57, comp_005: 0.51)
└── Risk Heuristics:    2 matched (rh_001: 0.61, rh_003: 0.58)
```

### Step 5: Build Grounding Context
Assemble a structured prompt combining:
- All call signals (intent, sentiment, risk flags)
- Top matching fraud patterns with similarity scores
- Relevant compliance rules
- Risk interpretation heuristics

```
=== CALL SIGNALS ===
Intent: repayment_promise (confidence: 0.60, conditionality: high)
Sentiment: stressed (confidence: 0.82)
Contradictions Detected: YES
Risk Score: 78 | Fraud Likelihood: high

=== MATCHED FRAUD PATTERNS ===
[1] (0.73) Conditional Promise with Contradiction
    73% of such calls result in non-payment...

=== COMPLIANCE GUIDANCE ===
[1] (0.57) Verbal Commitment Assessment Guidelines
    Verbal commitments with high conditionality should not be treated as binding...
```

### Step 5b: Backboard AI — Log Signals & Context (NEW)
Create a Backboard thread for this call. Store the raw signals and grounding context as the first 2 messages.

```
Backboard Thread: 0d9324d2-56f0-4b29-94c4-0870fea9adb0
Message 1: [CALL SIGNALS] — full NLP payload
Message 2: [GROUNDING CONTEXT] — assembled context with knowledge matches
```

*Fire-and-forget — if Backboard is down, pipeline continues normally.*

### Step 6: LLM Grounded Reasoning
GPT-4o-mini receives the grounding context and returns structured JSON:

```json
{
  "grounded_assessment": "high_risk",
  "explanation": "The call exhibits multiple high-risk indicators, including 
    a conditional repayment promise, stress in the customer's sentiment, and 
    contradictions. These factors align closely with pattern fp_001 
    'Conditional Promise with Contradiction' which has a 73% non-payment rate.",
  "recommended_action": "escalate_to_compliance",
  "confidence": 0.81,
  "regulatory_flags": [],
  "matched_patterns": ["Conditional Promise with Contradiction", "Evasive Response Pattern"]
}
```

**Key LLM rules enforced by system prompt:**
- Never use accusatory language ("fraudster", "liar")
- Must cite specific knowledge patterns
- Must return valid JSON with all 6 fields
- Cannot override the NLP risk score
- Falls back to `manual_review` if LLM is unavailable

### Step 6b: Backboard AI — Log LLM Output (NEW)
Store the LLM's reasoning output as the 3rd message in the Backboard thread.

```
Message 3: [LLM REASONING OUTPUT] — full JSON assessment
```

**Now the complete reasoning chain is permanently auditable:**
`Signal inputs → Knowledge matches → LLM decision`

### Step 7: Store RAG Output
Persist the `rag_output` JSON into the `call_analyses` table.

### Step 7b: Auto-Set Case Status
Automatically derive case status from risk score:

| Risk Score | Auto-Status |
|---|---|
| 0–29 | `resolved` |
| 30–50 | `in_review` |
| 51–100 | `escalated` |

### Step 8: Return Response
Final response includes everything + the Backboard thread_id:

```json
{
  "call_id": "call_2026_02_10_cff45c",
  "call_timestamp": "2026-02-10T07:02:17+00:00",
  "input_risk_assessment": { "risk_score": 78, "fraud_likelihood": "high", "confidence": 0.81 },
  "rag_output": {
    "grounded_assessment": "high_risk",
    "explanation": "The call matches 'Conditional Promise with Contradiction'...",
    "recommended_action": "escalate_to_compliance",
    "confidence": 0.81,
    "matched_patterns": ["Conditional Promise with Contradiction", "Evasive Response Pattern"]
  },
  "backboard_thread_id": "0d9324d2-56f0-4b29-94c4-0870fea9adb0"
}
```

---

## The Knowledge Base

**16 expert-written documents** stored as embeddings in Supabase pgvector:

| Category | Count | Examples |
|---|---|---|
| Fraud Patterns | 6 | "Conditional Promise with Contradiction" (73% non-payment), "Third-Party Impersonation" (critical severity), "Aggressive Deflection" (78% non-payment) |
| Compliance Rules | 5 | "Verbal Commitment Assessment Guidelines", "Escalation Protocol for High-Risk Calls", "Prohibited Language in Risk Assessments" |
| Risk Heuristics | 5 | "Risk Score Interpretation: Low (0-40)", "Medium (41-70)", "High (71-100)" |

**How retrieval works:** When a call comes in, we embed its summary and find the **most semantically similar** documents — not keyword matching, but **meaning-based retrieval** using cosine similarity on 1536-dim vectors.

**Extensibility:** Adding a new fraud pattern = add a JSON entry to `knowledge/fraud_patterns.json` and run `POST /knowledge/seed`. No code changes needed.

---

## The Chatbot — Intelligence Layer

The chatbot turns the entire system into an **interactive knowledge + analytics assistant**.

### What It Can Do

| Query Type | Example | How It Works |
|---|---|---|
| Knowledge Query | "What fraud patterns involve contradictions?" | Vector search knowledge base → cite fp_001 |
| Call Lookup | "Tell me about call_2026_02_10_cff45c" | Direct DB lookup → full record + reasoning |
| Temporal Query (NEW) | "Summarize last 5 calls" | `get_recent_calls(5)` + Backboard memory |
| Trend Analysis (NEW) | "What happened in the last 10 days?" | Temporal fetch + cross-call memory |
| Multi-turn | "Which of those has the highest risk?" | Conversation history for context |

### Chatbot Flow

```
User: "Summarize last 5 calls and their risk patterns"
        │
        ▼
   Detect temporal query → regex: "last 5 calls"
        │
   ┌────┴──────────────────────────────────┐
   │                                       │
   ▼                                       ▼
 Fetch 5 most recent                 Query Backboard
 calls from DB                       cross-call memory
   │                                       │
   ▼                                       ▼
 Embed question → vector search      Memory enrichment
   │                                       │
   └────────────┬──────────────────────────┘
                ▼
    Build context (calls + knowledge + memory)
                │
                ▼
    GPT-4o-mini → answer with citations
                │
                ▼
    "Here are the last 5 calls analyzed:
     1. call_xxx — Risk: 78 (High) — Conditional promise...
     2. call_yyy — Risk: 15 (Low) — Firm commitment...
     Overall: 2 high-risk, 1 medium, 2 low. Most common 
     pattern: Conditional Promise."
```

### Before vs After Backboard

| User Types | Before Backboard | After Backboard |
|---|---|---|
| "Summarize last 5 calls" | ❌ "I don't have enough information" | ✅ Full summary with risk breakdown |
| "What patterns are trending?" | ❌ Generic knowledge-base answer | ✅ Aggregated patterns from memory |
| "Why was this call high risk?" | ⚠️ "Risk score is 78" | ✅ Full reasoning chain: signals → knowledge → logic |
| "Compare recent escalated calls" | ❌ Failed | ✅ Temporal data + cross-call insights |

---

## Backboard AI — Reasoning Audit Layer

**Backboard AI** provides persistent reasoning threads and cross-call memory.

### What It Stores Per Call

Every analyzed call creates a Backboard thread with exactly 3 messages:

```
Thread: 0d9324d2-56f0-4b29-94c4-0870fea9adb0
├── Message 1: [CALL SIGNALS]       — raw NLP payload (intent, sentiment, flags)
├── Message 2: [GROUNDING CONTEXT]  — assembled context + matched knowledge
└── Message 3: [LLM REASONING]      — final assessment with citations
```

### What You Can Do With It

| Feature | Endpoint | Example |
|---|---|---|
| View audit trail | `GET /backboard/{call_id}` | See full reasoning chain for any call |
| Ask about a call | `POST /backboard/{call_id}/query` | "Why was this escalated?" → detailed answer |
| Query cross-call memory | `POST /backboard/memory/query` | "Most common fraud patterns this week?" |
| List all threads | `GET /backboard/threads/all` | Admin view of all audit trails |

### Live Test: Asking Backboard About a Call

```
POST /api/v1/backboard/call_2026_02_10_cff45c/query
Body: {"question": "Why was this call flagged as high risk?"}

Response:
"The call was flagged as high risk due to:
1. Conditional Repayment Promise — highly conditional, weak commitment
2. Stressed Sentiment (0.82 confidence) — associated with avoidance
3. Contradictions in Statements — undermines reliability of commitments
4. Evasive Responses — linked to non-payment behaviors
5. Audio Quality Issues — suspicious speech patterns, low stability

These match 'Conditional Promise with Contradiction' (fp_001) and 
'Evasive Response Pattern' (fp_004), resulting in a 78% risk score 
and escalation to compliance."
```

### Zero-Risk Architecture

Every Backboard call is wrapped in `try/except`:
- If Backboard is down → pipeline runs exactly as before
- If Backboard is slow → non-blocking, doesn't delay response
- If API key is missing → logs a warning, continues normally

---

## Command Center Dashboard — 7 Endpoints

The dashboard provides real-time operational intelligence:

| Endpoint | What It Shows | Frontend Component |
|---|---|---|
| `GET /dashboard/stats` | Total calls, risk distribution, resolution rate | KPI cards at top |
| `GET /dashboard/recent-activity` | Last N calls with outcomes | Activity timeline |
| `GET /dashboard/top-patterns` | Most frequent fraud patterns | Pattern frequency chart |
| `GET /dashboard/active-cases` | Highest-risk unresolved cases | Priority case list |
| `GET /dashboard/health` | System health (DB, KB, embeddings) | Status badge |
| `PATCH /call/{id}/status` | Update case status (resolve, escalate) | Action buttons |
| `GET /calls?page=1&status=escalated` | Paginated call listing with filters | Data table |

### Dashboard Stats Example

```json
{
  "total_calls": 47,
  "total_calls_today": 12,
  "high_risk_count": 8,
  "medium_risk_count": 15,
  "low_risk_count": 24,
  "avg_risk_score": 42.3,
  "resolution_rate": 51.1,
  "status_breakdown": { "open": 3, "in_review": 12, "escalated": 9, "resolved": 23 }
}
```

---

## Complete API Reference (18 Endpoints)

| # | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | `POST` | `/api/v1/analyze-call` | Main pipeline — ground risk signals |
| 2 | `GET` | `/api/v1/call/{call_id}` | Fetch single call record |
| 3 | `PATCH` | `/api/v1/call/{call_id}/status` | Update case status |
| 4 | `GET` | `/api/v1/calls` | Paginated call listing with filters |
| 5 | `POST` | `/api/v1/chat` | Knowledge chatbot (temporal + memory) |
| 6 | `POST` | `/api/v1/knowledge/seed` | Seed knowledge base |
| 7 | `GET` | `/api/v1/knowledge/status` | Check KB status |
| 8 | `GET` | `/api/v1/dashboard/stats` | KPI numbers |
| 9 | `GET` | `/api/v1/dashboard/recent-activity` | Recent call timeline |
| 10 | `GET` | `/api/v1/dashboard/top-patterns` | Pattern frequency |
| 11 | `GET` | `/api/v1/dashboard/active-cases` | Highest-risk open cases |
| 12 | `GET` | `/api/v1/dashboard/health` | System health |
| 13 | `GET` | `/api/v1/backboard/{call_id}` | Full reasoning audit trail |
| 14 | `POST` | `/api/v1/backboard/{call_id}/query` | Ask about a call's reasoning |
| 15 | `GET` | `/api/v1/backboard/threads/all` | List all audit threads |
| 16 | `POST` | `/api/v1/backboard/memory/query` | Cross-call memory query |
| 17 | `GET` | `/health` | Basic health check |
| 18 | `POST` | `/api/v1/knowledge/seed` | Seed knowledge base |

---

## Live Demo Script for Judges

### Demo 1: Analyze a High-Risk Call (2 min)

**Step 1:** Send a call to the pipeline:
```
POST /api/v1/analyze-call
Body: { risk_score: 78, sentiment: stressed, contradictions: true ... }
```

**Step 2:** Show the response — grounded assessment with cited patterns:
```
"grounded_assessment": "high_risk"
"matched_patterns": ["Conditional Promise with Contradiction"]
"explanation": "Matches fp_001 with 73% non-payment rate..."
```

**Step 3:** Show the Backboard audit trail:
```
GET /api/v1/backboard/call_2026_02_10_cff45c
→ 3 messages: signals → context → reasoning
```

**Step 4:** Ask Backboard why:
```
POST /api/v1/backboard/call_2026_02_10_cff45c/query
{"question": "Why was this escalated?"}
→ Full reasoning chain explanation
```

**Pitch line:** *"Every AI decision is now traceable from input to output. A compliance officer can audit exactly what the AI saw and why it decided."*

### Demo 2: Chatbot Intelligence (2 min)

**Step 1:** Ask about knowledge:
```
"What fraud patterns involve contradictions?"
→ Cites fp_001 with 73% non-payment rate (from knowledge base)
```

**Step 2:** Ask about recent calls:
```
"Summarize last 5 calls"
→ Risk breakdown, pattern frequency, resolution status
```

**Step 3:** Ask cross-call insights:
```
"What fraud patterns are trending?"
→ Backboard memory aggregates patterns across ALL analyzed calls
```

**Pitch line:** *"The chatbot doesn't just answer from a static knowledge base — it remembers every call ever analyzed, detects time-based queries, and learns patterns across calls."*

### Demo 3: Dashboard (1 min)

**Show:**
- `GET /dashboard/stats` → KPI cards
- `GET /dashboard/active-cases` → highest-risk unresolved
- `PATCH /call/{id}/status` → resolve a case
- Stats update in real-time

**Pitch line:** *"Full operational dashboard with real-time KPIs, case management, and pattern tracking."*

---

## What Makes This Different

| Traditional Approach | Our VoiceOps RAG Pipeline |
|---|---|
| Hardcoded risk rules | Dynamic knowledge base (add docs, no code changes) |
| "Risk = 78" (unexplained) | "Risk = 78 because it matches fp_001 with 73% non-payment" |
| Can't audit AI decisions | Full reasoning audit trail via Backboard AI |
| No cross-call learning | Backboard memory learns patterns across all calls |
| Static chatbot (FAQ) | Intelligent chatbot: temporal queries, memory, multi-turn |
| Accusatory language risk | Compliance-safe language enforced by system prompt |
| Static thresholds | LLM reasons holistically across all signals |
| Isolated call analysis | Cross-call pattern detection and trend analysis |
| No fallback | Graceful degradation — LLM down → safe fallback; Backboard down → pipeline continues |

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| API Framework | FastAPI (Python) | Async-ready, auto-docs, Pydantic validation |
| Database | Supabase PostgreSQL + pgvector | Managed DB + native vector similarity search |
| Embeddings | OpenAI text-embedding-3-small | 1536 dims, high accuracy, low cost |
| LLM | GPT-4o-mini | Structured JSON output, fast, cost-effective |
| Audit Layer | Backboard AI | Persistent reasoning threads, cross-call memory |
| HTTP Client | httpx | Modern Python HTTP client for Backboard calls |
| Validation | Pydantic v2 | Type-safe input/output contracts |

---

## Project Structure

```
VoiceOPs_Rag_Pipeline/
├── main.py                          # FastAPI app entry point
├── requirements.txt                 # Dependencies
├── .env                             # API keys (OPENAI, SUPABASE, BACKBOARD)
│
├── app/
│   ├── api/
│   │   └── routes.py                # All 18 endpoints — pipeline, chat, dashboard, backboard
│   ├── db/
│   │   ├── supabase_client.py       # Supabase connection singleton
│   │   └── queries.py               # All database operations (15+ functions)
│   ├── models/
│   │   └── schemas.py               # Pydantic models (20+ schemas)
│   ├── services/
│   │   ├── embedding.py             # OpenAI embedding service
│   │   ├── ingestion.py             # Step 2: Store call records
│   │   ├── retrieval.py             # Step 4: Vector search knowledge
│   │   ├── context_builder.py       # Step 5: Build grounding context
│   │   ├── reasoning.py             # Step 6: GPT-4o-mini reasoning
│   │   ├── updater.py               # Step 7: Store RAG output
│   │   ├── seeding.py               # Knowledge base seeder
│   │   ├── chat_retrieval.py        # Chatbot retrieval (knowledge + calls)
│   │   ├── chat_context.py          # Chatbot context builder
│   │   ├── chat_reasoning.py        # Chatbot LLM reasoning
│   │   └── backboard_service.py     # Backboard AI integration (audit + memory)
│   └── utils/
│       └── id_generator.py          # call_id and timestamp generation
│
├── knowledge/
│   ├── fraud_patterns.json          # 6 fraud patterns
│   ├── compliance_rules.json        # 5 compliance rules
│   └── risk_heuristics.json         # 5 risk heuristics
│
└── sql/
    ├── init.sql                     # Database + pgvector + RPC functions
    └── migrate_chatbot.sql          # Chatbot migration
```

---

## Safety & Resilience

| Failure | What Happens |
|---|---|
| OpenAI API down | LLM retries once, then returns safe fallback: `manual_review` with `confidence: 0.0` |
| Backboard AI down | Pipeline completes normally. Warning logged. Zero impact. |
| Supabase down | Returns 500 with clear error message |
| Invalid input | Pydantic returns 422 with detailed field validation errors |
| Knowledge base empty | Returns 503: "Seed knowledge base first" |
| Chatbot LLM fails | Returns fallback: "Assistant temporarily unavailable" |

---

## Key Numbers

| Metric | Value |
|---|---|
| Knowledge documents | 16 (6 fraud + 5 compliance + 5 heuristic) |
| Embedding dimensions | 1536 (OpenAI text-embedding-3-small) |
| API endpoints | 18 |
| Pipeline steps | 10 (8 core + 2 Backboard audit) |
| Pydantic models | 20+ (strict input/output contracts) |
| DB query functions | 15+ |
| Service modules | 11 |
| Lines of code | ~2,000+ |
| External APIs | 3 (OpenAI, Supabase, Backboard AI) |

---

## Strong Points to Highlight for Judges

### 1. Not Just Another RAG — It's a Reasoning Audit System
Most RAG projects retrieve and answer. Ours **stores the complete reasoning chain** for every AI decision. This is enterprise-grade traceability.

### 2. Zero-Disruption Architecture
Backboard AI is a **parallel audit layer** — if it fails, the pipeline runs identically. We designed for failure from day one.

### 3. Compliance-First LLM Design
Our system prompt forbids accusatory language. The AI says "high-risk indicators" instead of "fraudster". This prevents regulatory liability — a real-world requirement for financial institutions.

### 4. Knowledge Base is a Living System
Add a new fraud pattern = add a JSON document + run seed endpoint. No code changes, no redeployment. Knowledge evolves with the business.

### 5. Chatbot That Understands Time
"Summarize last 5 calls" → actually fetches the 5 most recent calls. Most chatbots can't do temporal queries. Ours detects them with regex and enriches answers with Backboard memory.

### 6. Every Call Becomes Searchable
The moment a call is analyzed (Step 3), its embedding is stored. The chatbot can immediately find semantically similar past calls. The system gets smarter with every call.

### 7. Multi-Model Architecture
- **OpenAI text-embedding-3-small** → semantic understanding
- **GPT-4o-mini** → structured reasoning
- **Backboard AI** → audit trails + cross-call memory
- **Supabase pgvector** → managed vector similarity search

Three AI services, each handling what it does best.

### 8. Real-World Data Contracts
20+ Pydantic schemas ensure strict typing between NLP service → RAG pipeline → frontend. Zero ambiguity about what data flows where.

---

## How to Run

```bash
# 1. Clone & install
cd VoiceOPs_Rag_Pipeline
pip install -r requirements.txt

# 2. Set up .env
SUPABASE_URL=...
SUPABASE_KEY=...
OPENAI_API_KEY=...
BACKBOARD_API_KEY=...

# 3. Run SQL migrations in Supabase SQL Editor
# (init.sql → migrate_chatbot.sql → dashboard migrations)

# 4. Start server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 5. Seed knowledge base (once)
POST http://localhost:8000/api/v1/knowledge/seed

# 6. Analyze your first call
POST http://localhost:8000/api/v1/analyze-call
```

---

## Why This Matters for the Real World

> In Indian banking, the RBI requires that all AI-assisted risk decisions be explainable and auditable. A risk score alone is not sufficient for regulatory compliance. Financial institutions need to demonstrate *why* a call was flagged, *what knowledge* was used, and *how* the AI reached its conclusion.
>
> Our pipeline provides exactly this: from the raw NLP signals to the matched fraud patterns to the LLM's grounded reasoning — every step is stored, traceable, and queryable. With Backboard AI, we add cross-call learning and per-call reasoning Q&A — turning a static risk pipeline into an intelligent, auditable system.

**One-liner for judges:** *"We don't just flag risky calls — we explain why, store the reasoning chain, and let you query it in natural language. Every AI decision is auditable, every pattern is cited, and the system learns from every call it processes."*
