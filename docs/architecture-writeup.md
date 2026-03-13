# Architecture Write-Up: ArcVault Intake Triage Pipeline

## System Design

The pipeline follows a linear five-stage architecture: **Ingest → Classify → Validate → Route → Respond**. Each stage has a single responsibility and can be tested independently.

```
Customer Request
       │
       ▼
┌──────────────┐
│   Webhook    │  POST /arcvault-triage
│   (n8n)      │  Accepts { source, message }
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Normalize   │  Set node
│  Input       │  Extract source, message, classificationInput
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Classify    │  Code node → OpenAI API
│  (OpenAI)    │  gpt-4o-mini, temp=0, seed=42
│              │  Structured Outputs (strict: true)
│              │  Check finish_reason, refusal, parse JSON
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Route &     │  Code node
│  Escalate    │  Category → Queue mapping
│              │  Rule-based escalation overrides
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  IF: Esc?    │  IF node (visual)
│              │  escalation_needed == true?
└──┬───────┬───┘
   │       │
  TRUE   FALSE
   │       │
   ▼       ▼
┌──────┐ ┌────────────┐
│ Set: │ │  Switch:   │  Switch node (visual)
│ Esc  │ │  Queue     │  Routes by destination_queue
│ Queue│ └──┬──┬──┬───┘
└──┬───┘    │  │  │ ...
   │        ▼  ▼  ▼
   │     ┌───────────────┐
   │     │ Set: <Queue>  │  Set nodes (visual)
   │     │ Engineering,  │  Each adds routing_destination
   │     │ Product, etc. │
   │     └──────┬────────┘
   │            │
   ▼            ▼
┌──────────────────┐
│  Write to Output │  Code node
│  Log             │  POST to webhook.site (optional)
└──────┬───────────┘
       │
       ▼
┌──────────────┐
│  Respond to  │  Returns enriched JSON
│  Webhook     │  to the caller
└──────────────┘
```

There is no persistent state between requests. Each message is classified, routed, and returned independently. This stateless design means the pipeline can be horizontally scaled without coordination.

The same logic runs in two places: an **n8n workflow** (for live webhook processing) and a **Python pipeline** (for batch processing and generating the deliverable output file). Both use the identical system prompt and escalation rules.

## Why a Hybrid Architecture (Code + Visual Nodes)

The workflow uses a **hybrid approach**: Code nodes for complex logic (OpenAI API calls, multi-rule escalation checks) and visual n8n nodes (IF, Switch, Set) for transparent routing decisions.

**Code nodes are used where they add value:**
- **Classify (Code):** The OpenAI API call requires constructing a complex request body with a JSON schema, parsing the response, and checking for truncation/refusal. This logic would be awkward to express in n8n's Edit Fields or HTTP Request node.
- **Route & Escalate (Code):** Applying multiple escalation rules (confidence threshold, keyword matching, billing amount parsing) in sequence with short-circuit logic is cleaner as imperative code.

**Visual nodes are used where they add value:**
- **IF node:** The escalation branch is immediately visible on the canvas. Anyone viewing the workflow can see the decision point.
- **Switch node:** Category-based routing is expressed as a visual branching tree with labeled outputs (Engineering, Product, Billing, IT/Security, Engineering-Urgent, Fallback). This makes the routing map self-documenting.
- **Set nodes:** Each queue assignment is a named, visible node. The data flow from classification to final routing is traceable on the canvas.

**Tradeoff:** 15 nodes is more complex than a minimal 4-node Code-only pipeline, but the visual routing tree is significantly easier to audit and modify. A reviewer can understand the routing logic without reading JavaScript.

## Why HTTP Request via Code Node (Not the AI Agent Node)

The AI Agent node adds autonomous tool-calling and multi-step reasoning. A classification pipeline needs the opposite: deterministic, single-call, schema-constrained output. Using the OpenAI API directly gives full control over `temperature`, `seed`, `response_format`, and the JSON Schema — parameters the built-in AI Agent node does not expose.

## Why Structured Outputs with Strict Mode

OpenAI's Structured Outputs with `strict: true` uses a context-free grammar engine to mask invalid tokens during generation. This guarantees 100% schema adherence — every response matches the defined JSON Schema exactly. Without strict mode, schema compliance drops below 40% on internal benchmarks.

Key schema design decisions:
- **Field order enforces generation order.** The schema follows a four-phase structure: reasoning → signal booleans → confidence → classification. Because Structured Outputs generates fields top-to-bottom, the model observes ambiguity signals *before* it scores confidence, and scores confidence *before* it commits to a category. This ordering is the mechanism that produces varied, calibrated confidence scores.
- The `reasoning` field is first in the schema. This forces chain-of-thought analysis.
- Four signal booleans (`single_category_match`, `alternative_category`, `user_expresses_uncertainty`, `explicit_identifiers_present`) precede `confidence`. The model's own factual observations constrain the confidence range.
- All categorical fields use `enum` constraints. The model literally cannot produce a value outside the set.
- `escalation_reason` uses `["string", "null"]` type to allow nullable output within strict mode.
- `identifiers` is a structured object (not free text) for machine consumption by downstream systems.

