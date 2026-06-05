from fastapi import FastAPI

from src.models import CaseIntake

app = FastAPI(
    title="Multi-Agent Compliance Assistant",
    description="Auditable compliance decision support for AI product launches.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/cases/validate", response_model=CaseIntake)
def validate_case(case: CaseIntake) -> CaseIntake:
    """Validate and normalize a compliance case without starting agent execution."""
    return case
