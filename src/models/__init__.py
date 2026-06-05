"""Shared structured data contracts."""

from src.models.analysis import (
    AgentAnalysis,
    CaseAnalysisRequest,
    ParallelAnalysisResponse,
    PolicyAnalysis,
)
from src.models.case import (
    AgeGroup,
    AIActRole,
    CaseIntake,
    DataCategory,
    DeploymentContext,
    FeatureType,
    HumanOversight,
)
from src.models.decision import (
    AgentFinding,
    AuditResult,
    Citation,
    ComplianceDecision,
    ControlRequirement,
    DecisionOutcome,
    FindingCategory,
    FindingSeverity,
)
from src.models.evidence import (
    EvidenceChunk,
    EvidenceMatch,
    EvidenceQuery,
    EvidenceResponse,
    PolicyDocument,
    PolicySection,
)

__all__ = [
    "AIActRole",
    "AgeGroup",
    "AgentAnalysis",
    "AgentFinding",
    "AuditResult",
    "CaseIntake",
    "CaseAnalysisRequest",
    "Citation",
    "ComplianceDecision",
    "ControlRequirement",
    "DataCategory",
    "DecisionOutcome",
    "DeploymentContext",
    "EvidenceChunk",
    "EvidenceMatch",
    "EvidenceQuery",
    "EvidenceResponse",
    "FeatureType",
    "FindingCategory",
    "FindingSeverity",
    "HumanOversight",
    "PolicyDocument",
    "PolicyAnalysis",
    "PolicySection",
    "ParallelAnalysisResponse",
]
