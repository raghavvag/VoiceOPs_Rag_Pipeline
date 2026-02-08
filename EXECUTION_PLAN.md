# Financial Audio Intelligence — Execution Plan

## Document Purpose

This file is the **implementation blueprint** for the RAG pipeline.
It covers architecture, execution flow, folder structure, tech stack,
API contracts, database schema, and step-by-step build order.

Refer to `Rules.md` for project context and design principles.

---

# 1. Tech Stack

| Layer              | Technology                          |
| ------------------ | ----------------------------------- |
| Language           | Python 3.10.11                      |
| Framework          | FastAPI                             |
| Database           | Supabase (PostgreSQL + pgvector)    |
| Embedding Model    | OpenAI `text-embedding-3-small`     |
| LLM Reasoning      | OpenAI `gpt-4o` / `gpt-4o-mini`   |
| Vector Search      | pgvector (cosine similarity)        |
| Environment        | `.env` with `dotenv`                |
| Deployment         | Local / Docker / Cloud              |

---

# 2. Folder Structure

```
VoiceOPs_Rag_Pipeline/
│
├── Rules.md                    # Project context (source of truth)
├── EXECUTION_PLAN.md           # This file (implementation blueprint)
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
├── main.py                     # FastAPI app entry point
│
├── app/
│   ├── __init__.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py           # API endpoints
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic models (input/output)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion.py        # Step 1-2: receive + store metadata + obligations
│   │   ├── embedding.py        # Step 3-4: generate + store embeddings
│   │   ├── retrieval.py        # Step 5: history + semantic + obligation retrieval
│   │   ├── context_builder.py  # Step 6: build reasoning context
│   │   ├── reasoning.py        # Step 7: LLM risk reasoning
│   │   └── updater.py          # Step 8: update call record
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── supabase_client.py  # Supabase connection
│   │   └── queries.py          # SQL + vector queries
│   │
│   └── utils/
│       ├── __init__.py
│       ├── id_generator.py     # Auto-generate call_id
│       └── helpers.py          # Shared utilities
│
└── sql/
    └── init.sql                # Table creation scripts
```

---

# 3. Input Contract (Revised)

The RAG service receives this payload from Person-1 service:

```json
{
  "resolved_identity": {
    "loan_id": "LN102",
    "customer_id": "CUST45"
  },

  "cleaned_transcript": "salary late aaya emi pay nahi ho paaya next week kar dunga",

  "primary_insights": {
    "intent": {
      "label": "repayment_delay",
      "confidence": 0.92,
      "conditionality": "medium"
    },

    "sentiment": {
      "label": "stressed",
      "confidence": 0.88
    },

    "entities": {
      "payment_commitment": "next_week",
      "amount_mentioned": null
    },

    "risk_indicators": [
      "missed_emi",
      "salary_delay"
    ]
  },

  "summary_for_embedding": "Customer missed EMI due to salary delay and promised to make payment next week."
}
```

### Key Design Decisions on Input

| Field               | Source         | Notes                                      |
| ------------------- | -------------- | ------------------------------------------ |
| `call_id`           | Auto-generated | RAG service generates using timestamp + UUID |
| `call_timestamp`    | Auto-generated | Server UTC time at ingestion               |
| `loan_id`           | Input payload  | Nested under `resolved_identity` (nullable) |
| `customer_id`       | Input payload  | Nested under `resolved_identity` (nullable) |
| `cleaned_transcript`| Input payload  | Stored in metadata, NOT embedded           |
| `intent`            | Input payload  | Object: `label` + `confidence` + `conditionality` |
| `sentiment`         | Input payload  | Object: `label` + `confidence`             |
| `primary_insights`  | Input payload  | Stored as JSONB in `calls` table           |
| `summary_for_embedding` | Input payload | This text gets embedded into pgvector  |

---

# 4. Output Contract

The RAG service returns:

