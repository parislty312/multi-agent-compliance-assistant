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
