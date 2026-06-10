from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app

ROOT = Path(__file__).parents[1]
client = TestClient(app)


def test_review_console_is_served() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Compliance Review Console" in response.text
    assert 'data-testid="run-review"' in response.text
    assert 'data-testid="case-template"' in response.text


def test_frontend_assets_are_served() -> None:
    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")

    assert stylesheet.status_code == 200
    assert "--teal:" in stylesheet.text
    assert script.status_code == 200
    assert "async function runReview" in script.text


def test_demo_cases_are_available_to_console() -> None:
    response = client.get("/v1/demo/cases")

    assert response.status_code == 200
    body = response.json()
    assert len(body["cases"]) == 15
    assert body["cases"][8]["case"]["case_id"] == "CASE-009"
    assert body["cases"][8]["expected"]["outcome"] == "escalate"


def test_frontend_uses_semantic_landmarks_and_accessible_labels() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "<header" in html
    assert "<main" in html
    assert "<aside" in html
    assert 'aria-live="polite"' in html
    assert 'class="skip-link"' in html
    assert 'label for="case-template"' in html
