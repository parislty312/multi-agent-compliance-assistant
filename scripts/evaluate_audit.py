import json
from pathlib import Path

from src.agents.audit import AuditAgent
from src.audit import verify_decision_record
from src.models import AuditCheckStatus, CaseIntake, Citation
from src.orchestration import AuditedReviewWorkflow, LaunchReviewWorkflow

ROOT = Path(__file__).parents[1]
BENCHMARK_PATH = ROOT / "benchmarks" / "cases" / "week_1_cases.json"


def main() -> None:
    benchmarks = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    workflow = AuditedReviewWorkflow()
    results: list[dict[str, object]] = []

    for benchmark in benchmarks:
        case = CaseIntake.model_validate(benchmark["case"])
        result = workflow.review(case)
        results.append(
            {
                "case_id": case.case_id,
                "verdict": result.audit.verdict.value,
                "passed_checks": sum(
                    check.status == AuditCheckStatus.PASS
                    for check in result.audit.checks
                ),
                "total_checks": len(result.audit.checks),
                "record_hash_valid": verify_decision_record(result.record),
                "passed": (
                    result.audit.verdict.value == "pass"
                    and verify_decision_record(result.record)
                ),
            }
        )

    case = CaseIntake.model_validate(benchmarks[0]["case"])
    review = LaunchReviewWorkflow().review(case)
    finding = review.analysis.legal.findings[0].model_copy(
        update={
            "citations": [
                Citation(
                    source_id="POL-FAKE-999@9.9.9",
                    section="FAKE-9.9",
                    excerpt="Fabricated citation for audit evaluation.",
                )
            ]
        }
    )
    legal = review.analysis.legal.model_copy(
        update={"findings": [finding, *review.analysis.legal.findings[1:]]}
    )
    analysis = review.analysis.model_copy(update={"legal": legal})
    adversarial = review.model_copy(update={"analysis": analysis})
    adversarial_report = AuditAgent().audit(case, adversarial)

    report = {
        "cases": len(results),
        "passed_cases": sum(result["passed"] for result in results),
        "check_pass_rate": round(
            sum(result["passed_checks"] for result in results)
            / sum(result["total_checks"] for result in results),
            3,
        ),
        "valid_record_hashes": sum(
            result["record_hash_valid"] for result in results
        ),
        "fabricated_citation_detected": (
            adversarial_report.verdict.value == "fail"
            and bool(adversarial_report.unsupported_finding_ids)
        ),
        "results": results,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
