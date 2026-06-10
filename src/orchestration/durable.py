from datetime import UTC, datetime
from uuid import uuid4

from src.agents.audit import AuditAgent
from src.agents.enforcement import EnforcementAgent
from src.audit import build_decision_record
from src.models import (
    ApprovalAction,
    ApprovalRequest,
    AuditVerdict,
    CaseIntake,
    DecisionOutcome,
    HumanDecision,
    LaunchReviewResponse,
    WorkflowRun,
    WorkflowStage,
    WorkflowStatus,
)
from src.orchestration.analysis import AnalysisWorkflow
from src.workflow import SQLiteWorkflowRepository, WorkflowConflictError


class InvalidWorkflowTransitionError(RuntimeError):
    pass


class DurableOrchestrator:
    def __init__(
        self,
        *,
        repository: SQLiteWorkflowRepository,
        analysis_workflow: AnalysisWorkflow | None = None,
        enforcement_agent: EnforcementAgent | None = None,
        audit_agent: AuditAgent | None = None,
    ) -> None:
        self.repository = repository
        self.analysis_workflow = analysis_workflow or AnalysisWorkflow()
        self.enforcement_agent = enforcement_agent or EnforcementAgent()
        self.audit_agent = audit_agent or AuditAgent()

    def start(
        self,
        case: CaseIntake,
        *,
        idempotency_key: str | None = None,
        top_k: int = 8,
    ) -> WorkflowRun:
        key = idempotency_key or f"{case.case_id}:{uuid4().hex}"
        existing = self.repository.get_by_idempotency_key(key)
        if existing:
            if existing.case != case or existing.top_k != top_k:
                raise WorkflowConflictError(
                    "idempotency key already belongs to a different request"
                )
            return existing

        now = datetime.now(UTC)
        run = WorkflowRun(
            run_id=f"RUN-{uuid4().hex[:16].upper()}",
            idempotency_key=key,
            case=case,
            status=WorkflowStatus.SUBMITTED,
            current_stage=WorkflowStage.INTAKE,
            top_k=top_k,
            created_at=now,
            updated_at=now,
        )
        run = self.repository.create(run)
        self.repository.append_event(
            run_id=run.run_id,
            event_type="workflow_submitted",
            stage=WorkflowStage.INTAKE,
            payload={
                "case_id": case.case_id,
                "idempotency_key": key,
                "top_k": top_k,
            },
        )
        return self.execute(run.run_id)

    def execute(self, run_id: str) -> WorkflowRun:
        run = self.repository.get(run_id)
        if run.status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.AWAITING_APPROVAL,
        }:
            return run
        if run.status == WorkflowStatus.FAILED and not run.retryable:
            raise InvalidWorkflowTransitionError(
                f"workflow {run_id} failed with a non-retryable audit result"
            )

        run = self._save(
            run,
            attempt_count=run.attempt_count + 1,
            error=None,
        )
        try:
            if run.analysis is None:
                run = self._transition(
                    run,
                    status=WorkflowStatus.ANALYZING,
                    stage=WorkflowStage.ANALYSIS,
                    event_type="analysis_started",
                )
                analysis = self.analysis_workflow.analyze(
                    run.case,
                    top_k=run.top_k,
                )
                run = self._save(
                    run,
                    analysis=analysis,
                    status=WorkflowStatus.ENFORCING,
                    current_stage=WorkflowStage.ENFORCEMENT,
                )
                self.repository.append_event(
                    run_id=run.run_id,
                    event_type="analysis_completed",
                    stage=WorkflowStage.ANALYSIS,
                    payload={
                        "legal_findings": len(analysis.legal.findings),
                        "policy_findings": len(analysis.policy.findings),
                        "controls": len(analysis.policy.controls),
                        "evidence_index_version": analysis.evidence.index_version,
                    },
                )

            if run.enforcement is None:
                run = self._transition(
                    run,
                    status=WorkflowStatus.ENFORCING,
                    stage=WorkflowStage.ENFORCEMENT,
                    event_type="enforcement_started",
                )
                if run.analysis is None:
                    raise RuntimeError("analysis checkpoint is missing")
                enforcement = self.enforcement_agent.enforce(
                    run.case,
                    run.analysis,
                )
                run = self._save(
                    run,
                    enforcement=enforcement,
                    status=WorkflowStatus.AUDITING,
                    current_stage=WorkflowStage.AUDIT,
                )
                self.repository.append_event(
                    run_id=run.run_id,
                    event_type="enforcement_completed",
                    stage=WorkflowStage.ENFORCEMENT,
                    payload={
                        "outcome": enforcement.outcome.value,
                        "winning_rule_id": enforcement.winning_rule_id,
                        "ruleset_version": enforcement.ruleset_version,
                    },
                )

            if run.audit is None or run.record is None:
                run = self._transition(
                    run,
                    status=WorkflowStatus.AUDITING,
                    stage=WorkflowStage.AUDIT,
                    event_type="audit_started",
                )
                if run.analysis is None or run.enforcement is None:
                    raise RuntimeError("analysis or enforcement checkpoint is missing")
                review = LaunchReviewResponse(
                    analysis=run.analysis,
                    enforcement=run.enforcement,
                )
                audit = self.audit_agent.audit(run.case, review)
                record = build_decision_record(
                    case=run.case,
                    review=review,
                    audit=audit,
                )
                if audit.verdict == AuditVerdict.FAIL:
                    run = self._save(
                        run,
                        audit=audit,
                        record=record,
                        status=WorkflowStatus.FAILED,
                        current_stage=WorkflowStage.AUDIT,
                        error="audit failed; inspect audit checks",
                        retryable=False,
                    )
                    self.repository.append_event(
                        run_id=run.run_id,
                        event_type="audit_failed",
                        stage=WorkflowStage.AUDIT,
                        payload={
                            "verdict": audit.verdict.value,
                            "record_id": record.record_id,
                        },
                    )
                    return run

                needs_approval = (
                    audit.requires_human_review
                    or run.enforcement.human_approval_required
                )
                run = self._save(
                    run,
                    audit=audit,
                    record=record,
                    status=(
                        WorkflowStatus.AWAITING_APPROVAL
                        if needs_approval
                        else WorkflowStatus.COMPLETED
                    ),
                    current_stage=(
                        WorkflowStage.APPROVAL
                        if needs_approval
                        else WorkflowStage.COMPLETE
                    ),
                    final_outcome=(
                        None if needs_approval else run.enforcement.outcome
                    ),
                    retryable=False,
                )
                self.repository.append_event(
                    run_id=run.run_id,
                    event_type="audit_completed",
                    stage=WorkflowStage.AUDIT,
                    payload={
                        "verdict": audit.verdict.value,
                        "record_id": record.record_id,
                        "requires_human_review": needs_approval,
                    },
                )
                self.repository.append_event(
                    run_id=run.run_id,
                    event_type=(
                        "approval_requested"
                        if needs_approval
                        else "workflow_completed"
                    ),
                    stage=run.current_stage,
                    payload={
                        "outcome": run.enforcement.outcome.value,
                        "status": run.status.value,
                    },
                )
            return run
        except Exception as error:
            latest = self.repository.get(run.run_id)
            failed = self._save(
                latest,
                status=WorkflowStatus.FAILED,
                error=str(error),
                retryable=True,
            )
            self.repository.append_event(
                run_id=failed.run_id,
                event_type="workflow_failed",
                stage=failed.current_stage,
                payload={
                    "error": str(error),
                    "attempt_count": failed.attempt_count,
                },
            )
            return failed

    def resume(self, run_id: str) -> WorkflowRun:
        run = self.repository.get(run_id)
        if run.status != WorkflowStatus.FAILED or not run.retryable:
            raise InvalidWorkflowTransitionError(
                "only retryable failed workflows can be resumed"
            )
        self.repository.append_event(
            run_id=run_id,
            event_type="workflow_resumed",
            stage=run.current_stage,
            payload={"next_attempt": run.attempt_count + 1},
        )
        return self.execute(run_id)

    def decide(self, run_id: str, request: ApprovalRequest) -> WorkflowRun:
        run = self.repository.get(run_id)
        if run.status != WorkflowStatus.AWAITING_APPROVAL:
            raise InvalidWorkflowTransitionError(
                "human decisions require awaiting_approval status"
            )
        decision = HumanDecision.model_validate(request.model_dump())
        if decision.action == ApprovalAction.APPROVE:
            if run.enforcement is None:
                raise RuntimeError("enforcement result is missing")
            status = WorkflowStatus.COMPLETED
            final_outcome = run.enforcement.outcome
        elif decision.action == ApprovalAction.REJECT:
            status = WorkflowStatus.REJECTED
            final_outcome = DecisionOutcome.DENY
        else:
            status = WorkflowStatus.COMPLETED
            final_outcome = decision.override_outcome

        decided = self._save(
            run,
            status=status,
            current_stage=WorkflowStage.COMPLETE,
            human_decision=decision,
            final_outcome=final_outcome,
            retryable=False,
        )
        self.repository.append_event(
            run_id=run_id,
            event_type=f"human_{decision.action.value}",
            stage=WorkflowStage.APPROVAL,
            payload={
                "reviewer": decision.reviewer,
                "rationale": decision.rationale,
                "original_outcome": (
                    run.enforcement.outcome.value if run.enforcement else None
                ),
                "final_outcome": (
                    final_outcome.value if final_outcome else None
                ),
            },
        )
        self.repository.append_event(
            run_id=run_id,
            event_type="workflow_completed",
            stage=WorkflowStage.COMPLETE,
            payload={
                "status": decided.status.value,
                "final_outcome": (
                    decided.final_outcome.value
                    if decided.final_outcome
                    else None
                ),
            },
        )
        return decided

    def _transition(
        self,
        run: WorkflowRun,
        *,
        status: WorkflowStatus,
        stage: WorkflowStage,
        event_type: str,
    ) -> WorkflowRun:
        transitioned = self._save(
            run,
            status=status,
            current_stage=stage,
        )
        self.repository.append_event(
            run_id=run.run_id,
            event_type=event_type,
            stage=stage,
            payload={"attempt_count": transitioned.attempt_count},
        )
        return transitioned

    def _save(self, run: WorkflowRun, **updates: object) -> WorkflowRun:
        updated = run.model_copy(update=updates)
        return self.repository.save(updated, expected_version=run.version)
