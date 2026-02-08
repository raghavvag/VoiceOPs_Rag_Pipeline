# Financial Audio Intelligence — Execution Plan (v2)

## Document Purpose

This is the **implementation blueprint** for the RAG service.
Architecture was pivoted from customer-centric memory to **call-centric risk grounding**.

Refer to `Rules.md` for project context and design principles.

---

# 1. Architecture Summary

**Old approach:** Track customer history → predict repayment risk over time.
**New approach:** Treat each call as an independent risk event → ground signals against known patterns.

RAG is a **legal + fraud-aware reasoning assistant**, not a database.

### What RAG Does

1. Grounds risk signals against known fraud/compliance patterns
2. Converts NLP signals into explainable, auditor-friendly narratives
3. Validates (never overrides) the risk assessment from NLP
4. Recommends policy-aware actions
5. Ensures regulatory-safe language

### What RAG Does NOT Do

- Extract intent
- Detect sentiment
- Compute risk scores
- Detect contradictions
- Analyze raw transcript
- Remember customers
- Make final business decisions

---

# 2. Tech Stack

| Layer              | Technology                          |
| ------------------ | ----------------------------------- |
| Language           | Python 3.13.5                       |
| Framework          | FastAPI                             |
| Database           | Supabase (PostgreSQL + pgvector)    |
| Embedding Model    | OpenAI `text-embedding-3-small`     |
| LLM Reasoning      | OpenAI `gpt-4o` / `gpt-4o-mini`   |
| Vector Search      | pgvector (cosine similarity)        |
| Environment        | `.env` with `dotenv`                |

---

# 3. Folder Structure

```
VoiceOPs_Rag_Pipeline/
│
├── Rules.md
├── EXECUTION_PLAN.md
├── .env
├── .gitignore
├── requirements.txt
├── main.py                         # FastAPI entry point
│
├── app/
│   ├── __init__.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # API endpoints
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py              # Pydantic models (input/output)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion.py            # Step 1-2: validate + store call
│   │   ├── embedding.py            # Step 3: embed summary_for_rag
│   │   ├── retrieval.py            # Step 4: retrieve knowledge chunks
│   │   ├── context_builder.py      # Step 5: build grounding context
│   │   ├── reasoning.py            # Step 6: LLM grounded reasoning
│   │   └── updater.py              # Step 7: store RAG output
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── supabase_client.py      # Supabase connection
│   │   └── queries.py              # SQL + vector queries
│   │
│   └── utils/
│       ├── __init__.py
│       ├── id_generator.py         # Auto-generate call_id
│       └── helpers.py              # Shared utilities
│
├── knowledge/
│   ├── fraud_patterns.json         # Curated fraud pattern documents
│   ├── compliance_rules.json       # Regulatory guidance documents
│   └── risk_heuristics.json        # Risk heuristic documents
│
└── sql/
    └── init.sql                    # Table creation scripts
```

---

# 4. Input Contract (NLP Service → RAG Service)

```json
{
  "call_context": {
    "call_language": "hinglish",
    "call_quality": {
      "noise_level": "medium",
      "call_stability": "low",
      "speech_naturalness": "suspicious"
    }
  },

  "speaker_analysis": {
    "customer_only_analysis": true,
    "agent_influence_detected": false
  },

  "nlp_insights": {
    "intent": {
      "label": "repayment_promise",
      "confidence": 0.6,
      "conditionality": "high"
    },
    "sentiment": {
      "label": "stressed",
      "confidence": 0.82
    },
    "obligation_strength": "weak",
    "entities": {
      "payment_commitment": "next_week",
      "amount_mentioned": null
    },
    "contradictions_detected": true
  },

  "risk_signals": {
    "audio_trust_flags": [
      "low_call_stability",
      "unnatural_speech_pattern"
    ],
    "behavioral_flags": [
      "conditional_commitment",
      "evasive_responses",
      "statement_contradiction"
    ]
  },

  "risk_assessment": {
    "risk_score": 78,
    "fraud_likelihood": "high",
    "confidence": 0.81
  },

  "summary_for_rag": "Customer made a conditional repayment promise, showed stress, and contradicted earlier statements, which aligns with known high-risk call patterns."
}
```

### Key Design Decisions on Input

