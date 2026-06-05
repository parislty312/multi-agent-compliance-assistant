from collections.abc import Callable

from src.models import (
    AgeGroup,
    CaseIntake,
    DataCategory,
    DecisionOutcome,
    EnforcementResult,
    EnforcementRule,
    EnforcementRuleset,
    ParallelAnalysisResponse,
    RuleTrace,
)

Predicate = Callable[
    [CaseIntake, ParallelAnalysisResponse],
    tuple[bool, dict[str, object]],
]


class EnforcementEngine:
    def __init__(self, ruleset: EnforcementRuleset) -> None:
        self.ruleset = ruleset
        self.predicates: dict[str, Predicate] = {
            "unsafe_child_companion": self._unsafe_child_companion,
            "autonomous_employment_termination": (
                self._autonomous_employment_termination
            ),
            "high_impact_automated_decision": self._high_impact_automated_decision,
            "biometric_identity_decision": self._biometric_identity_decision,
            "material_launch_gap": self._material_launch_gap,
            "minor_safeguard_review": self._minor_safeguard_review,
            "sensitive_data_review": self._sensitive_data_review,
            "baseline_allow": self._baseline_allow,
        }
        unknown = {
            rule.predicate
            for rule in ruleset.rules
            if rule.predicate not in self.predicates
        }
        if unknown:
            raise ValueError(f"unknown enforcement predicates: {sorted(unknown)}")

    def evaluate(
        self,
        case: CaseIntake,
        analysis: ParallelAnalysisResponse,
    ) -> EnforcementResult:
        if analysis.case_id != case.case_id:
            raise ValueError("analysis case_id must match enforcement case")

        traces: list[RuleTrace] = []
        higher_priority_match = False
        for rule in sorted(
            self.ruleset.rules,
            key=lambda item: (-item.priority, item.rule_id),
        ):
            trace = self._evaluate_rule(rule, case, analysis)
            if rule.predicate == "baseline_allow" and higher_priority_match:
                trace = trace.model_copy(
                    update={
                        "matched": False,
                        "facts": {
                            **trace.facts,
                            "suppressed_by_higher_priority_rule": True,
                        },
                    }
                )
            traces.append(trace)
            if trace.matched:
                higher_priority_match = True
        winning = next(trace for trace in traces if trace.matched)
        blocking_controls = [
            control for control in analysis.policy.controls if control.blocking
        ]
        required_controls = (
            blocking_controls
            if winning.outcome
            in {
                DecisionOutcome.CONDITIONAL_ALLOW,
                DecisionOutcome.ESCALATE,
                DecisionOutcome.DENY,
            }
            else []
        )
        open_questions = list(
            dict.fromkeys(
                [
                    *analysis.legal.open_questions,
                    *analysis.policy.open_questions,
                ]
            )
        )

        return EnforcementResult(
            case_id=case.case_id,
            outcome=winning.outcome,
            risk_level=winning.risk_level,
            summary=(
                f"{winning.outcome.value} selected by {winning.rule_id}: "
                f"{winning.explanation}"
            ),
            human_approval_required=winning.outcome
            in {DecisionOutcome.ESCALATE, DecisionOutcome.DENY},
            ruleset_id=self.ruleset.ruleset_id,
            ruleset_version=self.ruleset.version,
            winning_rule_id=winning.rule_id,
            rule_trace=traces,
            required_controls=required_controls,
            open_questions=open_questions,
        )

    def _evaluate_rule(
        self,
        rule: EnforcementRule,
        case: CaseIntake,
        analysis: ParallelAnalysisResponse,
    ) -> RuleTrace:
        matched, facts = self.predicates[rule.predicate](case, analysis)
        available_categories = {
            finding.category
            for finding in [
                *analysis.legal.findings,
                *analysis.policy.findings,
            ]
        }
        missing_categories = set(rule.required_categories) - available_categories
        if matched and missing_categories:
            matched = False
            facts["missing_required_categories"] = sorted(
                category.value for category in missing_categories
            )
        return RuleTrace(
            rule_id=rule.rule_id,
            title=rule.title,
            priority=rule.priority,
            matched=matched,
            outcome=rule.outcome,
            risk_level=rule.risk_level,
            predicate=rule.predicate,
            explanation=rule.explanation,
            facts=facts,
        )

    @staticmethod
    def _unsafe_child_companion(
        case: CaseIntake,
        _: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        facts = {
            "under_13": AgeGroup.UNDER_13 in case.affected_age_groups,
            "feature_type": case.feature_type.value,
            "human_oversight": case.human_oversight.enabled,
            "user_notice": case.user_notice_present,
            "safety_evaluation": case.safety_evaluation_complete,
        }
        matched = (
            facts["under_13"]
            and case.feature_type.value == "chatbot"
            and not case.human_oversight.enabled
            and not case.user_notice_present
            and not case.safety_evaluation_complete
        )
        return matched, facts

    @staticmethod
    def _autonomous_employment_termination(
        case: CaseIntake,
        _: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        domain = (case.decision_domain or "").lower()
        facts = {
            "automated_decision": case.automated_decision,
            "decision_domain": domain,
            "human_oversight": case.human_oversight.enabled,
            "appeal": case.human_oversight.user_appeal_available,
        }
        matched = (
            case.automated_decision
            and "employment termination" in domain
            and not case.human_oversight.enabled
            and not case.human_oversight.user_appeal_available
        )
        return matched, facts

    @staticmethod
    def _high_impact_automated_decision(
        case: CaseIntake,
        _: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        domain = (case.decision_domain or "").lower()
        high_impact_terms = {
            "employment",
            "credit",
            "healthcare",
            "education",
            "account access",
        }
        matched_terms = sorted(term for term in high_impact_terms if term in domain)
        facts = {
            "automated_decision": case.automated_decision,
            "decision_domain": domain,
            "matched_domains": matched_terms,
        }
        return case.automated_decision and bool(matched_terms), facts

    @staticmethod
    def _biometric_identity_decision(
        case: CaseIntake,
        _: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        facts = {
            "automated_decision": case.automated_decision,
            "biometric_data": DataCategory.BIOMETRIC in case.data_categories,
            "feature_type": case.feature_type.value,
        }
        matched = (
            case.automated_decision
            and DataCategory.BIOMETRIC in case.data_categories
            and case.feature_type.value == "identity_verification"
        )
        return matched, facts

    @staticmethod
    def _material_launch_gap(
        case: CaseIntake,
        analysis: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        blocking_controls = [
            control.control_id
            for control in analysis.policy.controls
            if control.blocking
        ]
        facts = {
            "missing_notice": not case.user_notice_present,
            "missing_safety_evaluation": not case.safety_evaluation_complete,
            "open_question_count": len(case.open_questions),
            "blocking_controls": blocking_controls,
        }
        matched = bool(
            not case.user_notice_present
            or not case.safety_evaluation_complete
            or case.open_questions
            or blocking_controls
        )
        return matched, facts

    @staticmethod
    def _minor_safeguard_review(
        case: CaseIntake,
        _: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        minor_groups = {
            AgeGroup.UNDER_13,
            AgeGroup.TEEN_13_TO_17,
            AgeGroup.ALL_AGES,
        }
        affected = sorted(
            age.value for age in set(case.affected_age_groups) & minor_groups
        )
        facts = {
            "affected_minor_groups": affected,
            "minor_data": DataCategory.MINOR_DATA in case.data_categories,
        }
        return bool(affected), facts

    @staticmethod
    def _sensitive_data_review(
        case: CaseIntake,
        _: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        sensitive = {
            DataCategory.BIOMETRIC,
            DataCategory.HEALTH,
            DataCategory.FINANCIAL,
            DataCategory.PRECISE_LOCATION,
        }
        matched_data = sorted(
            item.value for item in set(case.data_categories) & sensitive
        )
        facts = {
            "sensitive_data": matched_data,
            "open_question_count": len(case.open_questions),
        }
        return bool(matched_data and case.open_questions), facts

    @staticmethod
    def _baseline_allow(
        _: CaseIntake,
        __: ParallelAnalysisResponse,
    ) -> tuple[bool, dict[str, object]]:
        return True, {"fallback": True}
