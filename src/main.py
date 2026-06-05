from fastapi import FastAPI

from src.knowledge import PolicyRetriever
from src.models import (
    CaseAnalysisRequest,
    CaseIntake,
    EvidenceQuery,
    EvidenceResponse,
    EnforcementRequest,
    LaunchReviewResponse,
    ParallelAnalysisResponse,
)
from src.orchestration import AnalysisWorkflow, LaunchReviewWorkflow

app = FastAPI(
    title="Multi-Agent Compliance Assistant",
    description="Auditable compliance decision support for AI product launches.",
    version="0.1.0",
)
retriever = PolicyRetriever()
analysis_workflow = AnalysisWorkflow(retriever=retriever)
launch_review_workflow = LaunchReviewWorkflow(analysis_workflow=analysis_workflow)


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