```json
{
  "call_id": "call_2026_02_08_a1b2c3",
  "loan_id": "LN102",
  "customer_id": "CUST45",
  "call_timestamp": "2026-02-08T14:30:00Z",

  "current_insights": {
    "intent": {
      "label": "repayment_delay",
      "confidence": 0.92,
      "conditionality": "medium"
    },
    "sentiment": {
      "label": "stressed",
      "confidence": 0.88
    },
    "risk_indicators": ["missed_emi", "salary_delay"]
  },

  "obligation_analysis": {
    "current_commitment": {
      "type": "payment_promise",
      "detail": "next_week",
      "amount": null,
      "conditionality": "medium"
    },
    "past_commitments": [
      {
        "call_id": "call_2026_01_25_d4e5f6",
        "commitment": "pay by month end",
        "fulfilled": false
      }
    ],
    "fulfillment_rate": 0.33,
    "broken_promises_count": 2
  },

  "risk_assessment": {
    "risk_level": "HIGH",
    "explanation": "Customer has delayed EMI payments in 3 recent calls. Salary delay is a recurring reason. Payment commitments were made but not fulfilled in prior interactions. Commitment fulfillment rate is 33%.",
    "confidence": 0.85,
    "regulatory_flags": []
  },

  "history_used": {
    "timeline_calls_retrieved": 3,
    "semantic_matches_retrieved": 2
  }
}
```

---

# 5. Database Schema

## Table: `calls`

```sql
CREATE TABLE calls (
    call_id         TEXT PRIMARY KEY,
    loan_id         TEXT,
    customer_id     TEXT,
    call_timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cleaned_transcript TEXT,
    extracted_insights JSONB,
    summary         TEXT,
    final_risk      JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calls_loan_id ON calls (loan_id);
CREATE INDEX idx_calls_timestamp ON calls (call_timestamp DESC);
```

