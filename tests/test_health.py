import json
from pathlib import Path

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
