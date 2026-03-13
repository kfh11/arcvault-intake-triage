# Prompt Documentation: ArcVault Intake Triage

## System Prompt

The full prompt is maintained in `pipeline/prompts.py` (single source of truth for both the Python pipeline and the n8n workflow). Below is a summary of each section:

**Categories:** Five mutually exclusive categories (Bug Report, Feature Request, Billing Issue, Technical Question, Incident/Outage), each with description and keyword indicators.

**Priority rules:** Three tiers (High, Medium, Low) based on business impact — outages and security concerns are always High.

**Classification signals:** Four boolean fields the model must fill in BEFORE scoring confidence. These are factual observations about the message text, not judgments:
- `single_category_match` — does the message map to exactly one category?
- `alternative_category` — if not, which is the strongest alternative?
- `user_expresses_uncertainty` — does the sender hedge or express doubt?
- `explicit_identifiers_present` — does the message contain error codes, invoice numbers, URLs, dollar amounts?

**Confidence scoring:** Range constraints tied to signal patterns. The model cannot assign 0.95 if it already wrote `single_category_match: false`. Four ranges enforce this: 0.50–0.75 (ambiguous + alternative), 0.60–0.82 (ambiguous or uncertain), 0.90–0.97 (clear + identifiers), 0.82–0.92 (clear, no identifiers).

**Escalation rules (LLM layer):** Four content-based rules: (1) explicit multi-user disruption keywords, (2) billing discrepancy > $500, (3) security concerns, (4) conflicting signals for 2+ categories.

**Entity extraction:** Structured extraction of account IDs, invoice numbers, error codes, URLs, and other identifiers into typed arrays.

**Three few-shot examples:** Spanning clear-cut (Bug Report, single=true, identifiers=true), ambiguous (Bug Report with alternative=Technical Question, uncertain=true), and informational (Technical Question, single=true, identifiers=false). Few-shot examples deliberately omit confidence scores. Including them caused the model to anchor to example values (0.95, 0.58, 0.86) rather than computing from signal-to-range constraints. The examples demonstrate correct signal observation; the range rules produce the confidence.

## Design Decisions

### Signal-before-confidence schema ordering

The field order in the JSON Schema is the core design insight. Structured Outputs generates fields top-to-bottom. The schema enforces this generation order:

1. **Phase 1 — Reasoning:** The model articulates its analysis.
2. **Phase 2 — Signal booleans:** The model makes factual observations about ambiguity (`single_category_match`, `alternative_category`, `user_expresses_uncertainty`, `explicit_identifiers_present`).
3. **Phase 3 — Confidence:** The model scores confidence, now constrained by the signals it already committed to.
4. **Phase 4 — Classification:** The model assigns category, priority, and enrichment fields.

When the model picks a category first and then scores confidence (as in earlier iterations), it defends its choice — confidence is always high. By forcing signal observation *before* confidence generation, the model's own factual observations constrain the number. Once it writes `single_category_match: false`, it cannot coherently write `confidence: 0.95`.

### Why signal booleans, not a free-form confidence score

Every previous approach to LLM-generated confidence failed:

1. **Few-shot examples with scores:** Model anchored to example values, copying 0.96 or 0.68 regardless of input.
2. **No examples:** Model defaulted to 0.95 for everything.
3. **Signal-based rules in prose:** No measurable effect on output scores.
4. **`competing_categories` list → code-computed confidence:** gpt-4o-mini returned empty arrays at temperature 0 — it's too decisive to report alternatives when asked directly.

The signal-boolean approach works because:
- **Boolean questions have objectively correct answers.** "Does the message contain an error code?" is a factual yes/no — the model answers these accurately at temperature 0.
- **Range constraints prevent uniform scores.** If `single_category_match` is false, the prompt says confidence must be 0.50–0.75, and code-side validation enforces it.
- **The model isn't introspecting.** It's not being asked "how sure are you?" (which it can't answer). It's being asked "did the user express uncertainty?" (which it can answer). Consistency with its own observations produces calibrated confidence as a side effect.

### Code-side confidence validation

Even with prompt constraints, the model could occasionally produce a confidence score outside the allowed range. The `validate_and_adjust_confidence()` function clamps the score to the correct range based on the signal pattern. This is a safety net — the prompt constrains the model, but code enforces it. The output includes a `confidence_clamped` flag for auditability.

### Chain-of-thought via the `reasoning` field

The `reasoning` field is the first field in the schema. The model must articulate its reasoning before producing any other fields. Research on structured chain-of-thought shows accuracy improvements when the model explains its logic before committing to a label.

**Tradeoff:** Adds ~100-200 tokens per response. The accuracy improvement justifies this for a triage pipeline where misrouting has real business cost.

### Enum constraints on categorical fields

All categorical fields (`category`, `priority`, `urgency_signal`, `alternative_category`) use JSON Schema `enum` arrays. With `strict: true`, the model literally cannot produce a value outside the defined set.

### `urgency_signal` vs `priority`

`priority` is the actionable routing field (Low/Medium/High) used by escalation logic and queue assignment; `urgency_signal` is a finer-grained content-level assessment (Low/Moderate/High/Critical) preserved for downstream analytics and SLA engines that may need a four-tier scale.

### Single API call (not multi-step)

Classification, signal observation, confidence scoring, enrichment, entity extraction, and summarization happen in a single API call. Structured Outputs guarantees all fields are populated.

**Tradeoff:** The prompt is longer (~800 tokens). At gpt-4o-mini's rate, this adds ~$0.00012 per request — negligible.

### Deterministic confidence at temperature 0

Input #2 (bulk export feature request) consistently returns 0.90 confidence across runs. At temperature 0 with deterministic decoding, this is expected — the model converges on a single value. The value falls within the valid range (0.82–0.92) and the signal pattern is correct (single_category_match=true, no identifiers, no uncertainty). The round number is a known tendency of LLMs when generating floats. In production, this could be addressed by using logprobs-based confidence (see Phase 2 in architecture write-up) which produces truly continuous distributions.

### What I would change with more time

1. **Logprobs-based confidence.** The optimal approach uses OpenAI's `logprobs` API parameter. By constraining the model to output a single category token and reading the token-level log probabilities, we get the model's actual probability distribution over categories — e.g., 0.88 for "Bug Report" and 0.09 for "Technical Question." This eliminates all prompting artifacts. The reason this is a Phase 2 optimization is that logprobs do not work cleanly with structured output mode (multi-token JSON generation buries per-field probabilities). The workaround is a two-call pattern: first call for category + logprobs, second call for full enrichment. This doubles latency and cost.

2. **Tune range boundaries from production data.** The current ranges (0.50–0.75, 0.60–0.82, 0.82–0.92, 0.90–0.97) are designed to produce reasonable escalation rates. With production traffic, I'd analyze the distribution of signal patterns and adjust boundaries to hit a target escalation rate (e.g., 10-15%).

3. **Expand the category taxonomy.** Five categories cover the assessment requirements, but a production system would need subcategories (e.g., Bug Report → UI Bug, API Bug, Data Bug) for more precise routing.
