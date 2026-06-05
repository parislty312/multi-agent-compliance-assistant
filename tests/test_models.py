from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models import (
    AuditResult,
    ComplianceDecision,
    DecisionOutcome,
    FindingSeverity,
)


def decision_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision_id": "DEC-001",
        "case_id": "CASE-001",
        "outcome": DecisionOutcome.ALLOW,
        "risk_level": FindingSeverity.LOW,
        "summary": "The feature may launch with the safeguards described in the case.",
        "findings": [],
        "required_controls": [],
        "open_questions": [],
        "human_approval_required": False,
        "audit": AuditResult(
            passed=True,
            reviewed_finding_ids=[],
            unsupported_finding_ids=[],
            missing_categories=[],
            notes=[],
        ),
        "policy_version": "synthetic-policy-v0.1",
        "created_at": datetime.now(UTC),
    }
    payload.update(overrides)
    return payload


def test_conditional_allow_requires_control() -> None:
    with pytest.raises(ValidationError, match="requires at least one control"):
        ComplianceDecision.model_validate(
            decision_payload(outcome=DecisionOutcome.CONDITIONAL_ALLOW)
        )


def test_escalation_requires_human_approval() -> None:
    with pytest.raises(ValidationError, match="requires human approval"):
        ComplianceDecision.model_validate(decision_payload(outcome=DecisionOutcome.ESCALATE))


def test_deny_requires_high_or_critical_risk() -> None:
    with pytest.raises(ValidationError, match="requires high or critical risk"):
        ComplianceDecision.model_validate(decision_payload(outcome=DecisionOutcome.DENY))

