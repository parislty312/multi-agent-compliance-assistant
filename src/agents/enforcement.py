"""Deterministic control enforcement agent."""

from src.enforcement import EnforcementEngine, load_enforcement_ruleset
from src.models import CaseIntake, EnforcementResult, ParallelAnalysisResponse


class EnforcementAgent:
    def __init__(self, engine: EnforcementEngine | None = None) -> None:
        self.engine = engine or EnforcementEngine(load_enforcement_ruleset())

    def enforce(
        self,
        case: CaseIntake,
        analysis: ParallelAnalysisResponse,
    ) -> EnforcementResult:
        return self.engine.evaluate(case, analysis)
