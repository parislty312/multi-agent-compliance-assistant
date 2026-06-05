from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FeatureType(StrEnum):
    CHATBOT = "chatbot"
    CONTENT_GENERATION = "content_generation"
    CONTENT_MODERATION = "content_moderation"
    DECISION_SUPPORT = "decision_support"
    IDENTITY_VERIFICATION = "identity_verification"
    PERSONALIZATION = "personalization"


class DataCategory(StrEnum):
    PUBLIC = "public"
    ACCOUNT = "account"
    CONTACT = "contact"
    PRECISE_LOCATION = "precise_location"
    BIOMETRIC = "biometric"
    HEALTH = "health"
    FINANCIAL = "financial"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    USER_CONTENT = "user_content"
    MINOR_DATA = "minor_data"


class AgeGroup(StrEnum):
    UNDER_13 = "under_13"
    TEEN_13_TO_17 = "teen_13_to_17"
    ADULT = "adult"
    ALL_AGES = "all_ages"


class AIActRole(StrEnum):
    PROVIDER = "provider"
    DEPLOYER = "deployer"
    BOTH = "both"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class HumanOversight(StrictModel):
    enabled: bool
    reviewer_role: str | None = None
    review_trigger: str | None = None
    user_appeal_available: bool = False

    @model_validator(mode="after")
    def require_review_details_when_enabled(self) -> "HumanOversight":
        if self.enabled and (not self.reviewer_role or not self.review_trigger):
            raise ValueError(
                "reviewer_role and review_trigger are required when human oversight is enabled"
            )
        return self


class DeploymentContext(StrictModel):
    target_markets: list[str] = Field(min_length=1)
    ai_act_role: AIActRole = AIActRole.UNKNOWN
    external_users: bool = True
    launch_stage: str = Field(default="pre_launch", min_length=1)


class CaseIntake(StrictModel):
    case_id: str = Field(pattern=r"^CASE-\d{3}$")
    title: str = Field(min_length=5, max_length=120)
    summary: str = Field(min_length=20, max_length=2000)
    business_owner: str = Field(min_length=2, max_length=100)
    feature_type: FeatureType
    intended_use: str = Field(min_length=20, max_length=1000)
    prohibited_uses: list[str] = Field(default_factory=list)
    deployment: DeploymentContext
    affected_age_groups: list[AgeGroup] = Field(min_length=1)
    data_categories: list[DataCategory] = Field(min_length=1)
    automated_decision: bool
    decision_domain: str | None = None
    model_provider: str = Field(min_length=2, max_length=100)
    model_name: str = Field(min_length=2, max_length=100)
    model_outputs: list[str] = Field(min_length=1)
    human_oversight: HumanOversight
    retention_days: int | None = Field(default=None, ge=0, le=3650)
    user_notice_present: bool
    safety_evaluation_complete: bool
    known_limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_risk_context(self) -> "CaseIntake":
        if self.automated_decision and not self.decision_domain:
            raise ValueError("decision_domain is required for automated decisions")
        if DataCategory.MINOR_DATA in self.data_categories and not any(
            age in self.affected_age_groups
            for age in (AgeGroup.UNDER_13, AgeGroup.TEEN_13_TO_17, AgeGroup.ALL_AGES)
        ):
            raise ValueError("minor_data requires a minor or all-ages audience")
        return self

