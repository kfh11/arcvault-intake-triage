# ArcVault Intake Triage Pipeline

AI-powered intake classification and routing pipeline for ArcVault, built with **n8n** and **OpenAI**.

Accepts unstructured customer messages via webhook, classifies them using GPT-4o-mini with Structured Outputs, enriches with entity extraction, routes to the correct team queue, and flags ambiguous or high-impact cases for human escalation.

## Project Structure

```
├── workflow/
│   └── arcvault-intake-triage.json  # n8n workflow (primary deliverable)
├── pipeline/                        # Python pipeline (development & validation)
│   ├── config.py                    # Model, thresholds, queue map
│   ├── schema.py                    # Pydantic models (mirrors OpenAI JSON Schema)
│   ├── prompts.py                   # System prompt (single source of truth)
│   ├── classifier.py                # OpenAI Structured Output call
│   ├── router.py                    # Category → queue mapping
│   ├── escalation.py                # Rule-based overrides + confidence validation
│   └── pipeline.py                  # Orchestrator
├── run_pipeline.py                  # CLI: process all inputs → write output
├── data/
│   ├── sample_inputs.json           # 5 test inputs
│   └── classification_results.json  # Generated output (deliverable)
├── scripts/
│   └── test_webhook.sh              # curl commands to test live webhook
├── docs/
│   ├── architecture-writeup.md      # System design document
│   └── prompt-documentation.md      # Prompt rationale
├── docker-compose.yml               # n8n self-hosted setup
├── requirements.txt                 # Python dependencies
└── .env                             # OPENAI_API_KEY (not committed)
```

---

## Primary Deliverable: n8n Workflow

The n8n workflow is the production-ready artifact. It implements the full triage pipeline as a 15-node hybrid workflow combining Code nodes (for OpenAI API calls and business logic) with visual IF/Switch/Set nodes (for transparent routing).

### Setup

```bash
docker compose up -d
```

Open `http://localhost:5678` and complete the one-time setup:

1. **Create owner account** at `http://localhost:5678`
2. **Import workflow:** Workflows → Import from File → select `workflow/arcvault-intake-triage.json`
3. **Activate** the workflow (toggle in the top-right corner)

The workflow uses `$env.OPENAI_API_KEY` directly from the Docker environment (set in `.env`), so no n8n credential setup is needed.

### Test the Webhook

```bash
chmod +x scripts/test_webhook.sh
./scripts/test_webhook.sh
```

Or send a single request:

```bash
curl -X POST http://localhost:5678/webhook/arcvault-triage \
  -H 'Content-Type: application/json' \
  -d '{"source": "Email", "message": "I keep getting a 403 error when logging in."}'
```

### Workflow Architecture

```
Webhook → Normalize Input (Set) → Classify (Code/OpenAI) → Route & Escalate (Code)
  → IF escalation_needed?
    ├─ TRUE  → Set: Escalation Queue ──────────────────┐
    └─ FALSE → Switch: destination_queue                │
                 ├─ Engineering      → Set: Engineering  │
                 ├─ Product          → Set: Product      ├→ Output Log → Respond
                 ├─ Billing          → Set: Billing      │
                 ├─ IT/Security      → Set: IT/Security  │
                 ├─ Engineering-Urgent → Set: Eng-Urgent │
                 └─ Fallback         → Set: Fallback ───┘
```

---

## Supporting Deliverable: Python Pipeline

The Python pipeline mirrors the n8n workflow logic exactly. It serves as:
- A **development tool** for iterating on prompts and schemas without restarting n8n
- A **validation tool** to verify classification results independently
- The generator for `data/classification_results.json`

### Run

```bash
pip install -r requirements.txt
python run_pipeline.py
```

Output: `data/classification_results.json` (5 classified records).

---

## Key Design Decisions

- **Single API call:** Classification + enrichment + summarization in one Structured Output call. Reduces latency, cost, and failure points.
- **Signal-before-confidence schema ordering:** Four boolean signal fields (single_category_match, alternative_category, user_expresses_uncertainty, explicit_identifiers_present) are generated *before* the confidence score. The model's own factual observations constrain the confidence range, producing genuinely varied scores (0.68–0.92 across the 5 test inputs).
- **Two-layer escalation:** The LLM flags content-level concerns; deterministic code rules override for business-critical thresholds (confidence < 0.70, billing > $500, outage keywords). Three distinct escalation triggers fire across the 5 test inputs.
- **Code-side confidence validation:** `validate_and_adjust_confidence()` clamps any LLM-generated confidence outside its allowed range based on signal patterns — a safety net ensuring the prompt constraints are enforced.
- **Hybrid n8n architecture:** Code nodes for complex logic (API calls, escalation rules), visual IF/Switch/Set nodes for transparent routing.

## Model Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | gpt-4o-mini | $0.15/$0.60 per M tokens, sufficient for classification |
| Temperature | 0 | Deterministic output |
| Seed | 42 | Reproducibility hint (best-effort per OpenAI docs) |
| Output format | Structured Outputs, `strict: true` | 100% schema compliance guaranteed |

## Deliverables Checklist

- [x] n8n workflow (`workflow/arcvault-intake-triage.json`) — 15-node hybrid architecture
- [x] Structured output file (`data/classification_results.json`) — 5 classified records, 3/5 escalated
- [x] Prompt documentation (`docs/prompt-documentation.md`)
- [x] Architecture write-up (`docs/architecture-writeup.md`)
- [x] Screen recording demo (shared separately)
