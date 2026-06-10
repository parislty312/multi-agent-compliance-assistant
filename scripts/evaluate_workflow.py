import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.models import CaseIntake, WorkflowStatus
from src.orchestration import DurableOrchestrator
from src.workflow import SQLiteWorkflowRepository

ROOT = Path(__file__).parents[1]
BENCHMARK_PATH = ROOT / "benchmarks" / "cases" / "week_1_cases.json"


def main() -> None:
    benchmarks = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []

    with TemporaryDirectory() as directory:
        repository = SQLiteWorkflowRepository(
            Path(directory) / "workflow-evaluation.db"
        )
        orchestrator = DurableOrchestrator(repository=repository)

        for benchmark in benchmarks:
            case = CaseIntake.model_validate(benchmark["case"])
            expected_outcome = benchmark["expected"]["outcome"]
            expected_status = (
                WorkflowStatus.AWAITING_APPROVAL
                if expected_outcome in {"escalate", "deny"}
                else WorkflowStatus.COMPLETED
            )
            run = orchestrator.start(
                case,
                idempotency_key=f"evaluation:{case.case_id}",
            )
            repeated = orchestrator.start(
                case,
                idempotency_key=f"evaluation:{case.case_id}",
            )
            events = repository.list_events(run.run_id)
            passed = all(
                [
                    run.status == expected_status,
                    run.analysis is not None,
                    run.enforcement is not None,
                    run.audit is not None,
                    run.record is not None,
                    repeated.run_id == run.run_id,
                    repository.verify_event_chain(run.run_id),
                ]
            )
            results.append(
                {
                    "case_id": case.case_id,
                    "expected_status": expected_status.value,
                    "actual_status": run.status.value,
                    "attempt_count": run.attempt_count,
                    "event_count": len(events),
                    "event_chain_valid": repository.verify_event_chain(
                        run.run_id
                    ),
                    "idempotent_replay": repeated.run_id == run.run_id,
                    "passed": passed,
                }
            )

    report = {
        "cases": len(results),
        "passed_cases": sum(result["passed"] for result in results),
        "event_chains_valid": sum(
            result["event_chain_valid"] for result in results
        ),
        "idempotent_replays": sum(
            result["idempotent_replay"] for result in results
        ),
        "results": results,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

