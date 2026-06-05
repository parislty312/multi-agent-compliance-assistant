from fastapi import FastAPI

from src.audit import verify_decision_record
from src.knowledge import PolicyRetriever
from src.models import (
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
)
from src.orchestration import (
    AnalysisWorkflow,
    AuditedReviewWorkflow,
    LaunchReviewWorkflow,
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
