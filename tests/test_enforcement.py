import json
from pathlib import Path

import pytest

from src.agents.enforcement import EnforcementAgent
from src.enforcement import EnforcementEngine, load_enforcement_ruleset
from src.models import CaseIntake, DecisionOutcome
from src.orchestration import AnalysisWorkflow, LaunchReviewWorkflow

ROOT = Path(__file__).parents[1]


def load_benchmarks() -> list[dict[str, object]]:
    path = ROOT / "benchmarks" / "cases" / "week_1_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workflow() -> LaunchReviewWorkflow:
    return LaunchReviewWorkflow()


def test_ruleset_is_versioned_and_has_unique_priorities() -> None:
    ruleset = load_enforcement_ruleset()

    assert ruleset.ruleset_id == "RULESET-LAUNCH-001"
    assert ruleset.version == "1.0.0"
    assert len(ruleset.rules) == 8
    assert len({rule.priority for rule in ruleset.rules}) == len(ruleset.rules)


def test_all_benchmark_outcomes_match_expected(
    workflow: LaunchReviewWorkflow,
) -> None:
    mismatches: dict[str, tuple[str, str]] = {}

    for benchmark in load_benchmarks():
        case = CaseIntake.model_validate(benchmark["case"])
        response = workflow.review(case)
        actual = response.enforcement.outcome.value
        expected = benchmark["expected"]["outcome"]
        if actual != expected:
            mismatches[case.case_id] = (expected, actual)

    assert mismatches == {}


def test_rule_trace_is_complete_and_winner_has_highest_matched_priority(
    workflow: LaunchReviewWorkflow,
) -> None:
    case = CaseIntake.model_validate(load_benchmarks()[13]["case"])

    result = workflow.review(case).enforcement

    assert len(result.rule_trace) == 8
    matched = [trace for trace in result.rule_trace if trace.matched]
    assert matched
    assert result.winning_rule_id == matched[0].rule_id
    assert result.outcome == DecisionOutcome.DENY
    assert result.human_approval_required
    assert "RULE-ALLOW-001" not in {trace.rule_id for trace in matched}


def test_conditional_allow_returns_blocking_controls(
    workflow: LaunchReviewWorkflow,
) -> None:
    case = CaseIntake.model_validate(load_benchmarks()[4]["case"])

    result = workflow.review(case).enforcement

    assert result.outcome == DecisionOutcome.CONDITIONAL_ALLOW
    assert result.required_controls
    assert all(control.blocking for control in result.required_controls)
    assert not result.human_approval_required


def test_allow_has_no_required_controls(
    workflow: LaunchReviewWorkflow,
) -> None:
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])

    result = workflow.review(case).enforcement

    assert result.outcome == DecisionOutcome.ALLOW
    assert result.required_controls == []
    assert result.winning_rule_id == "RULE-ALLOW-001"


def test_enforcement_rejects_analysis_from_another_case() -> None:
    benchmarks = load_benchmarks()
    first_case = CaseIntake.model_validate(benchmarks[0]["case"])
    second_case = CaseIntake.model_validate(benchmarks[1]["case"])
    analysis = AnalysisWorkflow().analyze(first_case)

    with pytest.raises(ValueError, match="case_id must match"):
        EnforcementAgent().enforce(second_case, analysis)


def test_engine_rejects_unknown_predicate() -> None:
    ruleset = load_enforcement_ruleset()
    invalid = ruleset.model_copy(
        update={
            "rules": [
                ruleset.rules[0].model_copy(update={"predicate": "not_registered"}),
                *ruleset.rules[1:],
            ]
        }
    )

    with pytest.raises(ValueError, match="unknown enforcement predicates"):
        EnforcementEngine(invalid)
