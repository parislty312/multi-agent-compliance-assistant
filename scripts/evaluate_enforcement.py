import json
from collections import Counter
from pathlib import Path

from src.models import CaseIntake
from src.orchestration import LaunchReviewWorkflow

ROOT = Path(__file__).parents[1]
BENCHMARK_PATH = ROOT / "benchmarks" / "cases" / "week_1_cases.json"


def main() -> None:
    benchmarks = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    workflow = LaunchReviewWorkflow()
    results: list[dict[str, object]] = []

    for benchmark in benchmarks:
        case = CaseIntake.model_validate(benchmark["case"])
        response = workflow.review(case)
        expected = benchmark["expected"]["outcome"]
        actual = response.enforcement.outcome.value
        results.append(
            {
                "case_id": case.case_id,
                "expected": expected,
                "actual": actual,
                "winning_rule_id": response.enforcement.winning_rule_id,
                "risk_level": response.enforcement.risk_level.value,
                "matched_rules": [
                    trace.rule_id
                    for trace in response.enforcement.rule_trace
                    if trace.matched
                ],
                "required_controls": len(
                    response.enforcement.required_controls
                ),
                "passed": expected == actual,
            }
        )

    expected_counts = Counter(result["expected"] for result in results)
    actual_counts = Counter(result["actual"] for result in results)
    report = {
        "cases": len(results),
        "passed_cases": sum(result["passed"] for result in results),
        "outcome_accuracy": round(
            sum(result["passed"] for result in results) / len(results),
            3,
        ),
        "expected_distribution": dict(sorted(expected_counts.items())),
        "actual_distribution": dict(sorted(actual_counts.items())),
        "results": results,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
