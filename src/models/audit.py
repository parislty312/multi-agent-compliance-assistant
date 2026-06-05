from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from src.models.case import CaseIntake, StrictModel
from src.models.decision import FindingCategory, FindingSeverity
from src.models.enforcement import LaunchReviewResponse


class AuditVerdict(StrEnum):
    PASS = "pass"
    REVIEW_REQUIRED = "review_required"
    FAIL = "fail"


class AuditCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class AuditCheck(StrictModel):
    check_id: str = Field(pattern=r"^AUD-CHECK-\d{3}$")
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    title: str = Field(min_length=5, max_length=150)
    status: AuditCheckStatus
    severity: FindingSeverity
    details: str = Field(min_length=10, max_length=1500)
    related_ids: list[str] = Field(default_factory=list)


class AuditReport(StrictModel):
    case_id: str = Field(pattern=r"^CASE-\d{3}$")
    verdict: AuditVerdict
    summary: str = Field(min_length=10, max_length=1000)
    checks: list[AuditCheck] = Field(min_length=1)
    unsupported_finding_ids: list[str] = Field(default_factory=list)
    missing_categories: list[FindingCategory] = Field(default_factory=list)
    requires_human_review: bool
    audited_ruleset_version: str = Field(min_length=1)
    audited_evidence_index_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_verdict(self) -> "AuditReport":
        failed = [check for check in self.checks if check.status == AuditCheckStatus.FAIL]
        if self.verdict == AuditVerdict.PASS and failed:
            raise ValueError("pass verdict cannot contain failed checks")
        if self.verdict == AuditVerdict.FAIL and not failed:
            raise ValueError("fail verdict requires at least one failed check")
        return self


class DecisionRecord(StrictModel):
    record_id: str = Field(pattern=r"^REC-[A-F0-9]{16}$")
    case_id: str = Field(pattern=r"^CASE-\d{3}$")
    case: CaseIntake
    review: LaunchReviewResponse
    audit: AuditReport
    hash_algorithm: str = Field(default="sha256", pattern=r"^sha256$")
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditRequest(StrictModel):
    case: CaseIntake
    review: LaunchReviewResponse | None = None
    top_k: int = Field(default=8, ge=1, le=25)


class AuditedLaunchReview(StrictModel):
    review: LaunchReviewResponse
    audit: AuditReport
    record: DecisionRecord

