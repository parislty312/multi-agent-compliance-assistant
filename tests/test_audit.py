import json
from pathlib import Path

from src.agents.audit import AuditAgent
from src.audit import build_decision_record, verify_decision_record
from src.models import (
    AuditCheckStatus,
    AuditVerdict,
    CaseIntake,
    Citation,
    FindingCategory,
)
from src.orchestration import AuditedReviewWorkflow, LaunchReviewWorkflow

ROOT = Path(__file__).parents[1]


def load_benchmarks() -> list[dict[str, object]]:
    path = ROOT / "benchmarks" / "cases" / "week_1_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def check_status(report: object, code: str) -> AuditCheckStatus:
    return next(check.status for check in report.checks if check.code == code)


def test_all_benchmark_reviews_pass_independent_audit() -> None:
    workflow = AuditedReviewWorkflow()

    for benchmark in load_benchmarks():
        case = CaseIntake.model_validate(benchmark["case"])
        result = workflow.review(case)

        assert result.audit.verdict == AuditVerdict.PASS
        assert all(
            check.status == AuditCheckStatus.PASS
            for check in result.audit.checks
        )
        assert verify_decision_record(result.record)


def test_audit_detects_fabricated_citation() -> None:
    case = CaseIntake.model_validate(load_benchmarks()[9]["case"])
    review = LaunchReviewWorkflow().review(case)
    finding = review.analysis.legal.findings[0].model_copy(
        update={
            "citations": [
                Citation(
                    source_id="POL-FAKE-999@9.9.9",
                    section="FAKE-9.9",
                    excerpt="This text does not exist in the evidence snapshot.",
                )
            ]
        }
    )
    legal = review.analysis.legal.model_copy(
        update={"findings": [finding, *review.analysis.legal.findings[1:]]}
    )
    analysis = review.analysis.model_copy(update={"legal": legal})
    tampered_review = review.model_copy(update={"analysis": analysis})

    report = AuditAgent().audit(case, tampered_review)

    assert report.verdict == AuditVerdict.FAIL
    assert (
        check_status(report, "CITATION_INTEGRITY")
        == AuditCheckStatus.FAIL
    )
    assert report.unsupported_finding_ids


def test_audit_detects_tampered_enforcement_result() -> None:
    case = CaseIntake.model_validate(load_benchmarks()[8]["case"])
    review = LaunchReviewWorkflow().review(case)
    enforcement = review.enforcement.model_copy(
        update={"summary": "A manually altered enforcement explanation."}
    )
    tampered_review = review.model_copy(update={"enforcement": enforcement})

    report = AuditAgent().audit(case, tampered_review)

    assert report.verdict == AuditVerdict.FAIL
    assert (
        check_status(report, "ENFORCEMENT_REPLAY")
        == AuditCheckStatus.FAIL
    )


def test_audit_detects_altered_required_control() -> None:
    case = CaseIntake.model_validate(load_benchmarks()[4]["case"])
    review = LaunchReviewWorkflow().review(case)
    altered_control = review.enforcement.required_controls[0].model_copy(
        update={"description": "An altered control not issued by the Policy Agent."}
    )
    enforcement = review.enforcement.model_copy(
        update={
            "required_controls": [
                altered_control,
                *review.enforcement.required_controls[1:],
            ]
        }
    )
    tampered_review = review.model_copy(update={"enforcement": enforcement})

    report = AuditAgent().audit(case, tampered_review)

    assert report.verdict == AuditVerdict.FAIL
    assert (
        check_status(report, "CONTROL_LINKAGE")
        == AuditCheckStatus.FAIL
    )


def test_decision_record_hash_detects_post_audit_change() -> None:
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])
    review = LaunchReviewWorkflow().review(case)
    audit = AuditAgent().audit(case, review)
    record = build_decision_record(case=case, review=review, audit=audit)
    altered_case = record.case.model_copy(
        update={"title": "A changed title after record creation"}
    )
    altered_record = record.model_copy(update={"case": altered_case})
    altered_metadata = record.model_copy(update={"case_id": "CASE-999"})

    assert verify_decision_record(record)
    assert not verify_decision_record(altered_record)
    assert not verify_decision_record(altered_metadata)
    assert record.record_id.startswith("REC-")
    assert len(record.content_hash) == 64


def test_audit_requires_review_for_agent_abstention() -> None:
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])
    review = LaunchReviewWorkflow().review(case)
    legal = review.analysis.legal.model_copy(
        update={"abstained_categories": [FindingCategory.TRANSPARENCY]}
    )
    analysis = review.analysis.model_copy(update={"legal": legal})
    abstained_review = review.model_copy(update={"analysis": analysis})

    report = AuditAgent().audit(case, abstained_review)

    assert report.verdict == AuditVerdict.REVIEW_REQUIRED
    assert report.requires_human_review
    assert (
        check_status(report, "ANALYSIS_ABSTENTION")
        == AuditCheckStatus.FAIL
    )
