from pydantic import Field, model_validator

from src.models.case import CaseIntake, StrictModel
from src.models.decision import AgentFinding, ControlRequirement, FindingCategory
from src.models.evidence import EvidenceResponse


class AgentAnalysis(StrictModel):
    agent: str = Field(pattern=r"^(legal|policy)$")
    case_id: str = Field(pattern=r"^CASE-\d{3}$")
    summary: str = Field(min_length=10, max_length=1000)
    findings: list[AgentFinding]
    open_questions: list[str] = Field(default_factory=list)
    abstained_categories: list[FindingCategory] = Field(default_factory=list)
    evidence_index_version: str = Field(min_length=1)


class PolicyAnalysis(AgentAnalysis):
    agent: str = Field(default="policy", pattern=r"^policy$")
    controls: list[ControlRequirement] = Field(default_factory=list)

    @model_validator(mode="after")
    def controls_reference_findings(self) -> "PolicyAnalysis":
        finding_ids = {finding.finding_id for finding in self.findings}
        for control in self.controls:
            if not set(control.source_finding_ids) <= finding_ids:
                raise ValueError("controls must reference findings from the same analysis")
        return self


class CaseAnalysisRequest(StrictModel):
    case: CaseIntake
    top_k: int = Field(default=8, ge=1, le=25)


class ParallelAnalysisResponse(StrictModel):
    case_id: str = Field(pattern=r"^CASE-\d{3}$")
    evidence: EvidenceResponse
    legal: AgentAnalysis
    policy: PolicyAnalysis

