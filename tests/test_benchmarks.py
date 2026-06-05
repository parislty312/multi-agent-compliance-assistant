import json
from collections import Counter
from pathlib import Path

from src.models import CaseIntake, DecisionOutcome, FindingCategory, FindingSeverity

BENCHMARK_PATH = (
    Path(__file__).parents[1] / "benchmarks" / "cases" / "week_1_cases.json"
)


def load_benchmarks() -> list[dict[str, object]]:
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


def test_week_one_has_fifteen_valid_unique_cases() -> None:
    benchmarks = load_benchmarks()
    cases = [CaseIntake.model_validate(item["case"]) for item in benchmarks]

    assert len(cases) == 15
    assert len({case.case_id for case in cases}) == 15


def test_week_one_covers_every_decision_outcome() -> None:
    outcomes = Counter(item["expected"]["outcome"] for item in load_benchmarks())

    assert set(outcomes) == {outcome.value for outcome in DecisionOutcome}
    assert all(count >= 2 for count in outcomes.values())


def test_expected_labels_use_supported_risk_taxonomy() -> None:
    valid_risks = {risk.value for risk in FindingSeverity}
    valid_categories = {category.value for category in FindingCategory}

    for item in load_benchmarks():
        expected = item["expected"]
        assert expected["risk_level"] in valid_risks
        assert expected["categories"]
        assert set(expected["categories"]) <= valid_categories


def test_benchmark_rationales_are_reviewable() -> None:
    for item in load_benchmarks():
        assert len(item["rationale"]) >= 30

