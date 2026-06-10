import os

from fastapi import FastAPI, HTTPException

from src.audit import verify_decision_record
from src.knowledge import PolicyRetriever
from src.models import (
    ApprovalRequest,
    AuditedLaunchReview,
    AuditRequest,
    CaseAnalysisRequest,
    CaseIntake,
    DecisionRecord,
    EvidenceQuery,
    EvidenceResponse,
    EnforcementRequest,
    LaunchReviewResponse,
    ParallelAnalysisResponse,
    StartWorkflowRequest,
    WorkflowEvent,
    WorkflowRun,
)
from src.orchestration import (
    AnalysisWorkflow,
    AuditedReviewWorkflow,
    DurableOrchestrator,
    InvalidWorkflowTransitionError,
    LaunchReviewWorkflow,
)
from src.workflow import (
    SQLiteWorkflowRepository,
    WorkflowConflictError,
    WorkflowNotFoundError,
)

app = FastAPI(
    title="Multi-Agent Compliance Assistant",
    description="Auditable compliance decision support for AI product launches.",
    version="0.1.0",
)
retriever = PolicyRetriever()
analysis_workflow = AnalysisWorkflow(retriever=retriever)
launch_review_workflow = LaunchReviewWorkflow(analysis_workflow=analysis_workflow)
audited_review_workflow = AuditedReviewWorkflow(
    launch_review_workflow=launch_review_workflow
)
workflow_repository = SQLiteWorkflowRepository(
    os.getenv("WORKFLOW_DB_PATH", ".data/workflows.db")
)
durable_orchestrator = DurableOrchestrator(
    repository=workflow_repository,
    analysis_workflow=analysis_workflow,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/cases/validate", response_model=CaseIntake)
def validate_case(case: CaseIntake) -> CaseIntake:
    """Validate and normalize a compliance case without starting agent execution."""
    return case


@app.post("/v1/evidence/retrieve", response_model=EvidenceResponse)
def retrieve_evidence(query: EvidenceQuery) -> EvidenceResponse:
    """Return versioned policy sections with transparent retrieval scores."""
    return retriever.retrieve(query)


@app.get("/v1/policies")
def list_policies() -> dict[str, object]:
    return {
        "index_version": retriever.index_version,
        "policies": [
            {
                "policy_id": document.policy_id,
                "title": document.title,
                "version": document.version,
                "effective_date": document.effective_date,
                "status": document.status,
                "synthetic": document.synthetic,
                "section_count": len(document.sections),
            }
            for document in retriever.documents
        ],
    }


@app.post("/v1/analysis/run", response_model=ParallelAnalysisResponse)
def run_analysis(request: CaseAnalysisRequest) -> ParallelAnalysisResponse:
    """Run Legal and Policy analysis in parallel against one evidence snapshot."""
    return analysis_workflow.analyze(request.case, top_k=request.top_k)


@app.post("/v1/enforcement/evaluate", response_model=LaunchReviewResponse)
def evaluate_enforcement(request: EnforcementRequest) -> LaunchReviewResponse:
    """Run or reuse analysis, then apply versioned deterministic launch rules."""
    return launch_review_workflow.review(
        request.case,
        analysis=request.analysis,
        top_k=request.top_k,
    )


@app.post("/v1/audit/run", response_model=AuditedLaunchReview)
def run_audit(request: AuditRequest) -> AuditedLaunchReview:
    """Audit a supplied or newly generated launch review and seal its record."""
    return audited_review_workflow.review(
        request.case,
        review=request.review,
        top_k=request.top_k,
    )


@app.post("/v1/audit/verify")
def verify_audit_record(record: DecisionRecord) -> dict[str, object]:
    """Verify that a decision record still matches its canonical content hash."""
    return {
        "record_id": record.record_id,
        "case_id": record.case_id,
        "valid": verify_decision_record(record),
        "hash_algorithm": record.hash_algorithm,
    }


@app.post("/v1/workflows", response_model=WorkflowRun)
def start_workflow(request: StartWorkflowRequest) -> WorkflowRun:
    try:
        return durable_orchestrator.start(
            request.case,
            idempotency_key=request.idempotency_key,
            top_k=request.top_k,
        )
    except WorkflowConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/v1/workflows/{run_id}", response_model=WorkflowRun)
def get_workflow(run_id: str) -> WorkflowRun:
    try:
        return workflow_repository.get(run_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="workflow not found") from error


@app.get("/v1/workflows/{run_id}/events")
def get_workflow_events(run_id: str) -> dict[str, object]:
    try:
        events: list[WorkflowEvent] = workflow_repository.list_events(run_id)
        valid = workflow_repository.verify_event_chain(run_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="workflow not found") from error
    return {
        "run_id": run_id,
        "chain_valid": valid,
        "events": events,
    }


@app.post("/v1/workflows/{run_id}/resume", response_model=WorkflowRun)
def resume_workflow(run_id: str) -> WorkflowRun:
    try:
        return durable_orchestrator.resume(run_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="workflow not found") from error
    except InvalidWorkflowTransitionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/v1/workflows/{run_id}/decision", response_model=WorkflowRun)
def decide_workflow(run_id: str, request: ApprovalRequest) -> WorkflowRun:
    try:
        return durable_orchestrator.decide(run_id, request)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="workflow not found") from error
    except (InvalidWorkflowTransitionError, WorkflowConflictError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
