import json
from pathlib import Path

import pytest

from src.knowledge import PolicyRetriever
from src.knowledge.loader import build_evidence_chunks, load_policy_documents
from src.models import CaseIntake, EvidenceQuery

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def retriever() -> PolicyRetriever:
    return PolicyRetriever()


def load_benchmarks() -> list[dict[str, object]]:
    path = ROOT / "benchmarks" / "cases" / "week_1_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_policy_library_loads_versioned_synthetic_documents() -> None:
    documents = load_policy_documents()
    chunks = build_evidence_chunks(documents)

    assert len(documents) == 6
    assert len(chunks) == 19
    assert all(document.synthetic for document in documents)
    assert all(chunk.policy_version and chunk.section_id for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_credit_case_prioritizes_credit_policy(retriever: PolicyRetriever) -> None:
    case_payload = load_benchmarks()[9]["case"]
    case = CaseIntake.model_validate(case_payload)

    response = retriever.retrieve(EvidenceQuery(case=case, top_k=5))

    assert response.matches
    assert response.matches[0].chunk.section_id == "HIGH-1.2"
    assert "decision_domain" in response.matches[0].matched_on


def test_benchmark_expected_category_recall_is_complete(
    retriever: PolicyRetriever,
) -> None:
    missed: dict[str, list[str]] = {}

    for benchmark in load_benchmarks():
        case = CaseIntake.model_validate(benchmark["case"])
        response = retriever.retrieve(EvidenceQuery(case=case, top_k=8))
        retrieved_categories = {
            category.value
            for match in response.matches
            for category in match.chunk.categories
        }
        expected_categories = set(benchmark["expected"]["categories"])
        missing = sorted(expected_categories - retrieved_categories)
        if missing:
            missed[case.case_id] = missing

    assert missed == {}


def test_evidence_matches_are_precisely_citable(retriever: PolicyRetriever) -> None:
    response = retriever.retrieve(
        EvidenceQuery(
            query_text="harmful image output reporting and incident response",
            jurisdictions=["US"],
            top_k=3,
        )
    )

    first = response.matches[0]
    assert first.chunk.policy_id == "POL-SAFE-001"
    assert first.chunk.section_id == "SAFE-1.2"
    assert first.chunk.policy_version == "1.0.0"
    assert first.chunk.text
    assert first.score > 0
    assert first.matched_on

