import hashlib
import json
from datetime import UTC, datetime

from src.models import (
    AuditReport,
    CaseIntake,
    DecisionRecord,
    LaunchReviewResponse,
)


def canonical_record_payload(
    *,
    case: CaseIntake,
    review: LaunchReviewResponse,
    audit: AuditReport,
    created_at: datetime,
) -> bytes:
    payload = {
        "case": case.model_dump(mode="json"),
        "review": review.model_dump(mode="json"),
        "audit": audit.model_dump(mode="json"),
        "created_at": created_at.isoformat(),
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def build_decision_record(
    *,
    case: CaseIntake,
    review: LaunchReviewResponse,
    audit: AuditReport,
    created_at: datetime | None = None,
) -> DecisionRecord:
    timestamp = created_at or datetime.now(UTC)
    content_hash = hashlib.sha256(
        canonical_record_payload(
            case=case,
            review=review,
            audit=audit,
            created_at=timestamp,
        )
    ).hexdigest()
    return DecisionRecord(
        record_id=f"REC-{content_hash[:16].upper()}",
        case_id=case.case_id,
        case=case,
        review=review,
        audit=audit,
        content_hash=content_hash,
        created_at=timestamp,
    )


def verify_decision_record(record: DecisionRecord) -> bool:
    expected = hashlib.sha256(
        canonical_record_payload(
            case=record.case,
            review=record.review,
            audit=record.audit,
            created_at=record.created_at,
        )
    ).hexdigest()
    return all(
        [
            record.hash_algorithm == "sha256",
            record.content_hash == expected,
            record.record_id == f"REC-{expected[:16].upper()}",
            record.case_id == record.case.case_id,
            record.case_id == record.review.analysis.case_id,
            record.case_id == record.review.enforcement.case_id,
            record.case_id == record.audit.case_id,
        ]
    )
