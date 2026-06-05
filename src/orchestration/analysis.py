from concurrent.futures import ThreadPoolExecutor

from src.agents.legal import LegalAgent
from src.agents.policy import PolicyAgent
from src.knowledge import PolicyRetriever
from src.models import (
    CaseIntake,
    EvidenceQuery,
    ParallelAnalysisResponse,
)


class AnalysisWorkflow:
    def __init__(
        self,
        *,
        retriever: PolicyRetriever | None = None,
        legal_agent: LegalAgent | None = None,
        policy_agent: PolicyAgent | None = None,
    ) -> None:
        self.retriever = retriever or PolicyRetriever()
        self.legal_agent = legal_agent or LegalAgent()
        self.policy_agent = policy_agent or PolicyAgent()

    def analyze(self, case: CaseIntake, *, top_k: int = 8) -> ParallelAnalysisResponse:
        evidence = self.retriever.retrieve(EvidenceQuery(case=case, top_k=top_k))
        with ThreadPoolExecutor(max_workers=2) as executor:
            legal_future = executor.submit(self.legal_agent.analyze, case, evidence)
            policy_future = executor.submit(self.policy_agent.analyze, case, evidence)
            legal = legal_future.result()
            policy = policy_future.result()

        return ParallelAnalysisResponse(
            case_id=case.case_id,
            evidence=evidence,
            legal=legal,
            policy=policy,
        )
