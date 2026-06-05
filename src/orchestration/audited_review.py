from src.agents.audit import AuditAgent
from src.audit import build_decision_record
from src.models import (
    AuditedLaunchReview,
    CaseIntake,
    LaunchReviewResponse,
)
from src.orchestration.launch_review import LaunchReviewWorkflow


class AuditedReviewWorkflow:
    def __init__(
        self,
        *,
        launch_review_workflow: LaunchReviewWorkflow | None = None,
        audit_agent: AuditAgent | None = None,
    ) -> None:
        self.launch_review_workflow = (
            launch_review_workflow or LaunchReviewWorkflow()
        )
        self.audit_agent = audit_agent or AuditAgent()

    def review(
        self,
        case: CaseIntake,
        *,
        review: LaunchReviewResponse | None = None,
        top_k: int = 8,
    ) -> AuditedLaunchReview:
        resolved_review = review or self.launch_review_workflow.review(
            case,
            top_k=top_k,
        )
        audit = self.audit_agent.audit(case, resolved_review)
        record = build_decision_record(
            case=case,
            review=resolved_review,
            audit=audit,
        )
        return AuditedLaunchReview(
            review=resolved_review,
            audit=audit,
            record=record,
        )
