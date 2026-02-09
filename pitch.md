# VoiceOps RAG Pipeline — Pitch

## One Liner

> We built a **Retrieval-Augmented Generation pipeline** that takes raw call risk signals and grounds them against a curated knowledge base of fraud patterns, compliance rules, and risk heuristics — turning black-box scores into **explainable, auditable, and defensible** risk assessments.

---

## The Problem

Financial institutions process thousands of collection calls daily. NLP models extract intent, sentiment, and risk scores — but these are **raw numbers without context**.

- A risk score of 78 means nothing without knowing *why*
- Regulators demand explainability — "the AI said so" isn't acceptable
- Compliance teams can't audit what they can't understand
- Fraud patterns evolve, but hardcoded rules don't

---

## Our Solution

A **RAG-powered grounding layer** that sits between the NLP service and the frontend:

```
Call Audio → NLP Service → Risk Signals → RAG Pipeline → Grounded Assessment
                                              ↑
                                    Knowledge Base (pgvector)
                                    - 6 fraud patterns
                                    - 5 compliance rules
                                    - 5 risk heuristics
```

Instead of just saying "risk = 78", we say:

> *"This call matches the 'Conditional Promise with Contradiction' pattern (fp_001). The customer's conditional repayment language combined with detected statement contradictions correlates with a 73% non-payment rate. Recommend escalation to compliance per RBI verbal commitment guidelines."*

---

## How It Works — 8-Step Pipeline

```
┌─────────────────────────────────────────────────────┐
│                  POST /analyze-call                 │
└──────────────────────┬──────────────────────────────┘
                       │
          Step 1: Validate input (Pydantic)
                       │
          Step 2: Store in Supabase (call_analyses)
                       │
          Step 3: Embed summary → 1536-dim vector
                       │         (OpenAI text-embedding-3-small)
                       │
          Step 4: Vector search knowledge base
                       │    ├── fraud_patterns (cosine similarity)
                       │    ├── compliance_rules
                       │    └── risk_heuristics
                       │
          Step 5: Build grounding context
                       │    (signals + matched knowledge)
                       │
          Step 6: LLM reasoning (GPT-4o-mini)
                       │    → grounded_assessment
                       │    → explanation with citations
                       │    → recommended_action
                       │
          Step 7: Persist RAG output to DB
                       │
          Step 8: Return response
                       ▼
┌─────────────────────────────────────────────────────┐
│  { call_id, grounded_assessment, explanation,       │
│    recommended_action, confidence, matched_patterns }│
└─────────────────────────────────────────────────────┘
```

---

## The Knowledge Base

We curated **16 expert-written documents** stored as embeddings in Supabase pgvector:

| Category | Count | Example |
|---|---|---|
| Fraud Patterns | 6 | "Conditional Promise with Contradiction" — 73% non-payment rate |
| Compliance Rules | 5 | "RBI Guidelines on Verbal Commitment Recording" |
| Risk Heuristics | 5 | "Risk Score Interpretation: High Range (71-100)" |

When a call comes in, we embed its summary and find the **most semantically similar** documents — not keyword matching, but meaning-based retrieval.

---

## What Makes It Different

| Traditional Approach | Our RAG Pipeline |
|---|---|
| Hardcoded risk rules | Dynamic knowledge base (add docs anytime) |
| "Risk = 78" (unexplained) | "Risk = 78 because it matches pattern fp_001 with 73% non-payment" |
| Can't audit decisions | Every decision has cited sources |
| Accusatory language risk | Compliance-safe language enforced by system prompt |
| Static thresholds | LLM reasons across signals holistically |

---

## The Chatbot — Knowledge Query Assistant

We added an interactive chatbot that turns the knowledge base into a **searchable policy assistant**.

### How it works

