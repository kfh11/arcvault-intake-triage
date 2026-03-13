from .classifier import classify
from .escalation import check_escalation, validate_and_adjust_confidence
from .router import route
from .schema import TriageResult


def process(source: str, message: str) -> TriageResult:
    """Run the full triage pipeline: classify -> validate -> route -> escalate."""
    classification = classify(source, message)

    confidence, clamped, original = validate_and_adjust_confidence(classification)

    priority = classification.priority.value
    if classification.category.value == "Incident/Outage":
        priority = "High"

    destination_queue = route(classification)

    escalation_needed, escalation_reason = check_escalation(
        classification, message, confidence
    )

    if escalation_needed:
        destination_queue = "Escalation"

    return TriageResult(
        source=source,
        raw_message=message,
        reasoning=classification.reasoning,
        single_category_match=classification.single_category_match,
        alternative_category=(
            classification.alternative_category.value
            if classification.alternative_category
            else None
        ),
        user_expresses_uncertainty=classification.user_expresses_uncertainty,
        explicit_identifiers_present=classification.explicit_identifiers_present,
        confidence=confidence,
        confidence_clamped=clamped,
        category=classification.category.value,
        priority=priority,
        core_issue=classification.core_issue,
        identifiers=classification.identifiers,
        urgency_signal=classification.urgency_signal.value,
        destination_queue=destination_queue,
        escalation_needed=escalation_needed,
        escalation_reason=escalation_reason,
        human_review_flag=escalation_needed,
        summary=classification.summary,
    )