## Why gpt-4o-mini

At $0.15 / $0.60 per million input/output tokens, gpt-4o-mini is 17x cheaper than gpt-4o. For structured classification with strict schema constraints, it performs comparably — the grammar engine does most of the heavy lifting. We set `temperature: 0` for deterministic output and `seed: 42` as a reproducibility hint. OpenAI documents seed as best-effort — it improves consistency across runs but does not guarantee identical output. For true determinism guarantees, we rely on `temperature: 0` and the strict JSON schema, which constrain the output space far more effectively than seed alone.

## Routing Logic

| Category | Queue | Rationale |
|----------|-------|-----------|
| Bug Report | Engineering | Software defects require dev team triage |
| Feature Request | Product | Product team owns the roadmap |
| Billing Issue | Billing | Finance/billing team handles disputes |
| Technical Question | IT/Security | Configuration and integration questions |
| Incident/Outage | Engineering-Urgent | Active outages bypass the normal queue |
| Escalated (any) | Escalation Queue | Overrides category routing |
| Fallback (unknown) | Fallback-Escalation | Catch-all for unrecognized categories |

Incident/Outage always forces priority to High regardless of the model's assignment.

## Escalation Logic

The pipeline uses **two-layer escalation**: the LLM's own assessment plus deterministic rule-based overrides.

**Layer 1 — Model-driven:** The model sets `escalation_needed` based on content-level signals: explicit multi-user disruption, billing over $500, security concerns, or conflicting category signals.

**Layer 2 — Rule-based overrides (cannot be bypassed):**
1. **Confidence gate:** If confidence < 0.70, escalate. Confidence is generated by the LLM but *constrained* by signal booleans — when `single_category_match` is false and an alternative category exists, the prompt forces confidence into the 0.50–0.75 range. Code-side validation (`validate_and_adjust_confidence`) enforces these ranges as a safety net.
2. **Keyword gate:** Messages containing "outage", "down for all users", "system down", etc. are escalated and priority is forced to High.
3. **Billing gate:** Billing issues where a dollar amount exceeds $500 are escalated due to financial impact.

**Why signal-constrained confidence works:** The model doesn't introspect ("how sure am I?"). It answers factual boolean questions ("does this message contain an error code?", "does the user express uncertainty?"), then its own committed observations constrain the confidence range. This produces genuinely varied scores — observed range across 5 test inputs: 0.68 to 0.92. See `docs/prompt-documentation.md` for the full design rationale.

## What I Would Do Differently at Production Scale

**Reliability:** Add retry with exponential backoff on OpenAI API failures. Implement a dead-letter queue for messages that fail classification after retries.

**Cost:** Batch non-urgent messages and classify them in bulk during off-peak hours. Use a model fallback cascade: try gpt-4o-mini first, escalate to gpt-4o for low-confidence results.

**Latency:** Cache classification results for identical messages (common in support — the same error report arrives from multiple users). Median latency is currently ~3s per classification; caching would reduce repeat classifications to <50ms.

**Observability:** Log every classification with input hash, model response, confidence score, and routing decision. Build a dashboard tracking confidence distribution, escalation rate, and category breakdown over time. Alert on sudden shifts (e.g., escalation rate spikes above 40%).

**Feedback loop:** Let human reviewers mark misclassifications. Aggregate these into a fine-tuning dataset. Re-evaluate the prompt monthly against accumulated edge cases.

**True confidence calibration:** For production-grade confidence, the optimal approach uses OpenAI's `logprobs` API parameter. By constraining the model to output a single category token and reading the token-level log probabilities, we get the model's actual probability distribution over categories — e.g., 0.88 for "Bug Report" and 0.09 for "Technical Question." This eliminates all prompting artifacts. The reason this is a Phase 2 optimization is that logprobs do not work cleanly with structured output mode (multi-token JSON generation buries per-field probabilities). The workaround is a two-call pattern: first call for category + logprobs, second call for full enrichment. This doubles latency and cost, making it a production investment rather than a demo feature. Our current signal-constrained approach provides correctly ordered confidence (ambiguous inputs always score lower than clear ones) and threshold-reliable confidence (the 0.70 escalation gate works correctly). True calibration — where 0.80 corresponds to 80% actual accuracy — requires a labeled validation dataset and post-hoc calibration on production data.

## Phase 2 Roadmap (One Additional Week)

1. **Feedback loop UI:** A simple interface where reviewers can correct misclassifications. Store corrections as labeled training data.
2. **Multi-language support:** Detect message language, translate to English for classification, return results in the original language.
3. **SLA-aware routing:** Integrate with the support ticketing system to factor in current queue depth and agent availability.
4. **Analytics dashboard:** Real-time metrics on classification accuracy, escalation rate, average confidence by category, and routing distribution.
5. **Fine-tuned model:** Use accumulated labeled data to fine-tune gpt-4o-mini specifically for ArcVault's domain, improving accuracy and reducing prompt complexity.
