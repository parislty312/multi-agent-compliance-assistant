import json
from pathlib import Path

from src.agents.common import validate_finding_citations
from src.models import CaseIntake
from src.orchestration import AnalysisWorkflow

ROOT = Path(__file__).parents[1]
BENCHMARK_PATH = ROOT / "benchmarks" / "cases" / "week_1_cases.json"


def main() -> None:
    benchmarks = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    workflow = AnalysisWorkflow()
    results: list[dict[str, object]] = []

    for benchmark in benchmarks:
        case = CaseIntake.model_validate(benchmark["case"])
        response = workflow.analyze(case)
        validate_finding_citations(response.legal.findings, response.evidence)
        validate_finding_citations(response.policy.findings, response.evidence)
        expected = set(benchmark["expected"]["categories"])
        produced = {
            finding.category.value
            for finding in [*response.legal.findings, *response.policy.findings]
        }
        results.append(
            {
                "case_id": case.case_id,
                "expected_categories": sorted(expected),
                "produced_categories": sorted(produced),
                "expected_coverage": sorted(expected & produced),
                "legal_findings": len(response.legal.findings),
                "policy_findings": len(response.policy.findings),
                "controls": len(response.policy.controls),
                "unsupported_findings": 0,
                "passed": expected <= produced,
            }
        )

    report = {
        "cases": len(results),
        "passed_cases": sum(result["passed"] for result in results),
        "citation_validity_rate": 1.0,
        "results": results,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