```
User Question: "What fraud patterns involve contradictions?"
        │
        ▼
   Embed question → 1536-dim vector
        │
   ┌────┴─────────────────┐
   ▼                      ▼
 Knowledge Base        Call History
 (pgvector search)     (pgvector search)
   │                      │
   ▼                      ▼
 fp_001 (0.92)         call_xyz (0.57)
 comp_002 (0.54)
   │                      │
   └──────┬───────────────┘
          ▼
    Build context + conversation history
          │
          ▼
    GPT-4o-mini → Grounded answer with citations
          │
          ▼
    "The 'Conditional Promise with Contradiction'
     pattern (fp_001) is triggered when..."
```

### Key: Both searches are vector-based

The chatbot does **NOT** use SQL `WHERE` or keyword search. It uses **cosine similarity** on pgvector embeddings for both knowledge docs and past calls:

| Search Target | How | Example |
|---|---|---|
| Knowledge base | `match_knowledge` RPC — cosine similarity on `embedding` column | Question → embed → find closest fraud patterns |
| Past calls | `match_calls` RPC — cosine similarity on `summary_embedding` column | Question → embed → find semantically similar past calls |

The `summary_embedding` is stored during the main pipeline (Step 3) — every analyzed call becomes searchable by the chatbot automatically.

### Multi-turn conversations

The chatbot supports conversation history. The frontend sends previous messages, and the LLM uses them for contextual follow-ups:

```json
{
  "question": "Which of those has the highest non-payment rate?",
  "conversation_history": [
    {"role": "user", "content": "What are the main fraud patterns?"},
    {"role": "assistant", "content": "There are 6 fraud patterns..."}
  ]
}
```

---

## Live Test Results

### Test 1: High-Risk Call

**Input:** Conditional promise, stressed sentiment, contradictions detected, risk = 78

**RAG Output:**
- Assessment: `high_risk`
- Action: `escalate_to_compliance`
- Cited: "Conditional Promise with Contradiction" (fp_001)
- Confidence: 0.88

### Test 2: Low-Risk Call

**Input:** Clear promise, cooperative sentiment, no contradictions, risk = 15

**RAG Output:**
- Assessment: `low_risk`
- Action: `auto_clear`
- No fraud patterns matched
- Confidence: 0.92

### Test 3: Chatbot Query

**Question:** "What are the indicators of conditional promise fraud?"

**Answer:** Cited fp_001, comp_002 with similarity scores. Explained the 73% non-payment correlation. Professional, non-accusatory language.

---

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI (Python) |
| Database | Supabase PostgreSQL + pgvector |
| Embeddings | OpenAI text-embedding-3-small (1536 dims) |
| LLM | GPT-4o-mini (structured JSON output) |
| Validation | Pydantic v2 |

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/analyze-call` | Main pipeline — ground risk signals |
| POST | `/api/v1/chat` | Knowledge chatbot |
| GET | `/api/v1/call/{call_id}` | Fetch call record |
| POST | `/api/v1/knowledge/seed` | Seed knowledge base |
| GET | `/api/v1/knowledge/status` | Check KB status |
| GET | `/health` | Health check |

---

## Architecture Diagram

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Call Audio   │────▶│   NLP Service    │────▶│ RAG Pipeline │
│  (upstream)   │     │  (risk signals)  │     │  (this repo) │
└──────────────┘     └──────────────────┘     └──────┬───────┘
                                                     │
                     ┌───────────────────────────────┤
                     │                               │
              ┌──────▼───────┐              ┌────────▼────────┐
              │   Supabase   │              │    OpenAI API   │
              │  PostgreSQL  │              │  embed + reason │
              │  + pgvector  │              └─────────────────┘
              └──────────────┘
                     │
              ┌──────▼───────┐
              │   Frontend   │
              │  Dashboard + │
              │   Chatbot    │
              └──────────────┘
```

---

## Why This Matters

1. **Explainability** — Every risk decision is grounded in cited knowledge
2. **Auditability** — Full trail: input → matched patterns → reasoning → action
3. **Compliance** — Language guardrails prevent legal liability
4. **Extensibility** — Add new fraud patterns by adding JSON docs, no code changes
5. **Searchability** — Chatbot makes the knowledge base accessible to human analysts
6. **Scalability** — Stateless pipeline, each call is independent
