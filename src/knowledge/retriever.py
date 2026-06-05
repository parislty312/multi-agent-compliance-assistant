import re
from collections.abc import Iterable
from pathlib import Path

from src.knowledge.loader import (
    DEFAULT_POLICY_DIR,
    build_evidence_chunks,
    load_policy_documents,
)
from src.models import (
    EvidenceChunk,
    EvidenceMatch,
    EvidenceQuery,
    EvidenceResponse,
    FindingCategory,
)

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "using",
    "with",
}


def tokenize(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.lower())) - STOP_WORDS


def normalize_values(values: Iterable[object]) -> set[str]:
    return {str(value).lower().strip() for value in values if str(value).strip()}


class PolicyRetriever:
    def __init__(self, policy_dir: Path = DEFAULT_POLICY_DIR) -> None:
        self.documents = load_policy_documents(policy_dir)
        self.chunks = build_evidence_chunks(self.documents)
        versions = sorted({f"{doc.policy_id}@{doc.version}" for doc in self.documents})
        self.index_version = "|".join(versions)

    def retrieve(self, request: EvidenceQuery) -> EvidenceResponse:
        query_text = self._build_query_text(request)
        query_tokens = tokenize(query_text)
        requested_categories = set(request.categories)
        requested_jurisdictions = normalize_values(request.jurisdictions)

        case = request.case
        if case:
            requested_jurisdictions.update(
                market.lower() for market in case.deployment.target_markets
            )

        scored: list[EvidenceMatch] = []
        for chunk in self.chunks:
            score, matched_on = self._score_chunk(
                chunk=chunk,
                query_tokens=query_tokens,
                requested_categories=requested_categories,
                requested_jurisdictions=requested_jurisdictions,
                request=request,
            )
            if score > 0:
                scored.append(
                    EvidenceMatch(chunk=chunk, score=round(score, 3), matched_on=matched_on)
                )

        scored.sort(key=lambda item: (-item.score, item.chunk.chunk_id))
        matches = self._select_with_category_coverage(
            scored=scored,
            required_categories=self._required_categories(request),
            top_k=request.top_k,
        )
        return EvidenceResponse(
            query=query_text,
            index_version=self.index_version,
            total_candidates=len(self.chunks),
            matches=matches,
        )

    def _score_chunk(
        self,
        *,
        chunk: EvidenceChunk,
        query_tokens: set[str],
        requested_categories: set[FindingCategory],
        requested_jurisdictions: set[str],
        request: EvidenceQuery,
    ) -> tuple[float, list[str]]:
        score = 0.0
        matched_on: list[str] = []
        chunk_tokens = tokenize(
            " ".join(
                [
                    chunk.policy_title,
                    chunk.section_title,
                    chunk.text,
                    *chunk.keywords,
                    *chunk.decision_domains,
                ]
            )
        )
        lexical_overlap = query_tokens & chunk_tokens
        if lexical_overlap:
            score += min(len(lexical_overlap), 8) * 0.75
            matched_on.append(f"terms:{','.join(sorted(lexical_overlap)[:6])}")

        keyword_tokens = set().union(*(tokenize(keyword) for keyword in chunk.keywords))
        keyword_overlap = query_tokens & keyword_tokens
        if keyword_overlap:
            score += min(len(keyword_overlap), 5) * 1.5
            matched_on.append(f"keywords:{','.join(sorted(keyword_overlap)[:5])}")

        category_overlap = requested_categories & set(chunk.categories)
        if category_overlap:
            score += len(category_overlap) * 6
            matched_on.append(
                f"categories:{','.join(sorted(category.value for category in category_overlap))}"
            )

        chunk_jurisdictions = normalize_values(chunk.jurisdictions)
        if requested_jurisdictions and (
            requested_jurisdictions & chunk_jurisdictions or "global" in chunk_jurisdictions
        ):
            score += 1.5
            matched_on.append("jurisdiction")

        case = request.case
        if case:
            if case.feature_type in chunk.feature_types:
                score += 2
                matched_on.append("feature_type")

            data_overlap = set(case.data_categories) & set(chunk.data_categories)
            if data_overlap:
                score += len(data_overlap) * 2.5
                matched_on.append(
                    f"data:{','.join(sorted(category.value for category in data_overlap))}"
                )

            age_overlap = set(case.affected_age_groups) & set(chunk.age_groups)
            if age_overlap:
                score += len(age_overlap) * 3
                matched_on.append(
                    f"age:{','.join(sorted(age.value for age in age_overlap))}"
                )

            domain = (case.decision_domain or "").lower()
            if domain and any(term.lower() in domain for term in chunk.decision_domains):
                score += 5
                matched_on.append("decision_domain")

            if case.automated_decision and FindingCategory.HIGH_IMPACT_DECISION in chunk.categories:
                score += 4
                matched_on.append("automated_decision")

            if not case.user_notice_present and FindingCategory.TRANSPARENCY in chunk.categories:
                score += 3
                matched_on.append("missing_notice")

            if (
                not case.safety_evaluation_complete
                and FindingCategory.GOVERNANCE in chunk.categories
            ):
                score += 3
                matched_on.append("missing_evaluation")

            if (
                not case.human_oversight.enabled
                and FindingCategory.HIGH_IMPACT_DECISION in chunk.categories
            ):
                score += 4
                matched_on.append("missing_human_oversight")

        return score, matched_on

    def _required_categories(self, request: EvidenceQuery) -> set[FindingCategory]:
        categories = set(request.categories)
        case = request.case
        if not case:
            return categories
        if case.data_categories:
            categories.add(FindingCategory.PRIVACY)
        if any(age.value in {"under_13", "teen_13_to_17", "all_ages"} for age in case.affected_age_groups):
            categories.add(FindingCategory.CHILD_SAFETY)
        if case.automated_decision:
            categories.add(FindingCategory.HIGH_IMPACT_DECISION)
        if not case.user_notice_present:
            categories.add(FindingCategory.TRANSPARENCY)
        if not case.safety_evaluation_complete:
            categories.add(FindingCategory.GOVERNANCE)
        if case.feature_type.value in {"chatbot", "content_generation", "content_moderation"}:
            categories.add(FindingCategory.CONTENT_SAFETY)
        return categories

    @staticmethod
    def _select_with_category_coverage(
        *,
        scored: list[EvidenceMatch],
        required_categories: set[FindingCategory],
        top_k: int,
    ) -> list[EvidenceMatch]:
        selected: list[EvidenceMatch] = []
        selected_ids: set[str] = set()

        for category in sorted(required_categories, key=lambda item: item.value):
            match = next(
                (
                    item
                    for item in scored
                    if category in item.chunk.categories
                    and item.chunk.chunk_id not in selected_ids
                ),
                None,
            )
            if match:
                selected.append(match)
                selected_ids.add(match.chunk.chunk_id)
            if len(selected) == top_k:
                return sorted(selected, key=lambda item: (-item.score, item.chunk.chunk_id))

        for item in scored:
            if item.chunk.chunk_id not in selected_ids:
                selected.append(item)
                selected_ids.add(item.chunk.chunk_id)
            if len(selected) == top_k:
                break
        return sorted(selected, key=lambda item: (-item.score, item.chunk.chunk_id))

    @staticmethod
    def _build_query_text(request: EvidenceQuery) -> str:
        parts = [request.query_text]
        if request.case:
            case = request.case
            parts.extend(
                [
                    case.title,
                    case.summary,
                    case.intended_use,
                    case.decision_domain or "",
                    " ".join(case.known_limitations),
                    " ".join(case.open_questions),
                ]
            )
        return " ".join(part for part in parts if part).strip()
