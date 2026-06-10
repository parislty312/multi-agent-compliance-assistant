import json
import sqlite3
from pathlib import Path

import pytest

from src.agents.enforcement import EnforcementAgent
from src.models import (
    ApprovalAction,
    ApprovalRequest,
    CaseIntake,
    DecisionOutcome,
    WorkflowStatus,
)
from src.orchestration import (
    AnalysisWorkflow,
    DurableOrchestrator,
    InvalidWorkflowTransitionError,
)
from src.workflow import SQLiteWorkflowRepository, WorkflowConflictError

ROOT = Path(__file__).parents[1]


def load_benchmarks() -> list[dict[str, object]]:
    path = ROOT / "benchmarks" / "cases" / "week_1_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def make_orchestrator(tmp_path: Path) -> DurableOrchestrator:
    repository = SQLiteWorkflowRepository(tmp_path / "workflows.db")
    return DurableOrchestrator(repository=repository)


def test_low_risk_workflow_completes_and_event_chain_verifies(
    tmp_path: Path,
) -> None:
    orchestrator = make_orchestrator(tmp_path)
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])

    run = orchestrator.start(case, idempotency_key="low-risk-case")
    events = orchestrator.repository.list_events(run.run_id)

    assert run.status == WorkflowStatus.COMPLETED
    assert run.final_outcome == DecisionOutcome.ALLOW
    assert run.analysis and run.enforcement and run.audit and run.record
    assert [event.sequence for event in events] == list(
        range(1, len(events) + 1)
    )
    assert orchestrator.repository.verify_event_chain(run.run_id)


def test_high_risk_workflow_waits_for_human_approval(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path)
    case = CaseIntake.model_validate(load_benchmarks()[8]["case"])

    run = orchestrator.start(case, idempotency_key="high-risk-case")

    assert run.status == WorkflowStatus.AWAITING_APPROVAL
    assert run.final_outcome is None
    assert run.enforcement
    assert run.enforcement.outcome == DecisionOutcome.ESCALATE

    decided = orchestrator.decide(
        run.run_id,
        ApprovalRequest(
            action=ApprovalAction.APPROVE,
            reviewer="Compliance Reviewer",
            rationale="The documented safeguards and specialist review are sufficient.",
        ),
    )

    assert decided.status == WorkflowStatus.COMPLETED
    assert decided.final_outcome == DecisionOutcome.ESCALATE
    assert decided.human_decision
    assert decided.human_decision.reviewer == "Compliance Reviewer"


def test_human_override_preserves_original_enforcement(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path)
    case = CaseIntake.model_validate(load_benchmarks()[8]["case"])
    run = orchestrator.start(case, idempotency_key="override-case")

    decided = orchestrator.decide(
        run.run_id,
        ApprovalRequest(
            action=ApprovalAction.OVERRIDE,
            reviewer="Senior Compliance Officer",
            rationale="Additional offline evidence supports conditional launch controls.",
            override_outcome=DecisionOutcome.CONDITIONAL_ALLOW,
        ),
    )

    assert decided.enforcement
    assert decided.enforcement.outcome == DecisionOutcome.ESCALATE
    assert decided.final_outcome == DecisionOutcome.CONDITIONAL_ALLOW
    assert decided.human_decision
    assert decided.human_decision.action == ApprovalAction.OVERRIDE


def test_idempotency_returns_same_run_and_rejects_different_request(
    tmp_path: Path,
) -> None:
    orchestrator = make_orchestrator(tmp_path)
    cases = load_benchmarks()
    first = CaseIntake.model_validate(cases[0]["case"])
    second = CaseIntake.model_validate(cases[1]["case"])

    original = orchestrator.start(first, idempotency_key="stable-key")
    repeated = orchestrator.start(first, idempotency_key="stable-key")

    assert repeated.run_id == original.run_id
    assert len(orchestrator.repository.list_events(original.run_id)) == len(
        orchestrator.repository.list_events(repeated.run_id)
    )

    with pytest.raises(WorkflowConflictError, match="different request"):
        orchestrator.start(second, idempotency_key="stable-key")


class CountingAnalysisWorkflow:
    def __init__(self) -> None:
        self.calls = 0
        self.real = AnalysisWorkflow()

    def analyze(self, case: CaseIntake, *, top_k: int = 8):
        self.calls += 1
        return self.real.analyze(case, top_k=top_k)


class FlakyEnforcementAgent:
    def __init__(self) -> None:
        self.calls = 0
        self.real = EnforcementAgent()

    def enforce(self, case: CaseIntake, analysis):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary enforcement outage")
        return self.real.enforce(case, analysis)


def test_resume_uses_analysis_checkpoint_after_enforcement_failure(
    tmp_path: Path,
) -> None:
    repository = SQLiteWorkflowRepository(tmp_path / "resume.db")
    analysis = CountingAnalysisWorkflow()
    enforcement = FlakyEnforcementAgent()
    orchestrator = DurableOrchestrator(
        repository=repository,
        analysis_workflow=analysis,
        enforcement_agent=enforcement,
    )
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])

    failed = orchestrator.start(case, idempotency_key="resume-case")

    assert failed.status == WorkflowStatus.FAILED
    assert failed.retryable
    assert failed.analysis is not None
    assert failed.enforcement is None
    assert analysis.calls == 1

    resumed = orchestrator.resume(failed.run_id)

    assert resumed.status == WorkflowStatus.COMPLETED
    assert resumed.attempt_count == 2
    assert analysis.calls == 1
    assert enforcement.calls == 2


def test_optimistic_version_rejects_stale_writer(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path)
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])
    completed = orchestrator.start(case, idempotency_key="version-case")
    first_reader = orchestrator.repository.get(completed.run_id)
    stale_reader = orchestrator.repository.get(completed.run_id)

    orchestrator.repository.save(
        first_reader.model_copy(update={"error": "first writer"}),
        expected_version=first_reader.version,
    )

    with pytest.raises(WorkflowConflictError, match="changed after version"):
        orchestrator.repository.save(
            stale_reader.model_copy(update={"error": "stale writer"}),
            expected_version=stale_reader.version,
        )


def test_event_chain_detects_database_tampering(tmp_path: Path) -> None:
    database_path = tmp_path / "tamper.db"
    orchestrator = DurableOrchestrator(
        repository=SQLiteWorkflowRepository(database_path)
    )
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])
    run = orchestrator.start(case, idempotency_key="tamper-case")

    assert orchestrator.repository.verify_event_chain(run.run_id)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE workflow_events
            SET payload_json = '{"tampered":true}'
            WHERE run_id = ? AND sequence = 1
            """,
            (run.run_id,),
        )

    assert not orchestrator.repository.verify_event_chain(run.run_id)


def test_completed_workflow_cannot_be_resumed(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path)
    case = CaseIntake.model_validate(load_benchmarks()[0]["case"])
    run = orchestrator.start(case, idempotency_key="terminal-case")

    with pytest.raises(InvalidWorkflowTransitionError):
        orchestrator.resume(run.run_id)
