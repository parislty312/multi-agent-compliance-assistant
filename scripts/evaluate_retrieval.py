import json
from pathlib import Path

from src.knowledge import PolicyRetriever
from src.models import CaseIntake, EvidenceQuery

ROOT = Path(__file__).parents[1]
BENCHMARK_PATH = ROOT / "benchmarks" / "cases" / "week_1_cases.json"


def main() -> None:
    benchmarks = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    retriever = PolicyRetriever()
    expected_total = 0
    retrieved_total = 0
    case_results: list[dict[str, object]] = []

    for benchmark in benchmarks:
        case = CaseIntake.model_validate(benchmark["case"])
        response = retriever.retrieve(EvidenceQuery(case=case, top_k=8))
        expected = set(benchmark["expected"]["categories"])
        retrieved = {
            category.value
            for match in response.matches
            for category in match.chunk.categories
        }
        hits = expected & retrieved
        expected_total += len(expected)
        retrieved_total += len(hits)
        case_results.append(
            {
                "case_id": case.case_id,
                "expected_categories": sorted(expected),
                "covered_categories": sorted(hits),
                "top_section": response.matches[0].chunk.section_id,
                "passed": expected == hits,
            }
        )

    report = {
        "benchmark_cases": len(benchmarks),
        "policy_documents": len(retriever.documents),
        "evidence_chunks": len(retriever.chunks),
        "expected_category_recall_at_8": round(
            retrieved_total / expected_total,
            3,
        ),
        "passed_cases": sum(result["passed"] for result in case_results),
        "cases": case_results,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