| Field                | Source         | Notes                                                     |
| -------------------- | -------------- | --------------------------------------------------------- |
| `call_id`            | Auto-generated | RAG service generates: `call_{date}_{short_uuid}`         |
| `call_timestamp`     | Auto-generated | Server UTC time at ingestion                              |
| `call_context`       | NLP service    | Language + audio quality metadata                         |
| `speaker_analysis`   | NLP service    | Who was analyzed, agent influence flag                     |
| `nlp_insights`       | NLP service    | Intent, sentiment, entities — RAG does NOT recompute      |
| `risk_signals`       | NLP service    | Audio + behavioral flags — RAG grounds these              |
| `risk_assessment`    | NLP service    | Score + fraud likelihood — RAG validates, never overrides  |
| `summary_for_rag`    | NLP service    | Embedded for knowledge retrieval — the RAG query text      |

---

# 5. Output Contract

```json
{
  "call_id": "call_2026_02_09_a1b2c3",
  "call_timestamp": "2026-02-09T14:30:00Z",

  "input_risk_assessment": {
    "risk_score": 78,
    "fraud_likelihood": "high",
    "confidence": 0.81
  },

  "rag_output": {
    "grounded_assessment": "high_risk",
    "explanation": "The call exhibits multiple high-risk indicators. The customer made a conditional repayment promise with high conditionality and weak obligation strength, which matches documented patterns of unreliable commitments. Statement contradictions were detected, a behavioral flag commonly associated with evasive debtors. Audio analysis flagged unnatural speech patterns and low call stability, which may indicate call manipulation. These signals collectively align with known fraud-adjacent call patterns.",
    "recommended_action": "manual_review",
    "confidence": 0.85,
    "regulatory_flags": [],
    "matched_patterns": [
      "conditional_commitment_with_contradiction",
      "weak_obligation_with_evasion",
      "audio_quality_anomaly"
    ]
  }
}
```

---

# 6. Database Schema

## Table: `call_analyses`

Stores each call as an independent risk event with RAG output.

```sql
CREATE TABLE call_analyses (
    call_id             TEXT PRIMARY KEY,
    call_timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    call_context        JSONB,
    speaker_analysis    JSONB,
    nlp_insights        JSONB,
    risk_signals        JSONB,
    risk_assessment     JSONB,
    summary_for_rag     TEXT,
    rag_output          JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_call_analyses_timestamp ON call_analyses (call_timestamp DESC);
```

## Table: `knowledge_embeddings`

