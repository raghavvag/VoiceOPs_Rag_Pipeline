# Integration Guide

Two services integrate with the RAG Pipeline:

1. **NLP Service** → sends call analysis data → `POST /api/v1/analyze-call`
2. **Frontend Chatbot** → sends user questions → `POST /api/v1/chat`

---

## 1. NLP Service Integration

The NLP service processes raw call audio and sends structured risk signals to the RAG pipeline for grounding against the knowledge base.

### Endpoint

```
POST http://<RAG_HOST>:8000/api/v1/analyze-call
Content-Type: application/json
```

### Expected Input from NLP Service

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
    "audio_trust_flags": ["low_call_stability", "unnatural_speech_pattern"],
    "behavioral_flags": ["conditional_commitment", "evasive_responses", "statement_contradiction"]
  },
  "risk_assessment": {
    "risk_score": 78,
    "fraud_likelihood": "high",
    "confidence": 0.81
  },
  "summary_for_rag": "Customer made a conditional repayment promise, showed stress, and contradicted earlier statements, which aligns with known high-risk call patterns."
}
```

### Field Reference

| Field | Type | Required | Allowed Values |
|---|---|---|---|
| `call_context.call_language` | string | YES | any language string |
| `call_context.call_quality.noise_level` | string | YES | `low`, `medium`, `high` |
| `call_context.call_quality.call_stability` | string | YES | `low`, `medium`, `high` |
| `call_context.call_quality.speech_naturalness` | string | YES | `natural`, `suspicious` |
| `speaker_analysis.customer_only_analysis` | bool | YES | `true`, `false` |
| `speaker_analysis.agent_influence_detected` | bool | YES | `true`, `false` |
| `nlp_insights.intent.label` | string | YES | e.g. `repayment_promise`, `dispute`, `inquiry` |
| `nlp_insights.intent.confidence` | float | YES | 0.0 – 1.0 |
| `nlp_insights.intent.conditionality` | string | YES | `low`, `medium`, `high` |
| `nlp_insights.sentiment.label` | string | YES | e.g. `cooperative`, `stressed`, `angry`, `neutral` |
| `nlp_insights.sentiment.confidence` | float | YES | 0.0 – 1.0 |
| `nlp_insights.obligation_strength` | string | YES | `strong`, `moderate`, `weak` |
| `nlp_insights.entities.payment_commitment` | string | NO | e.g. `tomorrow`, `next_week`, `null` |
| `nlp_insights.entities.amount_mentioned` | float | NO | e.g. `5000`, `null` |
| `nlp_insights.contradictions_detected` | bool | YES | `true`, `false` |
| `risk_signals.audio_trust_flags` | string[] | YES | e.g. `["low_call_stability", "unnatural_speech_pattern"]` |
| `risk_signals.behavioral_flags` | string[] | YES | e.g. `["conditional_commitment", "evasive_responses"]` |
| `risk_assessment.risk_score` | int | YES | 0 – 100 |
| `risk_assessment.fraud_likelihood` | string | YES | `low`, `medium`, `high` |
| `risk_assessment.confidence` | float | YES | 0.0 – 1.0 |
| `summary_for_rag` | string | YES | Min 10 chars. Human-readable summary of the call. |

### Response from RAG (200 OK)

```json
{
  "call_id": "call_2026_02_09_a1b2c3",
  "call_timestamp": "2026-02-09T12:00:00+00:00",
  "input_risk_assessment": {
    "risk_score": 78,
    "fraud_likelihood": "high",
    "confidence": 0.81
  },
  "rag_output": {
    "grounded_assessment": "high_risk",
    "explanation": "The call signals match the 'Conditional Promise with Contradiction' fraud pattern (fp_001). The customer's conditional repayment promise with high conditionality, combined with stressed sentiment and detected contradictions, strongly aligns with known high-risk indicators.",
    "recommended_action": "escalate_to_compliance",
    "confidence": 0.88,
    "regulatory_flags": ["RBI verbal commitment recording required"],
    "matched_patterns": ["Conditional Promise with Contradiction", "Evasive Response Pattern"]
  }
}
```

### Response Fields

| Field | Type | Values |
|---|---|---|
| `call_id` | string | Auto-generated, format `call_YYYY_MM_DD_hexhex` |
| `call_timestamp` | ISO 8601 | UTC timestamp |
| `rag_output.grounded_assessment` | string | `high_risk`, `medium_risk`, `low_risk` |
| `rag_output.recommended_action` | string | `auto_clear`, `flag_for_review`, `manual_review`, `escalate_to_compliance` |
| `rag_output.confidence` | float | 0.0 – 1.0 |
| `rag_output.regulatory_flags` | string[] | Compliance concerns (empty if none) |
| `rag_output.matched_patterns` | string[] | Knowledge base patterns that matched |

### Error Responses

| Status | When |
|---|---|
| 422 | Invalid or missing fields in payload |
| 500 | Embedding, LLM, or DB failure |
| 503 | Knowledge base not seeded yet |

---

## 2. Frontend Chatbot Integration

The frontend sends user questions and receives grounded answers from the knowledge base and past call history.

### Endpoint

```
POST http://<RAG_HOST>:8000/api/v1/chat
Content-Type: application/json
```

### Basic Request (Minimal)

```json
{
  "question": "What are the indicators of conditional promise fraud?"
}
```

### Full Request (All Options)

```json
{
  "question": "Which fraud patterns involve contradictions?",
  "conversation_history": [
    {
      "role": "user",
      "content": "What are the main fraud patterns?"
    },
    {
      "role": "assistant",
      "content": "The knowledge base contains six fraud patterns including conditional promises, emotional manipulation, and evasive responses."
    }
  ],
  "filters": {
    "search_knowledge": true,
    "search_calls": true,
    "categories": ["fraud_pattern", "compliance", "risk_heuristic"],
    "knowledge_limit": 5,
    "calls_limit": 3
  }
}
```

### Field Reference

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `question` | string | YES | — | Min 5 chars. The user's question. |
| `conversation_history` | array | NO | `[]` | Previous messages for multi-turn context. |
| `conversation_history[].role` | string | YES (if history sent) | — | `user` or `assistant` |
| `conversation_history[].content` | string | YES (if history sent) | — | Message text |
| `filters.search_knowledge` | bool | NO | `true` | Search knowledge base (fraud patterns, compliance, heuristics) |
| `filters.search_calls` | bool | NO | `false` | Search past call analyses via vector similarity |
| `filters.categories` | string[] | NO | all three | `fraud_pattern`, `compliance`, `risk_heuristic` |
| `filters.knowledge_limit` | int | NO | `5` | Max knowledge docs to retrieve (1–10) |
| `filters.calls_limit` | int | NO | `3` | Max past calls to retrieve (1–10) |

### Response (200 OK)

```json
{
  "answer": "The 'Conditional Promise with Contradiction' pattern (fp_001) is triggered when a customer makes a payment promise with high conditionality and then contradicts prior statements. Historical data shows 73% of such calls result in non-payment.",
  "sources": [
    {
      "type": "knowledge",
      "doc_id": "fp_001",
      "category": "fraud_pattern",
      "title": "Conditional Promise with Contradiction",
      "similarity": 0.92
    },
    {
      "type": "call",
      "doc_id": "call_2026_02_09_d5de2d",
      "category": "call_analysis",
      "title": "Risk=15 | low",
      "similarity": 0.57
    }
  ],
  "metadata": {
    "knowledge_docs_searched": 5,
    "calls_searched": 1,
    "model": "gpt-4o-mini",
    "tokens_used": 942
  }
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `answer` | string | Grounded answer citing specific documents |
| `sources` | array | Documents used to generate the answer |
| `sources[].type` | string | `knowledge` (from knowledge base) or `call` (from past calls) |
| `sources[].doc_id` | string | Document or call ID |
| `sources[].category` | string | `fraud_pattern`, `compliance`, `risk_heuristic`, or `call_analysis` |
| `sources[].similarity` | float | Cosine similarity score (0–1, higher = more relevant) |
| `metadata.knowledge_docs_searched` | int | Number of knowledge docs retrieved |
| `metadata.calls_searched` | int | Number of past calls retrieved |
| `metadata.model` | string | LLM model used |
| `metadata.tokens_used` | int | Total tokens consumed |

### Frontend Implementation Notes

1. **Store conversation history client-side** — send it with each request for multi-turn
2. **Cap history at 10 messages** — the server truncates beyond that
3. **`search_calls` is OFF by default** — enable it only when user asks about past calls
4. **Sources are clickable** — use `doc_id` to link to knowledge doc or `call_id` to open call detail via `GET /api/v1/call/{call_id}`
5. **Similarity scores** — display as relevance percentage (e.g. `0.92` → `92% match`)

### Error Responses

| Status | When |
|---|---|
| 422 | Question too short (<5 chars) or invalid filters |
| 503 | Knowledge base not seeded |

---

## Other Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health check → `{"status": "ok"}` |
| `POST` | `/api/v1/knowledge/seed` | Seed knowledge base (run once) |
| `GET` | `/api/v1/knowledge/status` | Check knowledge doc count |
| `GET` | `/api/v1/call/{call_id}` | Fetch a specific call record |
