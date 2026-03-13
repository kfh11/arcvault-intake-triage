from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    BUG_REPORT = "Bug Report"
    FEATURE_REQUEST = "Feature Request"
    BILLING_ISSUE = "Billing Issue"
    TECHNICAL_QUESTION = "Technical Question"
    INCIDENT_OUTAGE = "Incident/Outage"


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class UrgencySignal(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"


class Identifiers(BaseModel):
    account_ids: list[str] = Field(default_factory=list)
    invoice_numbers: list[str] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class IntakeClassification(BaseModel):
    """Schema for the OpenAI Structured Output response.

    Field order is critical — the model generates top-to-bottom:
    Phase 1: reasoning (think before deciding)
    Phase 2: signal booleans (observe ambiguity before scoring)
    Phase 3: confidence (constrained by signals above)
    Phase 4: classification + enrichment (informed by everything above)
    """

    # Phase 1: Reasoning
    reasoning: str = Field(
        description="Step-by-step reasoning: what is the customer asking? "
        "Which category fits best? Is there ambiguity? What priority and why?"
    )

    # Phase 2: Signal observation
    single_category_match: bool = Field(
        description="True only if the message maps to exactly one category "
        "with zero signals pointing elsewhere."
    )
    alternative_category: Optional[Category] = None
    user_expresses_uncertainty: bool = Field(
        description="True if the sender uses hedging language like "
        "'I\\'m not sure', 'not sure if', 'is there a way to'."
    )
    explicit_identifiers_present: bool = Field(
        description="True if the message contains error codes, invoice numbers, "
        "account IDs, URLs, or dollar amounts."
    )

    # Phase 3: Confidence
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score constrained by the signal fields above.",
    )

    # Phase 4: Classification + enrichment
    category: Category
    priority: Priority
    core_issue: str = Field(description="One-sentence summary of the core issue")
    identifiers: Identifiers
    urgency_signal: UrgencySignal
    suggested_routing: str = Field(
        description="Suggested destination queue based on category"
    )
    escalation_needed: bool
    escalation_reason: Optional[str] = None
    summary: str = Field(
        description="2-3 sentence summary for the receiving team"
    )


class TriageResult(BaseModel):
    """Final output after classification + routing + escalation overrides."""

    source: str
    raw_message: str
    reasoning: str
    single_category_match: bool
    alternative_category: Optional[str] = None
    user_expresses_uncertainty: bool
    explicit_identifiers_present: bool
    confidence: float
    confidence_clamped: bool = False
    category: str
    priority: str
    core_issue: str
    identifiers: Identifiers
    urgency_signal: str
    destination_queue: str
    escalation_needed: bool
    escalation_reason: Optional[str] = None
    human_review_flag: bool
    summary: str
