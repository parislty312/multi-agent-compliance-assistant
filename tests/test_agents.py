import json
from pathlib import Path

import pytest

from src.agents.common import validate_finding_citations
from src.agents.legal import LegalAgent
from src.agents.policy import PolicyAgent
from src.knowledge import PolicyRetriever
from src.models import (
    AgentFinding,
    CaseIntake,
    Citation,
    EvidenceQuery,
    EvidenceResponse,
    FindingCategory,
    FindingSeverity,
)
from src.orchestration import AnalysisWorkflow

ROOT = Path(__file__).parents[1]


def load_benchmarks() -> list[dict[str, object]]:
    path = ROOT / "benchmarks" / "cases" / "week_1_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def retriever() -> PolicyRetriever:
    return PolicyRetriever()


def test_legal_agent_citations_are_bound_to_retrieved_evidence(
    retriever: PolicyRetriever,
) -> None:
    case = CaseIntake.model_validate(load_benchmarks()[9]["case"])
    evidence = retriever.retrieve(EvidenceQuery(case=case, top_k=8))

    analysis = LegalAgent().analyze(case, evidence)

    assert analysis.findings
    validate_finding_citations(analysis.findings, evidence)
    assert FindingCategory.HIGH_IMPACT_DECISION in {
        finding.category for finding in analysis.findings
    }
    assert any(finding.requires_human_review for finding in analysis.findings)


def test_policy_agent_produces_controls_linked_to_its_findings(
    retriever: PolicyRetriever,
) -> None:
    case = CaseIntake.model_validate(load_benchmarks()[5]["case"])
    evidence = retriever.retrieve(EvidenceQuery(case=case, top_k=8))

    analysis = PolicyAgent().analyze(case, evidence)

    finding_ids = {finding.finding_id for finding in analysis.findings}
    assert analysis.controls
    assert all(set(control.source_finding_ids) <= finding_ids for control in analysis.controls)
    assert any(control.owner == "Youth Safety" for control in analysis.controls)
    assert any(control.blocking for control in analysis.controls)


def test_agent_rejects_citation_outside_evidence() -> None:
    finding = AgentFinding(
        finding_id="FND-001",
        agent="legal",
        category=FindingCategory.PRIVACY,
        severity=FindingSeverity.LOW,
        statement="The feature requires documented privacy controls.",
        rationale="The case processes account data for an AI feature.",
        citations=[
            Citation(
                source_id="POL-FAKE-999@1.0.0",
                section="FAKE-1.1",
                excerpt="This evidence was never retrieved.",
            )
        ],
        confidence=0.5,
        requires_human_review=False,
    )

    with pytest.raises(ValueError, match="outside the response"):
        validate_finding_citations(
            [finding],
            EvidenceResponse(
                query="privacy",
                index_version="test",
                total_candidates=0,
                matches=[],
            ),
        )


def test_legal_agent_abstains_when_required_evidence_is_missing() -> None:
    case = CaseIntake.model_validate(load_benchmarks()[8]["case"])
    empty_evidence = EvidenceResponse(
        query="employment",
        index_version="empty-index",
        total_candidates=0,
        matches=[],
    )

    analysis = LegalAgent().analyze(case, empty_evidence)

    assert not analysis.findings
    assert FindingCategory.HIGH_IMPACT_DECISION in analysis.abstained_categories
    assert any("No retrieved evidence supported" in item for item in analysis.open_questions)


def test_parallel_workflow_uses_one_evidence_snapshot(
    retriever: PolicyRetriever,
) -> None:
    case = CaseIntake.model_validate(load_benchmarks()[8]["case"])

    response = AnalysisWorkflow(retriever=retriever).analyze(case)

    assert response.case_id == case.case_id
    assert response.legal.evidence_index_version == response.evidence.index_version
    assert response.policy.evidence_index_version == response.evidence.index_version
    assert {finding.agent for finding in response.legal.findings} == {"legal"}
    assert {finding.agent for finding in response.policy.findings} == {"policy"}


def test_all_benchmarks_produce_supported_analysis(
    retriever: PolicyRetriever,
) -> None:
    workflow = AnalysisWorkflow(retriever=retriever)

    for benchmark in load_benchmarks():
        case = CaseIntake.model_validate(benchmark["case"])
        response = workflow.analyze(case)
        validate_finding_citations(response.legal.findings, response.evidence)
        validate_finding_citations(response.policy.findings, response.evidence)
        assert response.legal.findings
        assert response.policy.findings
        assert response.policy.controls
        control_ids = [control.control_id for control in response.policy.controls]
        assert len(control_ids) == len(set(control_ids))
        produced_categories = {
            finding.category.value
            for finding in [*response.legal.findings, *response.policy.findings]
        }
        assert set(benchmark["expected"]["categories"]) <= produced_categories
