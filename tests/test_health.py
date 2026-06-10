import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validate_case_accepts_benchmark_payload() -> None:
    benchmark_path = (
        Path(__file__).parents[1] / "benchmarks" / "cases" / "week_1_cases.json"
    )
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))[0]["case"]

    response = client.post("/v1/cases/validate", json=payload)

    assert response.status_code == 200
    assert response.json()["case_id"] == "CASE-001"


def test_retrieve_evidence_for_benchmark_case() -> None:
    benchmark_path = (
        Path(__file__).parents[1] / "benchmarks" / "cases" / "week_1_cases.json"
    )
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))[8]["case"]

    response = client.post(
        "/v1/evidence/retrieve",
        json={"case": payload, "top_k": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["matches"]
    assert body["matches"][0]["chunk"]["section_id"] == "HIGH-1.1"
    assert body["index_version"]


def test_list_policies_exposes_version_metadata() -> None:
    response = client.get("/v1/policies")

    assert response.status_code == 200
    body = response.json()
    assert len(body["policies"]) == 6
    assert all(policy["synthetic"] for policy in body["policies"])
    assert all(policy["version"] == "1.0.0" for policy in body["policies"])


def test_run_parallel_analysis() -> None:
    benchmark_path = (
        Path(__file__).parents[1] / "benchmarks" / "cases" / "week_1_cases.json"
    )
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))[9]["case"]

    response = client.post(
        "/v1/analysis/run",
        json={"case": payload, "top_k": 8},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "CASE-010"
    assert body["legal"]["findings"]
    assert body["policy"]["findings"]
    assert body["policy"]["controls"]


def test_evaluate_enforcement() -> None:
    benchmark_path = (
        Path(__file__).parents[1] / "benchmarks" / "cases" / "week_1_cases.json"
    )
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))[14]["case"]

    response = client.post(
        "/v1/enforcement/evaluate",
        json={"case": payload, "top_k": 8},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enforcement"]["outcome"] == "deny"
    assert body["enforcement"]["winning_rule_id"] == "RULE-DENY-002"
    assert body["enforcement"]["ruleset_version"] == "1.0.0"
    assert body["enforcement"]["rule_trace"]


def test_run_audit_and_create_record() -> None:
    benchmark_path = (
        Path(__file__).parents[1] / "benchmarks" / "cases" / "week_1_cases.json"
    )
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))[8]["case"]

    response = client.post(
        "/v1/audit/run",
        json={"case": payload, "top_k": 8},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["audit"]["verdict"] == "pass"
    assert len(body["audit"]["checks"]) == 8
    assert body["record"]["hash_algorithm"] == "sha256"
    assert len(body["record"]["content_hash"]) == 64

    verify_response = client.post("/v1/audit/verify", json=body["record"])
    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] is True


def test_durable_workflow_api_and_human_decision() -> None:
    benchmark_path = (
        Path(__file__).parents[1] / "benchmarks" / "cases" / "week_1_cases.json"
    )
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))[8]["case"]
    key = f"api-workflow-{uuid4().hex}"

    start_response = client.post(
        "/v1/workflows",
        json={"case": payload, "idempotency_key": key, "top_k": 8},
    )

    assert start_response.status_code == 200
    run = start_response.json()
    assert run["status"] == "awaiting_approval"

    get_response = client.get(f"/v1/workflows/{run['run_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["version"] == run["version"]

    events_response = client.get(f"/v1/workflows/{run['run_id']}/events")
    assert events_response.status_code == 200
    assert events_response.json()["chain_valid"] is True
    assert events_response.json()["events"]

    decision_response = client.post(
        f"/v1/workflows/{run['run_id']}/decision",
        json={
            "action": "approve",
            "reviewer": "API Compliance Reviewer",
            "rationale": "The specialist review supports the documented escalation.",
        },
    )

    assert decision_response.status_code == 200
    decided = decision_response.json()
    assert decided["status"] == "completed"
    assert decided["final_outcome"] == "escalate"
