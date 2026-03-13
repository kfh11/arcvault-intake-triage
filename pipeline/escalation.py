import re

from .config import CONFIDENCE_THRESHOLD, ESCALATION_KEYWORDS
from .schema import IntakeClassification


def validate_and_adjust_confidence(
    classification: IntakeClassification,
) -> tuple[float, bool, float | None]:
    """Enforce confidence range consistency with signal fields.

    The prompt constrains the model to output confidence within a range
    determined by its own signal observations. This function is a safety
    net — if the LLM returns a score outside the allowed range, clamp it.

    Returns (confidence, was_clamped, original_if_clamped).
    """
    single = classification.single_category_match
    alt = classification.alternative_category
    uncertain = classification.user_expresses_uncertainty
    identifiers = classification.explicit_identifiers_present
    conf = classification.confidence

    if not single and alt is not None:
        lo, hi = 0.50, 0.75
    elif not single or uncertain:
        lo, hi = 0.60, 0.82
    elif single and not uncertain and identifiers:
        lo, hi = 0.90, 0.97
    elif single and not uncertain and not identifiers:
        lo, hi = 0.82, 0.92
    else:
        lo, hi = 0.70, 0.90

    if conf < lo or conf > hi:
        clamped = round(max(lo, min(hi, conf)), 2)
        return clamped, True, conf

    return conf, False, None


def check_escalation(
    classification: IntakeClassification,
    raw_message: str,
    confidence: float,
) -> tuple[bool, str | None]:
    """Apply rule-based escalation checks that override the LLM's decision.

    Returns (escalation_needed, reason). These rules supplement — and can
    override — the model's own `escalation_needed` flag, because
    business-critical rules must not rely on model judgment alone.
    """
    if classification.escalation_needed:
        return True, classification.escalation_reason or "Model flagged escalation"

    message_lower = raw_message.lower()

    if confidence < CONFIDENCE_THRESHOLD:
        return True, (
            f"Low confidence ({confidence:.2f}) "
            f"below threshold ({CONFIDENCE_THRESHOLD})"
        )

    for keyword in ESCALATION_KEYWORDS:
        if keyword in message_lower:
            return True, f"Escalation keyword detected: '{keyword}'"

    amount_match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", raw_message)
    if amount_match and classification.category.value == "Billing Issue":
        amount = float(amount_match.group(1).replace(",", ""))
        if amount > 500:
            return True, f"Billing amount ${amount:,.2f} exceeds $500 threshold"

    return False, None