## Table: `call_embeddings`

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE call_embeddings (
    embedding_id    TEXT PRIMARY KEY,
    call_id         TEXT REFERENCES calls(call_id),
    loan_id         TEXT NOT NULL,
    embedding       vector(1536),
    summary_text    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embeddings_loan_id ON call_embeddings (loan_id);
```

## Table: `obligations`

```sql
CREATE TABLE obligations (
    obligation_id     TEXT PRIMARY KEY,
    call_id           TEXT REFERENCES calls(call_id),
    loan_id           TEXT,
    commitment_type   TEXT NOT NULL,
    commitment_detail TEXT,
    amount            NUMERIC,
    due_context       TEXT,
    conditionality    TEXT,
    fulfilled         BOOLEAN DEFAULT NULL,
    fulfilled_by_call TEXT REFERENCES calls(call_id),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_obligations_loan_id ON obligations (loan_id);
CREATE INDEX idx_obligations_fulfilled ON obligations (fulfilled);
```

---

# 6. Execution Flow (Step-by-Step)

Below is the exact runtime sequence when a request hits the RAG service.

---

## Step 1 — Receive & Validate

**File:** `app/api/routes.py` → `app/models/schemas.py`

- FastAPI POST endpoint receives the JSON payload
- Pydantic validates the input against `CallInsightsInput` schema
- If validation fails → return 422

**Auto-generated fields:**
- `call_id` = `call_{date}_{short_uuid}` (e.g., `call_2026_02_08_a1b2c3`)
- `call_timestamp` = current UTC time

**Expected Input:**
```json
{
  "resolved_identity": {
    "loan_id": "LN102",
    "customer_id": "CUST45"
  },
  "cleaned_transcript": "salary late aaya emi pay nahi ho paaya next week kar dunga",
  "primary_insights": {
    "intent": { "label": "repayment_delay", "confidence": 0.92, "conditionality": "medium" },
    "sentiment": { "label": "stressed", "confidence": 0.88 },
    "entities": { "payment_commitment": "next_week", "amount_mentioned": null },
    "risk_indicators": ["missed_emi", "salary_delay"]
  },
  "summary_for_embedding": "Customer missed EMI due to salary delay and promised to make payment next week."
}
```

**Expected Output:**
```json
{
  "call_id": "call_2026_02_08_a1b2c3",
  "call_timestamp": "2026-02-08T14:30:00Z",
  "validated_payload": { "...full input payload..." },
  "status": "validated"
}
```

---

## Step 2 — Store Metadata + Track Obligations

**File:** `app/services/ingestion.py`

- Extract `loan_id` and `customer_id` from `resolved_identity` (handle null)
- Insert into `calls` table:
  - `call_id` (generated)
  - `loan_id`
  - `customer_id`
  - `call_timestamp` (generated)
  - `cleaned_transcript`
  - `extracted_insights` = full `primary_insights` as JSONB
  - `summary` = `summary_for_embedding`
  - `final_risk` = NULL (updated later in Step 8)
- If `payment_commitment` exists in entities → insert into `obligations` table
- Check previous unfulfilled obligations for this loan → attempt auto-resolution

**Expected Input:**
```json
{
  "call_id": "call_2026_02_08_a1b2c3",
  "loan_id": "LN102",
  "customer_id": "CUST45",
  "call_timestamp": "2026-02-08T14:30:00Z",
  "cleaned_transcript": "salary late aaya emi pay nahi ho paaya next week kar dunga",
  "extracted_insights": {
    "intent": { "label": "repayment_delay", "confidence": 0.92, "conditionality": "medium" },
    "sentiment": { "label": "stressed", "confidence": 0.88 },
    "entities": { "payment_commitment": "next_week", "amount_mentioned": null },
    "risk_indicators": ["missed_emi", "salary_delay"]
  },
  "summary": "Customer missed EMI due to salary delay and promised to make payment next week."
}
```

**Expected Output:**
```json
{
  "inserted": true,
  "call_id": "call_2026_02_08_a1b2c3",
  "table": "calls",
  "obligation_tracked": {
    "obligation_id": "obl_uuid_abc",
    "commitment_type": "payment_promise",
    "commitment_detail": "next_week",
    "conditionality": "medium"
  },
  "past_obligations_checked": 2,
  "auto_resolved": 0
}
```

---

## Step 3 — Generate Embedding

**File:** `app/services/embedding.py`

- Take `summary_for_embedding` text
- Call OpenAI embedding API (`text-embedding-3-small`)
- Returns a 1536-dim vector

**Expected Input:**
```json
{
  "text": "Customer missed EMI due to salary delay and promised to make payment next week."
}
```

**Expected Output:**
```json
{
  "embedding": [0.0123, -0.0456, 0.0789, "...1536 floats total..."]
}
```

---

## Step 4 — Store Vector Memory

**File:** `app/services/embedding.py`

- Insert into `call_embeddings` table:
  - `embedding_id` = generated UUID
  - `call_id` = from Step 1
  - `loan_id` = from input
  - `embedding` = vector from Step 3
  - `summary_text` = `summary_for_embedding`

**Expected Input:**
```json
{
  "embedding_id": "emb_uuid_xyz",
  "call_id": "call_2026_02_08_a1b2c3",
  "loan_id": "LN102",
  "embedding": [0.0123, -0.0456, "...1536 floats..."],
  "summary_text": "Customer missed EMI due to salary delay and promised to make payment next week."
}
```

**Expected Output:**
```json
{
  "inserted": true,
  "embedding_id": "emb_uuid_xyz",
  "table": "call_embeddings"
}
```

---

## Step 5 — Retrieve History + Obligations

**File:** `app/services/retrieval.py`

Three retrieval strategies:

### 5A — Loan Timeline Retrieval (SQL)

```sql
SELECT call_id, extracted_insights, summary, final_risk, call_timestamp
FROM calls
WHERE loan_id = :loan_id
  AND call_id != :current_call_id
ORDER BY call_timestamp DESC
LIMIT 5;
```

Purpose: Get the last N calls for this loan to detect repeated behavior.

### 5B — Semantic Retrieval (pgvector)

```sql
SELECT summary_text, 1 - (embedding <=> :query_embedding) AS similarity
FROM call_embeddings
WHERE loan_id = :loan_id
  AND call_id != :current_call_id
ORDER BY embedding <=> :query_embedding
LIMIT 3;
```

Purpose: Find semantically similar past situations for this loan.

### 5C — Obligation History Retrieval (SQL)

```sql
SELECT obligation_id, call_id, commitment_type, commitment_detail,
       amount, conditionality, fulfilled, created_at
FROM obligations
WHERE loan_id = :loan_id
ORDER BY created_at DESC
LIMIT 10;
```

Purpose: Get all past commitments and their fulfillment status.

**Expected Input:**
```json
{
  "loan_id": "LN102",
  "current_call_id": "call_2026_02_08_a1b2c3",
  "query_embedding": [0.0123, -0.0456, "...1536 floats..."]
}
```

**Expected Output:**
```json
{
  "timeline_calls": [
    {
      "call_id": "call_2026_01_25_d4e5f6",
      "call_timestamp": "2026-01-25T11:00:00Z",
      "extracted_insights": { "intent": { "label": "repayment_delay", "confidence": 0.85, "conditionality": "high" }, "sentiment": { "label": "neutral", "confidence": 0.75 } },
      "summary": "Customer requested EMI extension due to medical expenses.",
      "final_risk": { "risk_level": "MEDIUM", "confidence": 0.72 }
    },
    {
      "call_id": "call_2026_01_18_g7h8i9",
      "call_timestamp": "2026-01-18T09:30:00Z",
      "extracted_insights": { "intent": { "label": "partial_payment", "confidence": 0.90, "conditionality": "low" }, "sentiment": { "label": "cooperative", "confidence": 0.82 } },
      "summary": "Customer made partial payment and committed remaining by month end.",
      "final_risk": { "risk_level": "LOW", "confidence": 0.65 }
    }
  ],
  "semantic_matches": [
    {
      "summary_text": "Customer delayed EMI citing salary issues and promised next week.",
      "similarity": 0.91
    },
    {
      "summary_text": "Customer missed EMI and blamed late salary credit.",
      "similarity": 0.87
    }
  ],
  "obligation_history": [
    {
      "obligation_id": "obl_uuid_prev1",
      "call_id": "call_2026_01_25_d4e5f6",
      "commitment_type": "payment_promise",
      "commitment_detail": "by_month_end",
      "amount": null,
      "conditionality": "high",
      "fulfilled": false
    },
    {
      "obligation_id": "obl_uuid_prev2",
      "call_id": "call_2026_01_10_j1k2l3",
      "commitment_type": "payment_promise",
      "commitment_detail": "next_week",
      "amount": 5000,
      "conditionality": "low",
      "fulfilled": true
    }
  ]
}
```

---

## Step 6 — Build Reasoning Context

**File:** `app/services/context_builder.py`

Construct a structured prompt context from:

1. **Current call insights** — intent, sentiment, entities, risk indicators
2. **Timeline history** — last N calls with their insights and outcomes
3. **Semantic matches** — similar past situations and their outcomes
4. **Obligation history** — past commitments and fulfillment rates

**Expected Input:**
```json
{
  "current_insights": {
    "loan_id": "LN102",
    "intent": { "label": "repayment_delay", "confidence": 0.92, "conditionality": "medium" },
    "sentiment": { "label": "stressed", "confidence": 0.88 },
    "entities": { "payment_commitment": "next_week", "amount_mentioned": null },
    "risk_indicators": ["missed_emi", "salary_delay"],
    "summary": "Customer missed EMI due to salary delay and promised to make payment next week."
  },
  "timeline_calls": [ "...from Step 5A..." ],
  "semantic_matches": [ "...from Step 5B..." ],
  "obligation_history": [ "...from Step 5C..." ]
}
```

**Expected Output (formatted context string):**

```
=== CURRENT CALL ===
Loan ID: LN102
Intent: repayment_delay (confidence: 0.92, conditionality: medium)
Sentiment: stressed (confidence: 0.88)
Risk Indicators: missed_emi, salary_delay
Summary: Customer missed EMI due to salary delay and promised to make payment next week.

=== RECENT CALL HISTORY (Last 5) ===
[1] 2026-01-25 | Intent: repayment_delay (0.85, high) | Risk: MEDIUM | Summary: Customer requested EMI extension due to medical expenses.
[2] 2026-01-18 | Intent: partial_payment (0.90, low) | Risk: LOW | Summary: Customer made partial payment and committed remaining by month end.

=== OBLIGATION TRACKER ===
Total commitments: 3 | Fulfilled: 1 | Broken: 2 | Fulfillment rate: 33%
[1] 2026-01-25 | Promise: pay by month end | Fulfilled: NO
[2] 2026-01-10 | Promise: pay next week (₹5000) | Fulfilled: YES
[3] 2025-12-20 | Promise: pay by salary date | Fulfilled: NO

=== SIMILAR PAST SITUATIONS ===
[1] Similarity: 0.91 | Summary: Customer delayed EMI citing salary issues and promised next week.
[2] Similarity: 0.87 | Summary: Customer missed EMI and blamed late salary credit.
```

---

## Step 7 — LLM Risk Reasoning

**File:** `app/services/reasoning.py`

- Send the built context to OpenAI GPT-4o
- System prompt instructs the LLM to act as a financial risk analyst
- LLM returns structured output

**Expected Input:**
```json
{
  "system_prompt": "You are a financial risk analyst...",
  "context": "=== CURRENT CALL ===\nLoan ID: LN102\nIntent: repayment_delay\n...full context from Step 6..."
}
```

**Expected Output:**
```json
{
  "risk_level": "HIGH",
  "explanation": "Customer has delayed EMI payments in 3 recent calls. Salary delay is a recurring reason. Payment commitments were made but not fulfilled in prior interactions. Commitment fulfillment rate is 33% (1 of 3 promises kept). Current promise has medium conditionality.",
  "confidence": 0.85,
  "regulatory_flags": []
}
```

**System Prompt (core idea):**

```
You are a financial risk analyst. Based on the current call insights,
historical interaction data, and obligation fulfillment history,
assess the repayment risk for this loan.

You MUST return a JSON object with:
- risk_level: one of HIGH, MEDIUM, LOW
- explanation: concise reasoning citing specific evidence from history
  and obligation fulfillment rates
- confidence: a float between 0.0 and 1.0
- regulatory_flags: array of strings if any regulatory concerns detected
  (e.g. "threatening_language", "unauthorized_disclosure", "missing_consent")
  or empty array if none

Pay special attention to:
- Commitment fulfillment rate (broken promises = higher risk)
- Conditionality of current intent (high conditionality = less reliable)
- Patterns of repeated excuses across calls
- Whether amounts mentioned match or decrease over time

Be objective. Use evidence from the call history. If no history exists,
base your assessment on current call indicators only.
```

---

## Step 8 — Update Call Record

**File:** `app/services/updater.py`

- Update the `calls` table:

```sql
UPDATE calls
SET final_risk = :risk_assessment_json
WHERE call_id = :call_id;
```

- `final_risk` stores the complete risk assessment JSONB.

**Expected Input:**
```json
{
  "call_id": "call_2026_02_08_a1b2c3",
  "risk_assessment": {
    "risk_level": "HIGH",
    "explanation": "Customer has delayed EMI payments in 3 recent calls. Salary delay is a recurring reason. Commitment fulfillment rate is 33%.",
    "confidence": 0.85,
    "regulatory_flags": []
  }
}
```

**Expected Output:**
```json
{
  "updated": true,
  "call_id": "call_2026_02_08_a1b2c3",
  "table": "calls",
  "field": "final_risk"
}
```

---

## Step 9 — Return Response

**File:** `app/api/routes.py`

- Assemble the final response object
- Return to caller (frontend / n8n / Person-1 service)

**Expected Input (assembled internally from all previous steps):**
```
call_id, loan_id, customer_id, call_timestamp,
current_insights, risk_assessment, history_used counts
```

**Expected Output (final API response):**
```json
{
  "call_id": "call_2026_02_08_a1b2c3",
  "loan_id": "LN102",
  "customer_id": "CUST45",
  "call_timestamp": "2026-02-08T14:30:00Z",

  "current_insights": {
    "intent": {
      "label": "repayment_delay",
      "confidence": 0.92,
      "conditionality": "medium"
    },
    "sentiment": {
      "label": "stressed",
      "confidence": 0.88
    },
    "risk_indicators": ["missed_emi", "salary_delay"]
  },

  "obligation_analysis": {
    "current_commitment": {
      "type": "payment_promise",
      "detail": "next_week",
      "amount": null,
      "conditionality": "medium"
    },
    "past_commitments": [
      { "call_id": "call_2026_01_25_d4e5f6", "commitment": "pay by month end", "fulfilled": false },
      { "call_id": "call_2026_01_10_j1k2l3", "commitment": "pay next week", "fulfilled": true }
    ],
    "fulfillment_rate": 0.33,
    "broken_promises_count": 2
  },

  "risk_assessment": {
    "risk_level": "HIGH",
    "explanation": "Customer has delayed EMI payments in 3 recent calls. Salary delay is a recurring reason. Commitment fulfillment rate is 33%. Current promise has medium conditionality.",
    "confidence": 0.85,
    "regulatory_flags": []
  },

  "history_used": {
    "timeline_calls_retrieved": 2,
    "semantic_matches_retrieved": 2,
    "obligations_retrieved": 3
  }
}
```

---

# 7. API Endpoints

| Method | Path                  | Description                       |
| ------ | --------------------- | --------------------------------- |
| POST   | `/api/v1/process-call`| Main pipeline — ingest + analyze  |
| GET    | `/api/v1/loan/{loan_id}/history` | Get call history for a loan |
| GET    | `/api/v1/call/{call_id}` | Get single call details        |
| GET    | `/health`             | Health check                      |

---

# 8. Environment Variables

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_service_role_key

# OpenAI
OPENAI_API_KEY=sk-xxx

# App Config
TIMELINE_RETRIEVAL_LIMIT=5
SEMANTIC_RETRIEVAL_LIMIT=3
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
```

---

# 9. Build Order (Implementation Sequence)

This is the order in which to build and test:

| Phase | Task                                  | Files                          |
| ----- | ------------------------------------- | ------------------------------ |
| 1     | Project setup + dependencies          | `requirements.txt`, `.env`     |
| 2     | Pydantic schemas (input/output)       | `app/models/schemas.py`        |
| 3     | Supabase client + SQL init            | `app/db/`, `sql/init.sql`      |
| 4     | Ingestion service (store metadata)    | `app/services/ingestion.py`    |
| 5     | Embedding service (generate + store)  | `app/services/embedding.py`    |
| 6     | Retrieval service (SQL + vector)      | `app/services/retrieval.py`    |
| 7     | Context builder                       | `app/services/context_builder.py` |
| 8     | LLM reasoning                        | `app/services/reasoning.py`    |
| 9     | Updater service                       | `app/services/updater.py`      |
| 10    | API routes (wire everything)          | `app/api/routes.py`, `main.py` |
| 11    | Testing + debugging                   | Manual / Postman / curl        |
| 12    | Optional: Backboard AI integration    | —                              |

---

# 10. Error Handling Strategy

| Error Type            | Action                                    |
| --------------------- | ----------------------------------------- |
| Invalid input payload | Return 422 with validation errors         |
| Supabase insert fails | Return 500, log error                     |
| Embedding API fails   | Retry once, then return 500               |
| No history found      | Proceed with current-call-only reasoning  |
| LLM fails             | Retry once, then return fallback risk     |
| Vector search fails   | Fall back to SQL-only retrieval           |

---

# 11. Testing Checklist

- [ ] POST valid payload → 200 with risk assessment
- [ ] POST invalid payload → 422 validation error
- [ ] First call for a loan (no history) → reasoning works
- [ ] Multiple calls for same loan → history retrieved correctly
- [ ] Semantic search returns relevant matches
- [ ] Risk level is one of HIGH / MEDIUM / LOW
- [ ] Explanation references actual history
- [ ] Confidence is between 0.0 and 1.0
- [ ] `calls` table updated with `final_risk`
- [ ] `call_embeddings` table has correct vectors

---

# End of Execution Plan
