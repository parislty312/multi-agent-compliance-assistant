from datetime import date

from pydantic import Field, model_validator

from src.models.case import AgeGroup, CaseIntake, DataCategory, FeatureType, StrictModel
from src.models.decision import FindingCategory


class PolicySection(StrictModel):
    section_id: str = Field(pattern=r"^[A-Z]+-\d+\.\d+$")
    title: str = Field(min_length=5, max_length=150)
    text: str = Field(min_length=20, max_length=3000)
    categories: list[FindingCategory] = Field(min_length=1)
    jurisdictions: list[str] = Field(min_length=1)
    feature_types: list[FeatureType] = Field(default_factory=list)
    data_categories: list[DataCategory] = Field(default_factory=list)
    age_groups: list[AgeGroup] = Field(default_factory=list)
    decision_domains: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    control_ids: list[str] = Field(default_factory=list)


class PolicyDocument(StrictModel):
    policy_id: str = Field(pattern=r"^POL-[A-Z]+-\d{3}$")
    title: str = Field(min_length=5, max_length=150)
    version: str = Field(min_length=1, max_length=30)
    effective_date: date
    status: str = Field(pattern=r"^(active|draft|retired)$")
    source_type: str = Field(pattern=r"^(synthetic_internal_policy|public_summary)$")
    synthetic: bool
    owner: str = Field(min_length=2, max_length=100)
    sections: list[PolicySection] = Field(min_length=1)

    @model_validator(mode="after")
    def require_synthetic_flag(self) -> "PolicyDocument":
        if self.source_type == "synthetic_internal_policy" and not self.synthetic:
            raise ValueError("synthetic internal policies must set synthetic=true")
        return self


class EvidenceChunk(StrictModel):
    chunk_id: str
    policy_id: str
    policy_title: str
    policy_version: str
    effective_date: date
    source_type: str
    synthetic: bool
    section_id: str
    section_title: str
    text: str
    categories: list[FindingCategory]
    jurisdictions: list[str]
    feature_types: list[FeatureType]
    data_categories: list[DataCategory]
    age_groups: list[AgeGroup]
    decision_domains: list[str]
    keywords: list[str]
    control_ids: list[str]


class EvidenceQuery(StrictModel):
    query_text: str = Field(default="", max_length=2000)
    case: CaseIntake | None = None
    categories: list[FindingCategory] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=1, le=25)

    @model_validator(mode="after")
    def require_search_context(self) -> "EvidenceQuery":
        if not self.query_text and self.case is None and not self.categories:
            raise ValueError("query_text, case, or categories must be provided")
        return self


class EvidenceMatch(StrictModel):
    chunk: EvidenceChunk
    score: float = Field(ge=0)
    matched_on: list[str]


class EvidenceResponse(StrictModel):
    query: str
    index_version: str
    total_candidates: int
    matches: list[EvidenceMatch]

