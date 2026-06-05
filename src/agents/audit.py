"""Independent compliance decision audit agent."""

from src.agents.common import validate_finding_citations
from src.enforcement import EnforcementEngine, load_enforcement_ruleset
from src.models import (
    AuditCheck,
    AuditCheckStatus,
    AuditReport,
    AuditVerdict,
    CaseIntake,
    DecisionOutcome,
    FindingCategory,
    FindingSeverity,
    LaunchReviewResponse,
)


class AuditAgent:
    def __init__(self, engine: EnforcementEngine | None = None) -> None:
        self.engine = engine or EnforcementEngine(load_enforcement_ruleset())

    def audit(
        self,
        case: CaseIntake,
        review: LaunchReviewResponse,
    ) -> AuditReport:
        checks: list[AuditCheck] = []
        unsupported: list[str] = []

        checks.append(self._case_identity_check(case, review))

        citation_check, unsupported = self._citation_check(review)
        checks.append(citation_check)

        checks.append(self._evidence_version_check(review))
        checks.append(self._control_linkage_check(review))

        category_check, missing_categories = self._winning_rule_category_check(
            review
        )
        checks.append(category_check)

        checks.append(self._enforcement_replay_check(case, review))
        checks.append(self._human_boundary_check(review))
        checks.append(self._abstention_check(review))

        failed = [check for check in checks if check.status == AuditCheckStatus.FAIL]
        if any(
            check.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
            for check in failed
        ):
            verdict = AuditVerdict.FAIL
        elif failed:
            verdict = AuditVerdict.REVIEW_REQUIRED
        else:
            verdict = AuditVerdict.PASS

        human_required = (
            verdict != AuditVerdict.PASS
            or review.enforcement.human_approval_required
            or bool(review.analysis.legal.abstained_categories)
            or bool(review.analysis.policy.abstained_categories)
        )
        return AuditReport(
            case_id=case.case_id,
            verdict=verdict,
            summary=(
                f"Audit completed {len(checks)} checks with {len(failed)} failures; "
                f"verdict is {verdict.value}."
            ),
            checks=checks,
            unsupported_finding_ids=unsupported,
            missing_categories=missing_categories,
            requires_human_review=human_required,
            audited_ruleset_version=review.enforcement.ruleset_version,
            audited_evidence_index_version=review.analysis.evidence.index_version,
        )

    @staticmethod
    def _case_identity_check(
        case: CaseIntake,
        review: LaunchReviewResponse,
    ) -> AuditCheck:
        ids = {
            case.case_id,
            review.analysis.case_id,
            review.analysis.legal.case_id,
            review.analysis.policy.case_id,
            review.enforcement.case_id,
        }
        passed = len(ids) == 1
        return AuditAgent._check(
            check_id="AUD-CHECK-001",
            code="CASE_IDENTITY",
            title="Case identity consistency",
            passed=passed,
            severity=FindingSeverity.CRITICAL,
            details=(
                "All case identifiers are consistent."
                if passed
                else f"Mismatched case identifiers were found: {sorted(ids)}."
            ),
            related_ids=sorted(ids),
        )

    @staticmethod
    def _citation_check(
        review: LaunchReviewResponse,
    ) -> tuple[AuditCheck, list[str]]:
        unsupported: list[str] = []
        for analysis in (review.analysis.legal, review.analysis.policy):
            for finding in analysis.findings:
                try:
                    validate_finding_citations(
                        [finding],
                        review.analysis.evidence,
                    )
                except ValueError:
                    unsupported.append(f"{analysis.agent}:{finding.finding_id}")
        passed = not unsupported
        return (
            AuditAgent._check(
                check_id="AUD-CHECK-002",
                code="CITATION_INTEGRITY",
                title="Finding citation integrity",
                passed=passed,
                severity=FindingSeverity.CRITICAL,
                details=(
                    "Every finding cites an exact section from the evidence snapshot."
                    if passed
                    else "Unsupported or altered citations were detected."
                ),
                related_ids=unsupported,
            ),
            unsupported,
        )

    @staticmethod
    def _evidence_version_check(review: LaunchReviewResponse) -> AuditCheck:
        versions = {
            review.analysis.evidence.index_version,
            review.analysis.legal.evidence_index_version,
            review.analysis.policy.evidence_index_version,
        }
        passed = len(versions) == 1
        return AuditAgent._check(
            check_id="AUD-CHECK-003",
            code="EVIDENCE_VERSION",
            title="Evidence snapshot consistency",
            passed=passed,
            severity=FindingSeverity.HIGH,
            details=(
                "Both analysis agents used the same evidence index version."
                if passed
                else "Analysis agents reference different evidence index versions."
            ),
            related_ids=sorted(versions),
        )

    @staticmethod
    def _control_linkage_check(review: LaunchReviewResponse) -> AuditCheck:
        policy_finding_ids = {
            finding.finding_id for finding in review.analysis.policy.findings
        }
        policy_controls = {
            control.control_id: control for control in review.analysis.policy.controls
        }
        invalid_controls: list[str] = []
        for control in review.analysis.policy.controls:
            if not set(control.source_finding_ids) <= policy_finding_ids:
                invalid_controls.append(control.control_id)
        for control in review.enforcement.required_controls:
            source = policy_controls.get(control.control_id)
            if source is None or not source.blocking or source != control:
                invalid_controls.append(control.control_id)
        invalid_controls = sorted(set(invalid_controls))
        passed = not invalid_controls
        return AuditAgent._check(
            check_id="AUD-CHECK-004",
            code="CONTROL_LINKAGE",
            title="Control lineage consistency",
            passed=passed,
            severity=FindingSeverity.HIGH,
            details=(
                "All controls link to policy findings and enforcement controls are "
                "unchanged blocking controls."
                if passed
                else "Invalid, unlinked, or altered controls were detected."
            ),
            related_ids=invalid_controls,
        )

    def _winning_rule_category_check(
        self,
        review: LaunchReviewResponse,
    ) -> tuple[AuditCheck, list[FindingCategory]]:
        rule = next(
            (
                item
                for item in self.engine.ruleset.rules
                if item.rule_id == review.enforcement.winning_rule_id
            ),
            None,
        )
        available = {
            finding.category
            for finding in [
                *review.analysis.legal.findings,
                *review.analysis.policy.findings,
            ]
        }
        missing = (
            sorted(
                set(rule.required_categories) - available,
                key=lambda item: item.value,
            )
            if rule
            else []
        )
        passed = rule is not None and not missing
        return (
            self._check(
                check_id="AUD-CHECK-005",
                code="RISK_COVERAGE",
                title="Winning rule risk coverage",
                passed=passed,
                severity=FindingSeverity.HIGH,
                details=(
                    "The winning rule exists and all required risk categories are covered."
                    if passed
                    else "The winning rule is unknown or required risk categories are missing."
                ),
                related_ids=[category.value for category in missing],
            ),
            missing,
        )

    def _enforcement_replay_check(
        self,
        case: CaseIntake,
        review: LaunchReviewResponse,
    ) -> AuditCheck:
        replayed = self.engine.evaluate(case, review.analysis)
        passed = replayed == review.enforcement
        return self._check(
            check_id="AUD-CHECK-006",
            code="ENFORCEMENT_REPLAY",
            title="Deterministic enforcement replay",
            passed=passed,
            severity=FindingSeverity.CRITICAL,
            details=(
                "Independent replay exactly matches the submitted enforcement result."
                if passed
                else "Independent replay differs from the submitted enforcement result."
            ),
            related_ids=[
                review.enforcement.winning_rule_id,
                replayed.winning_rule_id,
            ],
        )

    @staticmethod
    def _human_boundary_check(review: LaunchReviewResponse) -> AuditCheck:
        outcome = review.enforcement.outcome
        expected = outcome in {DecisionOutcome.ESCALATE, DecisionOutcome.DENY}
        passed = review.enforcement.human_approval_required == expected
        return AuditAgent._check(
            check_id="AUD-CHECK-007",
            code="HUMAN_APPROVAL_BOUNDARY",
            title="Human approval boundary",
            passed=passed,
            severity=FindingSeverity.HIGH,
            details=(
                "Human approval matches the enforcement outcome."
                if passed
                else "Human approval does not match the enforcement outcome."
            ),
            related_ids=[outcome.value],
        )

    @staticmethod
    def _abstention_check(review: LaunchReviewResponse) -> AuditCheck:
        abstentions = sorted(
            {
                *(
                    f"legal:{category.value}"
                    for category in review.analysis.legal.abstained_categories
                ),
                *(
                    f"policy:{category.value}"
                    for category in review.analysis.policy.abstained_categories
                ),
            }
        )
        passed = not abstentions
        return AuditAgent._check(
            check_id="AUD-CHECK-008",
            code="ANALYSIS_ABSTENTION",
            title="Analysis evidence completeness",
            passed=passed,
            severity=FindingSeverity.MEDIUM,
            details=(
                "Neither analysis agent abstained from a required risk category."
                if passed
                else "One or more required categories lacked supporting evidence."
            ),
            related_ids=abstentions,
        )

    @staticmethod
    def _check(
        *,
        check_id: str,
        code: str,
        title: str,
        passed: bool,
        severity: FindingSeverity,
        details: str,
        related_ids: list[str],
    ) -> AuditCheck:
        return AuditCheck(
            check_id=check_id,
            code=code,
            title=title,
            status=(
                AuditCheckStatus.PASS if passed else AuditCheckStatus.FAIL
            ),
            severity=severity,
            details=details,
            related_ids=related_ids,
        )
