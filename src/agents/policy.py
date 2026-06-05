"""Evidence-bound internal policy mapping agent."""

from src.agents.common import (
    citation_from_match,
    evidence_by_category,
    validate_finding_citations,
)
from src.models import (
    AgentFinding,
    CaseIntake,
    ControlRequirement,
    EvidenceResponse,
    FindingCategory,
    FindingSeverity,
    PolicyAnalysis,
)


class PolicyAgent:
    """Maps case gaps to cited policy requirements and verifiable controls."""

    def analyze(self, case: CaseIntake, evidence: EvidenceResponse) -> PolicyAnalysis:
        categories = self._required_categories(case)
        matches = evidence_by_category(evidence, categories)
        findings: list[AgentFinding] = []
        controls_by_id: dict[str, ControlRequirement] = {}
        abstained: list[FindingCategory] = []

        for index, category in enumerate(sorted(categories, key=lambda item: item.value), 101):
            match = matches.get(category)
            if match is None:
                abstained.append(category)
                continue

            severity = self._severity(case, category)
            finding_id = f"FND-{index:03d}"
            findings.append(
                AgentFinding(
                    finding_id=finding_id,
                    agent="policy",
                    category=category,
                    severity=severity,
                    statement=(
                        f"Policy section {match.chunk.section_id} applies to the "
                        f"{category.value.replace('_', ' ')} aspects of {case.title}."
                    ),
                    rationale=(
                        "The section matched the structured case context and defines "
                        "controls that can be verified before launch."
                    ),
                    citations=[citation_from_match(match)],
                    confidence=min(0.99, 0.7 + match.score / 100),
                    requires_human_review=severity
                    in {FindingSeverity.HIGH, FindingSeverity.CRITICAL},
                )
            )
            for control in self._controls_for_match(
                case=case,
                finding_id=finding_id,
                category=category,
                control_ids=match.chunk.control_ids,
                section_title=match.chunk.section_title,
                blocking=severity
                in {
                    FindingSeverity.MEDIUM,
                    FindingSeverity.HIGH,
                    FindingSeverity.CRITICAL,
                },
            ):
                existing = controls_by_id.get(control.control_id)
                if existing:
                    controls_by_id[control.control_id] = existing.model_copy(
                        update={
                            "blocking": existing.blocking or control.blocking,
                            "source_finding_ids": list(
                                dict.fromkeys(
                                    [
                                        *existing.source_finding_ids,
                                        *control.source_finding_ids,
                                    ]
                                )
                            ),
                        }
                    )
                else:
                    controls_by_id[control.control_id] = control

        validate_finding_citations(findings, evidence)
        controls = list(controls_by_id.values())
        return PolicyAnalysis(
            agent="policy",
            case_id=case.case_id,
            summary=(
                f"Mapped {len(findings)} policy findings into {len(controls)} "
                "verifiable control requirements."
            ),
            findings=findings,
            controls=controls,
            open_questions=list(case.open_questions),
            abstained_categories=abstained,
            evidence_index_version=evidence.index_version,
        )

    @staticmethod
    def _required_categories(case: CaseIntake) -> set[FindingCategory]:
        categories = {
            FindingCategory.GOVERNANCE,
            FindingCategory.PRIVACY,
            FindingCategory.TRANSPARENCY,
        }
        if not case.safety_evaluation_complete or case.feature_type.value in {
            "chatbot",
            "content_generation",
            "content_moderation",
        }:
            categories.add(FindingCategory.CONTENT_SAFETY)
        if case.automated_decision:
            categories.add(FindingCategory.HIGH_IMPACT_DECISION)
        if any(age.value in {"under_13", "teen_13_to_17", "all_ages"} for age in case.affected_age_groups):
            categories.add(FindingCategory.CHILD_SAFETY)
        return categories

    @staticmethod
    def _severity(case: CaseIntake, category: FindingCategory) -> FindingSeverity:
        if category == FindingCategory.HIGH_IMPACT_DECISION:
            return FindingSeverity.HIGH
        if not case.human_oversight.enabled and category in {
            FindingCategory.CHILD_SAFETY,
            FindingCategory.GOVERNANCE,
        }:
            return FindingSeverity.CRITICAL
        if (
            not case.user_notice_present
            or not case.safety_evaluation_complete
            or case.open_questions
        ):
            return FindingSeverity.MEDIUM
        return FindingSeverity.LOW

    @staticmethod
    def _controls_for_match(
        *,
        case: CaseIntake,
        finding_id: str,
        category: FindingCategory,
        control_ids: list[str],
        section_title: str,
        blocking: bool,
    ) -> list[ControlRequirement]:
        ids = control_ids or [f"CTL-{category.value[:4].upper()}-001"]
        controls: list[ControlRequirement] = []
        for control_id in ids:
            controls.append(
                ControlRequirement(
                    control_id=control_id,
                    title=f"Verify {section_title}",
                    description=(
                        f"Implement and document the {section_title.lower()} requirement "
                        f"for {case.case_id} before launch."
                    ),
                    owner=PolicyAgent._owner_for(category),
                    blocking=blocking,
                    source_finding_ids=[finding_id],
                    verification_method=(
                        "Attach configuration, evaluation, notice, or reviewer evidence "
                        "to the case record and obtain owner sign-off."
                    ),
                )
            )
        return controls

    @staticmethod
    def _owner_for(category: FindingCategory) -> str:
        owners = {
            FindingCategory.PRIVACY: "Privacy",
            FindingCategory.CHILD_SAFETY: "Youth Safety",
            FindingCategory.HIGH_IMPACT_DECISION: "Responsible AI",
            FindingCategory.CONTENT_SAFETY: "Trust and Safety",
            FindingCategory.TRANSPARENCY: "Product Compliance",
            FindingCategory.GOVERNANCE: "AI Governance",
        }
        return owners[category]
