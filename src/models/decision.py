from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from src.models.case import StrictModel


class FindingSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(StrEnum):
    PRIVACY = "privacy"
    CHILD_SAFETY = "child_safety"
    HIGH_IMPACT_DECISION = "high_impact_decision"
    CONTENT_SAFETY = "content_safety"
    TRANSPARENCY = "transparency"
    GOVERNANCE = "governance"


class DecisionOutcome(StrEnum):
    ALLOW = "allow"
    CONDITIONAL_ALLOW = "conditional_allow"
    ESCALATE = "escalate"
    DENY = "deny"


class Citation(StrictModel):
    source_id: str = Field(min_length=3)
    section: str = Field(min_length=1)
    excerpt: str = Field(min_length=5, max_length=500)


class AgentFinding(StrictModel):
    finding_id: str = Field(pattern=r"^FND-\d{3}$")
    agent: str = Field(pattern=r"^(legal|policy|enforcement|audit)$")
    category: FindingCategory
    severity: FindingSeverity
    statement: str = Field(min_length=10, max_length=1000)
    rationale: str = Field(min_length=10, max_length=1500)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = False


class ControlRequirement(StrictModel):
    control_id: str = Field(pattern=r"^CTL-\d{3}$")
    title: str = Field(min_length=5, max_length=150)
    description: str = Field(min_length=10, max_length=1000)
    owner: str = Field(min_length=2, max_length=100)
    blocking: bool
    source_finding_ids: list[str] = Field(min_length=1)
    verification_method: str = Field(min_length=10, max_length=500)


class AuditResult(StrictModel):
    passed: bool
    reviewed_finding_ids: list[str]
    unsupported_finding_ids: list[str] = Field(default_factory=list)
    missing_categories: list[FindingCategory] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ComplianceDecision(StrictModel):
    decision_id: str = Field(pattern=r"^DEC-\d{3}$")
    case_id: str = Field(pattern=r"^CASE-\d{3}$")
    outcome: DecisionOutcome
    risk_level: FindingSeverity
    summary: str = Field(min_length=10, max_length=1000)
    findings: list[AgentFinding]
    required_controls: list[ControlRequirement] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    human_approval_required: bool
    audit: AuditResult
    policy_version: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_outcome_contract(self) -> "ComplianceDecision":
        if self.outcome == DecisionOutcome.CONDITIONAL_ALLOW and not self.required_controls:
            raise ValueError("conditional_allow requires at least one control")
        if self.outcome == DecisionOutcome.ESCALATE and not self.human_approval_required:
            raise ValueError("escalate requires human approval")
        if self.outcome == DecisionOutcome.DENY and self.risk_level not in {
            FindingSeverity.HIGH,
            FindingSeverity.CRITICAL,
        }:
            raise ValueError("deny requires high or critical risk")
        return self