Curated knowledge base for fraud patterns, compliance rules, and risk heuristics.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_embeddings (
    doc_id          TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_knowledge_category ON knowledge_embeddings (category);
```

### Knowledge Categories

| Category        | Purpose                                          | Example                                              |
| --------------- | ------------------------------------------------ | ---------------------------------------------------- |
| `fraud_pattern` | Known fraud call behaviors and red flags          | "Conditional promises followed by contradictions..."  |
| `compliance`    | Regulatory rules and required phrasing            | "RBI guidelines on verbal commitment recording..."    |
| `risk_heuristic`| Risk scoring logic and interpretation guidance    | "Risk score above 70 with weak obligation = HIGH..."  |

---

# 7. Execution Flow (Step-by-Step)

---

## Step 1 — Receive & Validate

**File:** `app/api/routes.py` → `app/models/schemas.py`

- FastAPI POST endpoint receives the JSON payload from NLP service
- Pydantic validates against `CallRiskInput` schema
- If validation fails → return 422

**Auto-generated fields:**
- `call_id` = `call_{date}_{short_uuid}`
- `call_timestamp` = current UTC time

**Expected Input:**
```json
{
  "call_context": { "call_language": "hinglish", "call_quality": { "noise_level": "medium", "call_stability": "low", "speech_naturalness": "suspicious" } },
  "speaker_analysis": { "customer_only_analysis": true, "agent_influence_detected": false },
  "nlp_insights": {
    "intent": { "label": "repayment_promise", "confidence": 0.6, "conditionality": "high" },
    "sentiment": { "label": "stressed", "confidence": 0.82 },
    "obligation_strength": "weak",
    "entities": { "payment_commitment": "next_week", "amount_mentioned": null },
    "contradictions_detected": true
  },
  "risk_signals": {
    "audio_trust_flags": ["low_call_stability", "unnatural_speech_pattern"],
    "behavioral_flags": ["conditional_commitment", "evasive_responses", "statement_contradiction"]
  },
  "risk_assessment": { "risk_score": 78, "fraud_likelihood": "high", "confidence": 0.81 },
  "summary_for_rag": "Customer made a conditional repayment promise, showed stress, and contradicted earlier statements."
}
```

**Expected Output (internal, passed to Step 2):**
```json
{
  "call_id": "call_2026_02_09_a1b2c3",
  "call_timestamp": "2026-02-09T14:30:00Z",
  "validated_payload": { "...full input..." },
  "status": "validated"
}
```

---

## Step 2 — Store Call Record

**File:** `app/services/ingestion.py`

- Insert the full call data into `call_analyses` table
- `rag_output` = NULL (populated after Step 7)

**Expected Input:**
```json
{
  "call_id": "call_2026_02_09_a1b2c3",
  "call_timestamp": "2026-02-09T14:30:00Z",
  "call_context": { "..." },
  "speaker_analysis": { "..." },
  "nlp_insights": { "..." },
  "risk_signals": { "..." },
  "risk_assessment": { "..." },
  "summary_for_rag": "Customer made a conditional repayment promise..."
}
```

**Expected Output:**
```json
{
  "inserted": true,
  "call_id": "call_2026_02_09_a1b2c3",
  "table": "call_analyses"
}
```

---

## Step 3 — Embed Summary for Knowledge Retrieval

**File:** `app/services/embedding.py`

- Take `summary_for_rag` text
- Call OpenAI embedding API (`text-embedding-3-small`)
- This embedding is used to QUERY the knowledge base (not stored permanently)

**Expected Input:**
```json
{
  "text": "Customer made a conditional repayment promise, showed stress, and contradicted earlier statements."
}
```

**Expected Output:**
```json
{
  "query_embedding": [0.0123, -0.0456, 0.0789, "...1536 floats..."]
}
```

---

## Step 4 — Retrieve Knowledge Chunks

**File:** `app/services/retrieval.py`

Semantic search against the curated knowledge base.

### 4A — Fraud Pattern Retrieval

```sql
SELECT doc_id, title, content, 1 - (embedding <=> :query_embedding) AS similarity
FROM knowledge_embeddings
WHERE category = 'fraud_pattern'
ORDER BY embedding <=> :query_embedding
LIMIT 3;
```

### 4B — Compliance Guidance Retrieval

```sql
SELECT doc_id, title, content, 1 - (embedding <=> :query_embedding) AS similarity
FROM knowledge_embeddings
WHERE category = 'compliance'
ORDER BY embedding <=> :query_embedding
LIMIT 2;
```

### 4C — Risk Heuristic Retrieval

```sql
SELECT doc_id, title, content, 1 - (embedding <=> :query_embedding) AS similarity
FROM knowledge_embeddings
WHERE category = 'risk_heuristic'
ORDER BY embedding <=> :query_embedding
LIMIT 2;
```

**Expected Input:**
```json
{
  "query_embedding": [0.0123, -0.0456, "...1536 floats..."]
}
```

**Expected Output:**
```json
{
  "fraud_patterns": [
    {
      "doc_id": "fp_001",
      "title": "Conditional Promise with Contradiction",
      "content": "When a customer makes a payment promise with high conditionality and contradicts prior statements, this is a strong indicator of unreliable commitment. Historical data shows 73% of such calls result in non-payment.",
      "similarity": 0.92
    },
    {
      "doc_id": "fp_004",
      "title": "Evasive Response Pattern",
      "content": "Customers who give evasive responses while under stress and avoid direct answers about payment timelines exhibit a documented fraud-adjacent behavior pattern.",
      "similarity": 0.87
    }
  ],
  "compliance_docs": [
    {
      "doc_id": "comp_012",
      "title": "Verbal Commitment Assessment Guidelines",
      "content": "Verbal commitments with high conditionality should not be treated as binding agreements. Assessors must note conditionality level and recommend verification.",
      "similarity": 0.85
    }
  ],
  "risk_heuristics": [
    {
      "doc_id": "rh_003",
      "title": "High Risk Score Interpretation",
      "content": "Risk scores above 70 combined with weak obligation strength and behavioral flags indicate high risk. Recommended action: manual review with compliance escalation if fraud likelihood exceeds 0.7.",
      "similarity": 0.89
    }
  ]
}
```

---

## Step 5 — Build Grounding Context

**File:** `app/services/context_builder.py`

Construct a structured prompt from:

1. **Call signals** — risk flags, NLP insights, risk score
2. **Retrieved knowledge** — fraud patterns, compliance rules, heuristics

**Expected Input:**
```json
{
  "call_signals": {
    "nlp_insights": { "...from input..." },
    "risk_signals": { "...from input..." },
    "risk_assessment": { "...from input..." },
    "call_context": { "...from input..." },
    "summary": "..."
  },
  "knowledge_chunks": {
    "fraud_patterns": [ "...from Step 4A..." ],
    "compliance_docs": [ "...from Step 4B..." ],
    "risk_heuristics": [ "...from Step 4C..." ]
  }
}
```

**Expected Output (formatted context string):**

```
=== CALL SIGNALS ===
Summary: Customer made a conditional repayment promise, showed stress, and contradicted earlier statements.
Intent: repayment_promise (confidence: 0.60, conditionality: high)
Sentiment: stressed (confidence: 0.82)
Obligation Strength: weak
Contradictions Detected: YES
Audio Flags: low_call_stability, unnatural_speech_pattern
Behavioral Flags: conditional_commitment, evasive_responses, statement_contradiction
Risk Score: 78 | Fraud Likelihood: high | Confidence: 0.81

=== MATCHED FRAUD PATTERNS ===
[1] (0.92) Conditional Promise with Contradiction
    When a customer makes a payment promise with high conditionality and contradicts prior statements, this is a strong indicator of unreliable commitment.

[2] (0.87) Evasive Response Pattern
    Customers who give evasive responses while under stress and avoid direct answers about payment timelines exhibit a documented fraud-adjacent behavior pattern.

=== COMPLIANCE GUIDANCE ===
[1] (0.85) Verbal Commitment Assessment Guidelines
    Verbal commitments with high conditionality should not be treated as binding agreements.

=== RISK HEURISTICS ===
[1] (0.89) High Risk Score Interpretation
    Risk scores above 70 combined with weak obligation strength and behavioral flags indicate high risk. Recommended action: manual review.
```

---

## Step 6 — LLM Grounded Reasoning

**File:** `app/services/reasoning.py`

- Send context to OpenAI GPT-4o
- LLM grounds signals against retrieved knowledge
- LLM does NOT override risk score — it explains and validates

**Expected Input:**
```json
{
  "system_prompt": "You are a financial risk grounding assistant...",
  "context": "=== CALL SIGNALS ===\n...full context from Step 5..."
}
```

**Expected Output:**
```json
{
  "grounded_assessment": "high_risk",
  "explanation": "The call exhibits multiple high-risk indicators. The customer made a conditional repayment promise with high conditionality and weak obligation strength, which matches documented patterns of unreliable commitments. Statement contradictions were detected, a behavioral flag commonly associated with evasive debtors. Audio analysis flagged unnatural speech patterns and low call stability, which may indicate call manipulation. These signals collectively align with known fraud-adjacent call patterns.",
  "recommended_action": "manual_review",
  "confidence": 0.85,
  "regulatory_flags": [],
  "matched_patterns": [
    "conditional_commitment_with_contradiction",
    "weak_obligation_with_evasion",
    "audio_quality_anomaly"
  ]
}
```

**System Prompt:**

```
You are a financial risk grounding assistant. Your role is to interpret
call-level risk signals by grounding them against known fraud patterns,
compliance rules, and risk heuristics.

You MUST return a JSON object with:
- grounded_assessment: one of "high_risk", "medium_risk", "low_risk"
- explanation: human-readable, auditor-friendly narrative explaining WHY
  the signals match or don't match known patterns. Cite specific patterns.
- recommended_action: one of "auto_clear", "flag_for_review", "manual_review",
  "escalate_to_compliance"
- confidence: float 0.0–1.0 representing grounding confidence
- regulatory_flags: array of regulatory concerns (empty if none)
- matched_patterns: array of pattern names that matched

RULES:
- You MUST NOT override the risk score from the NLP service
- You MUST NOT extract new intent, sentiment, or entities
- You MUST NOT use accusatory language ("fraudster", "liar", "criminal")
- You MUST use terms like: "high-risk indicators", "unreliable commitment",
  "requires verification", "fraud-adjacent pattern"
- If signals are ambiguous, say so and recommend manual review
- If no patterns match, state that clearly and lower confidence
- Base your reasoning ONLY on the provided signals and retrieved knowledge
```

---

## Step 7 — Store RAG Output

**File:** `app/services/updater.py`

```sql
UPDATE call_analyses
SET rag_output = :rag_output_json
WHERE call_id = :call_id;
```

**Expected Input:**
```json
{
  "call_id": "call_2026_02_09_a1b2c3",
  "rag_output": {
    "grounded_assessment": "high_risk",
    "explanation": "...",
    "recommended_action": "manual_review",
    "confidence": 0.85,
    "regulatory_flags": [],
    "matched_patterns": ["conditional_commitment_with_contradiction"]
  }
}
```

**Expected Output:**
```json
{
  "updated": true,
  "call_id": "call_2026_02_09_a1b2c3",
  "table": "call_analyses",
  "field": "rag_output"
}
```

---

## Step 8 — Return Response

**File:** `app/api/routes.py`

Assemble and return the final response.

**Expected Output (final API response):**
```json
{
  "call_id": "call_2026_02_09_a1b2c3",
  "call_timestamp": "2026-02-09T14:30:00Z",

  "input_risk_assessment": {
    "risk_score": 78,
    "fraud_likelihood": "high",
    "confidence": 0.81
  },

  "rag_output": {
    "grounded_assessment": "high_risk",
    "explanation": "The call exhibits multiple high-risk indicators...",
    "recommended_action": "manual_review",
    "confidence": 0.85,
    "regulatory_flags": [],
    "matched_patterns": [
      "conditional_commitment_with_contradiction",
      "weak_obligation_with_evasion",
      "audio_quality_anomaly"
    ]
  }
}
```

---

# 8. API Endpoints

| Method | Path                          | Description                              |
| ------ | ----------------------------- | ---------------------------------------- |
| POST   | `/api/v1/analyze-call`        | Main pipeline — ground + assess          |
| GET    | `/api/v1/call/{call_id}`      | Get single call analysis                 |
| POST   | `/api/v1/knowledge/seed`      | Seed knowledge base (one-time setup)     |
| GET    | `/health`                     | Health check                             |

---

# 9. Environment Variables

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_service_role_key

# OpenAI
OPENAI_API_KEY=sk-xxx

# App Config
FRAUD_PATTERN_RETRIEVAL_LIMIT=3
COMPLIANCE_RETRIEVAL_LIMIT=2
RISK_HEURISTIC_RETRIEVAL_LIMIT=2
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
```

---

# 10. Knowledge Base Seeding

The knowledge base must be populated ONCE before the pipeline works.

### Seeding Process

1. Read JSON files from `knowledge/` directory
2. Embed each document using OpenAI
3. Insert into `knowledge_embeddings` table

### Document Format (in JSON files)

```json
[
  {
    "doc_id": "fp_001",
    "category": "fraud_pattern",
    "title": "Conditional Promise with Contradiction",
    "content": "When a customer makes a payment promise with high conditionality and contradicts prior statements, this is a strong indicator of unreliable commitment. Historical data shows 73% of such calls result in non-payment.",
    "metadata": { "severity": "high", "source": "internal_audit_2025" }
  }
]
```

---

# 11. Build Order (Implementation Sequence)

| Phase | Task                                      | Files                              |
| ----- | ----------------------------------------- | ---------------------------------- |
| 1     | Project setup + dependencies              | `requirements.txt`, `.env` ✅ DONE  |
| 2     | Pydantic schemas (input/output)           | `app/models/schemas.py`            |
| 3     | Supabase client + SQL init                | `app/db/`, `sql/init.sql`          |
| 4     | Knowledge base JSON + seeding service     | `knowledge/`, seeding endpoint     |
| 5     | Ingestion service (store call)            | `app/services/ingestion.py`        |
| 6     | Embedding service (embed summary)         | `app/services/embedding.py`        |
| 7     | Retrieval service (knowledge search)      | `app/services/retrieval.py`        |
| 8     | Context builder                           | `app/services/context_builder.py`  |
| 9     | LLM reasoning                            | `app/services/reasoning.py`        |
| 10    | Updater service                           | `app/services/updater.py`          |
| 11    | API routes (wire everything)              | `app/api/routes.py`, `main.py`     |
| 12    | Testing + debugging                       | Manual / Postman / curl            |

---

# 12. Error Handling Strategy

| Error Type                | Action                                        |
| ------------------------- | --------------------------------------------- |
| Invalid input payload     | Return 422 with validation errors             |
| Supabase insert fails     | Return 500, log error                         |
| Embedding API fails       | Retry once, then return 500                   |
| No knowledge matches      | Proceed with signals-only reasoning           |
| LLM fails                 | Retry once, then return fallback assessment    |
| Knowledge base empty      | Return 503 (service not ready)                |

---

# 13. Testing Checklist

- [ ] POST valid payload → 200 with grounded assessment
- [ ] POST invalid payload → 422 validation error
- [ ] Knowledge base seeded with fraud patterns
- [ ] Semantic search returns relevant knowledge chunks
- [ ] Grounded assessment is one of high_risk / medium_risk / low_risk
- [ ] Explanation cites specific matched patterns
- [ ] recommended_action is policy-appropriate
- [ ] Confidence is between 0.0 and 1.0
- [ ] No accusatory language in explanation
- [ ] `call_analyses` table updated with `rag_output`

---

# 14. One-Line Explanation

> "RAG grounds call-level risk signals against known fraud patterns and regulatory guidance, turning raw model outputs into explainable and defensible assessments."

---

# End of Execution Plan
