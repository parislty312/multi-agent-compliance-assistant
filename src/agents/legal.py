"""Evidence-bound legal issue spotting for AI launch reviews."""

from src.agents.common import (
    citation_from_match,
    evidence_by_category,
    validate_finding_citations,
)
from src.models import (
    AgeGroup,
    AgentAnalysis,
    AgentFinding,
    CaseIntake,
    DataCategory,
    EvidenceResponse,
    FindingCategory,
    FindingSeverity,
)


class LegalAgent:
    """Identifies legal-review issues without claiming to provide legal advice."""

    def analyze(self, case: CaseIntake, evidence: EvidenceResponse) -> AgentAnalysis:
        required = self._required_categories(case)
        matches = evidence_by_category(evidence, required)
        findings: list[AgentFinding] = []
        abstained: list[FindingCategory] = []

        for index, category in enumerate(sorted(required, key=lambda item: item.value), 1):
            match = matches.get(category)
            if match is None:
                abstained.append(category)
                continue
            severity = self._severity(case, category)
            findings.append(
                AgentFinding(
                    finding_id=f"FND-{index:03d}",
                    agent="legal",
                    category=category,
                    severity=severity,
                    statement=self._statement(case, category),
                    rationale=(
                        f"The case facts trigger {category.value.replace('_', ' ')} review, "
                        f"and retrieved section {match.chunk.section_id} describes the "
                        "applicable synthetic policy requirement."
                    ),
                    citations=[citation_from_match(match)],
                    confidence=min(0.98, 0.65 + match.score / 100),
                    requires_human_review=severity
                    in {FindingSeverity.HIGH, FindingSeverity.CRITICAL},
                )
            )

        validate_finding_citations(findings, evidence)
        open_questions = list(case.open_questions)
        if abstained:
            open_questions.append(
                "No retrieved evidence supported: "
                + ", ".join(category.value for category in abstained)
            )
        if any(
            finding.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
            for finding in findings
        ):
            open_questions.append(
                "An authorized legal reviewer must confirm jurisdiction-specific obligations."
            )

        return AgentAnalysis(
            agent="legal",
            case_id=case.case_id,
            summary=(
                f"Legal issue spotting produced {len(findings)} evidence-backed findings "
                f"and abstained on {len(abstained)} categories."
            ),
            findings=findings,
            open_questions=list(dict.fromkeys(open_questions)),
            abstained_categories=abstained,
            evidence_index_version=evidence.index_version,
        )

    @staticmethod
    def _required_categories(case: CaseIntake) -> set[FindingCategory]:
        categories = {FindingCategory.PRIVACY, FindingCategory.TRANSPARENCY}
        if any(
            age in {AgeGroup.UNDER_13, AgeGroup.TEEN_13_TO_17, AgeGroup.ALL_AGES}
            for age in case.affected_age_groups
        ):
            categories.add(FindingCategory.CHILD_SAFETY)
        if case.automated_decision:
            categories.add(FindingCategory.HIGH_IMPACT_DECISION)
        if (
            case.feature_type.value
            in {"chatbot", "content_generation", "content_moderation"}
            or DataCategory.HEALTH in case.data_categories
        ):
            categories.add(FindingCategory.CONTENT_SAFETY)
        return categories

    @staticmethod
    def _severity(case: CaseIntake, category: FindingCategory) -> FindingSeverity:
        if (
            category == FindingCategory.CHILD_SAFETY
            and AgeGroup.UNDER_13 in case.affected_age_groups
            and not case.human_oversight.enabled
        ):
            return FindingSeverity.CRITICAL
        if (
            category == FindingCategory.HIGH_IMPACT_DECISION
            or DataCategory.BIOMETRIC in case.data_categories
        ):
            return FindingSeverity.HIGH
        if (
            not case.user_notice_present
            or not case.safety_evaluation_complete
            or DataCategory.MINOR_DATA in case.data_categories
        ):
            return FindingSeverity.MEDIUM
        return FindingSeverity.LOW

    @staticmethod
    def _statement(case: CaseIntake, category: FindingCategory) -> str:
        statements = {
            FindingCategory.PRIVACY: (
                f"{case.title} processes data that requires documented purpose, retention, "
                "access, and deletion controls."
            ),
            FindingCategory.CHILD_SAFETY: (
                f"{case.title} affects minors and requires age-appropriate safeguards."
            ),
            FindingCategory.HIGH_IMPACT_DECISION: (
                f"{case.title} influences a consequential decision in "
                f"{case.decision_domain or 'an unspecified domain'}."
            ),
            FindingCategory.CONTENT_SAFETY: (
                f"{case.title} generates or mediates content and requires misuse safeguards."
            ),
            FindingCategory.TRANSPARENCY: (
                f"{case.title} requires clear AI notice, explanation, or user recourse."
            ),
            FindingCategory.GOVERNANCE: (
                f"{case.title} requires documented governance and launch accountability."
            ),
        }
        return statements[category]
