from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.main import app
from src.workflow import SQLiteWorkflowRepository

client = TestClient(app)


@pytest.fixture(autouse=True)
def restore_settings():
    original = app.state.settings
    yield
    app.state.settings = original


def test_settings_require_api_key_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("COMPLIANCE_API_KEY", raising=False)

    with pytest.raises(ValueError, match="COMPLIANCE_API_KEY"):
        Settings.from_env()


def test_api_key_protects_operational_endpoints() -> None:
    app.state.settings = replace(app.state.settings, api_key="week-eight-secret")

    unauthorized = client.get("/v1/policies")
    authorized = client.get(
        "/v1/policies",
        headers={"Authorization": "Bearer week-eight-secret"},
    )
    demo = client.get("/v1/demo/cases")

    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"] == "Bearer"
    assert authorized.status_code == 200
    assert demo.status_code == 200


def test_request_size_limit_is_enforced() -> None:
    app.state.settings = replace(app.state.settings, max_request_bytes=10)

    response = client.post(
        "/v1/cases/validate",
        content=b'{"payload":"too large"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "request body exceeds configured size limit"


def test_security_headers_and_request_id_are_returned() -> None:
    response = client.get(
        "/health/live",
        headers={"X-Request-ID": "week8-test-request"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "week8-test-request"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_readiness_checks_dependencies() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "workflow_database": True,
            "policy_index": True,
        },
    }


def test_metrics_use_route_templates_not_workflow_ids() -> None:
    client.get("/health/live")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "compliance_http_requests_total" in response.text
    assert 'route="/health/live"' in response.text


def test_repository_healthcheck_reports_unavailable_database(
    tmp_path,
) -> None:
    repository = SQLiteWorkflowRepository(tmp_path / "healthy.db")
    assert repository.healthcheck()

    repository.path = tmp_path / "missing" / "unavailable.db"
    assert not repository.healthcheck()
