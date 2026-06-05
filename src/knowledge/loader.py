import json
from pathlib import Path

from src.models import EvidenceChunk, PolicyDocument

DEFAULT_POLICY_DIR = Path(__file__).parents[2] / "policies"


def load_policy_documents(policy_dir: Path = DEFAULT_POLICY_DIR) -> list[PolicyDocument]:
    documents: list[PolicyDocument] = []
    for path in sorted(policy_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        documents.append(PolicyDocument.model_validate(payload))
    if not documents:
        raise ValueError(f"no policy documents found in {policy_dir}")
    return documents


def build_evidence_chunks(documents: list[PolicyDocument]) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    seen_ids: set[str] = set()
    for document in documents:
        if document.status != "active":
            continue
        for section in document.sections:
            chunk_id = f"{document.policy_id}:{document.version}:{section.section_id}"
            if chunk_id in seen_ids:
                raise ValueError(f"duplicate evidence chunk id: {chunk_id}")
            seen_ids.add(chunk_id)
            chunks.append(
                EvidenceChunk(
                    chunk_id=chunk_id,
                    policy_id=document.policy_id,
                    policy_title=document.title,
                    policy_version=document.version,
                    effective_date=document.effective_date,
                    source_type=document.source_type,
                    synthetic=document.synthetic,
                    section_id=section.section_id,
                    section_title=section.title,
                    text=section.text,
                    categories=section.categories,
                    jurisdictions=section.jurisdictions,
                    feature_types=section.feature_types,
                    data_categories=section.data_categories,
                    age_groups=section.age_groups,
                    decision_domains=section.decision_domains,
                    keywords=section.keywords,
                    control_ids=section.control_ids,
                )
            )
    return chunks

