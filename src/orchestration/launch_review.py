from src.agents.enforcement import EnforcementAgent
from src.models import CaseIntake, LaunchReviewResponse, ParallelAnalysisResponse
from src.orchestration.analysis import AnalysisWorkflow


class LaunchReviewWorkflow:
    def __init__(
        self,
        *,
        analysis_workflow: AnalysisWorkflow | None = None,
        enforcement_agent: EnforcementAgent | None = None,
    ) -> None:
        self.analysis_workflow = analysis_workflow or AnalysisWorkflow()
        self.enforcement_agent = enforcement_agent or EnforcementAgent()

    def review(
        self,
        case: CaseIntake,
        *,
        analysis: ParallelAnalysisResponse | None = None,
        top_k: int = 8,
    ) -> LaunchReviewResponse:
        resolved_analysis = analysis or self.analysis_workflow.analyze(
            case,
            top_k=top_k,
        )
        enforcement = self.enforcement_agent.enforce(case, resolved_analysis)
        return LaunchReviewResponse(
            analysis=resolved_analysis,
            enforcement=enforcement,
        )
