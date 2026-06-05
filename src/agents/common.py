from collections.abc import Iterable

from src.models import (
    AgentFinding,
    Citation,
    EvidenceMatch,
    EvidenceResponse,
    FindingCategory,
)


def evidence_by_category(
    evidence: EvidenceResponse,
    categories: Iterable[FindingCategory],
) -> dict[FindingCategory, EvidenceMatch]:
    matches: dict[FindingCategory, EvidenceMatch] = {}
    for category in categories:
        match = next(
            (
                candidate
                for candidate in evidence.matches
                if category in candidate.chunk.categories
            ),
            None,
        )
        if match:
            matches[category] = match
    return matches


def citation_from_match(match: EvidenceMatch) -> Citation:
    return Citation(
        source_id=f"{match.chunk.policy_id}@{match.chunk.policy_version}",
        section=match.chunk.section_id,
        excerpt=match.chunk.text,
    )


def validate_finding_citations(
    findings: list[AgentFinding],
    evidence: EvidenceResponse,
) -> None:
    allowed = {
        (
            f"{match.chunk.policy_id}@{match.chunk.policy_version}",
            match.chunk.section_id,
            match.chunk.text,
        )
        for match in evidence.matches
    }
    for finding in findings:
        if not finding.citations:
            raise ValueError(f"finding {finding.finding_id} has no citation")
        for citation in finding.citations:
            key = (citation.source_id, citation.section, citation.excerpt)
            if key not in allowed:
                raise ValueError(
                    f"finding {finding.finding_id} cites evidence outside the response"
                )

