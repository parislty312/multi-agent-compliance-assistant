import hmac
import json
import logging
import re
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.audit import verify_decision_record
from src.config import Settings
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
from src.operations import RuntimeMetrics, log_access
from src.workflow import (
    SQLiteWorkflowRepository,
    WorkflowConflictError,
    WorkflowNotFoundError,
)

settings = Settings.from_env()
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(message)s",
)
access_logger = logging.getLogger("compliance.access")
app = FastAPI(
    title="Multi-Agent Compliance Assistant",
    description="Auditable compliance decision support for AI product launches.",
    version="0.2.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.state.settings = settings
app.state.metrics = RuntimeMetrics()
retriever = PolicyRetriever()
analysis_workflow = AnalysisWorkflow(retriever=retriever)
launch_review_workflow = LaunchReviewWorkflow(analysis_workflow=analysis_workflow)
audited_review_workflow = AuditedReviewWorkflow(
    launch_review_workflow=launch_review_workflow
)
workflow_repository = SQLiteWorkflowRepository(
    settings.workflow_db_path
)
durable_orchestrator = DurableOrchestrator(
    repository=workflow_repository,
    analysis_workflow=analysis_workflow,
)
project_root = Path(__file__).parents[1]
frontend_dir = project_root / "frontend"
benchmark_path = project_root / "benchmarks" / "cases" / "week_1_cases.json"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
request_id_pattern = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


@app.middleware("http")
async def operational_controls(request: Request, call_next):
    started = time.perf_counter()
    configured: Settings = request.app.state.settings
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if request_id_pattern.fullmatch(supplied_request_id)
        else uuid4().hex
    )
    status_code = 500

    content_length = request.headers.get("content-length")
    request_too_large = (
        content_length is not None
        and content_length.isdigit()
        and int(content_length) > configured.max_request_bytes
    )
    try:
        if request_too_large:
            response = JSONResponse(
                status_code=413,
                content={"detail": "request body exceeds configured size limit"},
            )
            status_code = response.status_code
        elif _requires_api_key(request.url.path) and configured.api_key:
            supplied_key = _extract_api_key(request)
            if not supplied_key or not hmac.compare_digest(
                supplied_key,
                configured.api_key,
            ):
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "valid API key required"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
                status_code = response.status_code
            else:
                response = await call_next(request)
                status_code = response.status_code
        else:
            response = await call_next(request)
            status_code = response.status_code
    except Exception:
        access_logger.exception(
            json.dumps(
                {
                    "event": "unhandled_request_error",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
                sort_keys=True,
            )
        )
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "internal server error",
                "request_id": request_id,
            },
        )
        status_code = response.status_code

    duration = time.perf_counter() - started
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    request.app.state.metrics.record(
        method=request.method,
        route=route_path,
        status_code=status_code,
        duration_seconds=duration,
    )
    log_access(
        access_logger,
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        duration_ms=duration * 1000,
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/v1/") else "no-cache"
    )
    response.headers["Content-Security-Policy"] = _content_security_policy(
        request.url.path
    )
    return response


def _requires_api_key(path: str) -> bool:
    return (
        (path.startswith("/v1/") and path != "/v1/demo/cases")
        or path == "/metrics"
    )


def _extract_api_key(request: Request) -> str | None:
    direct = request.headers.get("X-API-Key")
    if direct:
        return direct
    authorization = request.headers.get("Authorization", "")
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() == "bearer" and credential:
        return credential
    return None


def _content_security_policy(path: str) -> str:
    if path in {"/docs", "/redoc"}:
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
            "https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "frame-ancestors 'none'"
        )
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )


@app.get("/", include_in_schema=False)
def review_console() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> JSONResponse:
    checks = {
        "workflow_database": workflow_repository.healthcheck(),
        "policy_index": bool(retriever.documents),
    }
    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": checks,
        },
    )


@app.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request) -> str:
    return request.app.state.metrics.render_prometheus()


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


@app.get("/v1/demo/cases")
def list_demo_cases(request: Request) -> dict[str, object]:
    benchmarks = json.loads(benchmark_path.read_text(encoding="utf-8"))
    return {
        "docs_enabled": request.app.state.settings.docs_enabled,
        "cases": [
            {
                "case": item["case"],
                "expected": item["expected"],
                "rationale": item["rationale"],
            }
            for item in benchmarks
        ]
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
