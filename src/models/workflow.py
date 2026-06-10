from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from src.models.analysis import ParallelAnalysisResponse
from src.models.audit import AuditReport, DecisionRecord
from src.models.case import CaseIntake, StrictModel
from src.models.decision import DecisionOutcome
from src.models.enforcement import EnforcementResult


class WorkflowStatus(StrEnum):
    SUBMITTED = "submitted"
    ANALYZING = "analyzing"
    ENFORCING = "enforcing"
    AUDITING = "auditing"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class WorkflowStage(StrEnum):
    INTAKE = "intake"
    ANALYSIS = "analysis"
    ENFORCEMENT = "enforcement"
    AUDIT = "audit"
    APPROVAL = "approval"
    COMPLETE = "complete"


class ApprovalAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    OVERRIDE = "override"


class HumanDecision(StrictModel):
    action: ApprovalAction
    reviewer: str = Field(min_length=2, max_length=100)
    rationale: str = Field(min_length=10, max_length=1500)
    override_outcome: DecisionOutcome | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_override(self) -> "HumanDecision":
        if self.action == ApprovalAction.OVERRIDE and self.override_outcome is None:
            raise ValueError("override action requires override_outcome")
        if self.action != ApprovalAction.OVERRIDE and self.override_outcome is not None:
            raise ValueError("override_outcome is only valid for override action")
        return self


class WorkflowRun(StrictModel):
    run_id: str = Field(pattern=r"^RUN-[A-F0-9]{16}$")
    idempotency_key: str = Field(min_length=3, max_length=120)
    case: CaseIntake
    status: WorkflowStatus
    current_stage: WorkflowStage
    top_k: int = Field(default=8, ge=1, le=25)
    version: int = Field(default=1, ge=1)
    attempt_count: int = Field(default=0, ge=0)
    analysis: ParallelAnalysisResponse | None = None
    enforcement: EnforcementResult | None = None
    audit: AuditReport | None = None
    record: DecisionRecord | None = None
    human_decision: HumanDecision | None = None
    final_outcome: DecisionOutcome | None = None
    error: str | None = None
    retryable: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowEvent(StrictModel):
    event_id: int = Field(ge=1)
    run_id: str = Field(pattern=r"^RUN-[A-F0-9]{16}$")
    sequence: int = Field(ge=1)
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    stage: WorkflowStage
    payload: dict[str, object]
    previous_hash: str = Field(pattern=r"^(?:[a-f0-9]{64})?$")
    event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime


class StartWorkflowRequest(StrictModel):
    case: CaseIntake
    idempotency_key: str | None = Field(default=None, min_length=3, max_length=120)
    top_k: int = Field(default=8, ge=1, le=25)


class ApprovalRequest(StrictModel):
    action: ApprovalAction
    reviewer: str = Field(min_length=2, max_length=100)
    rationale: str = Field(min_length=10, max_length=1500)
    override_outcome: DecisionOutcome | None = None

    @model_validator(mode="after")
    def validate_override(self) -> "ApprovalRequest":
        if self.action == ApprovalAction.OVERRIDE and self.override_outcome is None:
            raise ValueError("override action requires override_outcome")
        if self.action != ApprovalAction.OVERRIDE and self.override_outcome is not None:
            raise ValueError("override_outcome is only valid for override action")
        return self
