from .config import CATEGORY_TO_QUEUE
from .schema import IntakeClassification


def route(classification: IntakeClassification) -> str:
    """Map classification category to destination queue. Pure function, no side effects."""
    return CATEGORY_TO_QUEUE.get(classification.category.value, "Escalation")
