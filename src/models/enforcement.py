from datetime import date

from pydantic import Field, model_validator

from src.models.analysis import ParallelAnalysisResponse
from src.models.case import CaseIntake, StrictModel
from src.models.decision import (
    ControlRequirement,
    DecisionOutcome,
    FindingCategory,
    FindingSeverity,
)


class EnforcementRule(StrictModel):
    rule_id: str = Field(pattern=r"^RULE-(?:DENY|ESC|COND|ALLOW)-\d{3}$")
    title: str = Field(min_length=5, max_length=150)
    priority: int = Field(ge=0, le=10000)
    outcome: DecisionOutcome
    risk_level: FindingSeverity
    predicate: str = Field(min_length=3, max_length=100)
    explanation: str = Field(min_length=10, max_length=1000)
    required_categories: list[FindingCategory] = Field(default_factory=list)


class EnforcementRuleset(StrictModel):
    ruleset_id: str = Field(pattern=r"^RULESET-[A-Z]+-\d{3}$")
    version: str = Field(min_length=1, max_length=30)
    effective_date: date
    rules: list[EnforcementRule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_rules(self) -> "EnforcementRuleset":
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule IDs must be unique")
        priorities = [rule.priority for rule in self.rules]
        if len(priorities) != len(set(priorities)):
            raise ValueError("rule priorities must be unique")
        return self


class RuleTrace(StrictModel):
    rule_id: str
    title: str
    priority: int
    matched: bool
    outcome: DecisionOutcome
    risk_level: FindingSeverity
    predicate: str
    explanation: str
    facts: dict[str, object]


class EnforcementResult(StrictModel):
    case_id: str = Field(pattern=r"^CASE-\d{3}$")
    outcome: DecisionOutcome
    risk_level: FindingSeverity
    summary: str = Field(min_length=10, max_length=1000)
    human_approval_required: bool
    ruleset_id: str
    ruleset_version: str
    winning_rule_id: str
    rule_trace: list[RuleTrace] = Field(min_length=1)
    required_controls: list[ControlRequirement] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_contract(self) -> "EnforcementResult":
        matched_ids = {trace.rule_id for trace in self.rule_trace if trace.matched}
        if self.winning_rule_id not in matched_ids:
            raise ValueError("winning rule must be present in the matched trace")
        if self.outcome == DecisionOutcome.CONDITIONAL_ALLOW and not self.required_controls:
            raise ValueError("conditional allow requires blocking controls")
        if self.outcome == DecisionOutcome.ESCALATE and not self.human_approval_required:
            raise ValueError("escalation requires human approval")
        if self.outcome == DecisionOutcome.DENY and not self.human_approval_required:
            raise ValueError("denial requires human confirmation")
        return self


class EnforcementRequest(StrictModel):
    case: CaseIntake
    analysis: ParallelAnalysisResponse | None = None
    top_k: int = Field(default=8, ge=1, le=25)


class LaunchReviewResponse(StrictModel):
    analysis: ParallelAnalysisResponse
    enforcement: EnforcementResult
