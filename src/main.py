from fastapi import FastAPI

app = FastAPI(
    title="Multi-Agent Compliance Assistant",
    description="Auditable compliance decision support for AI product launches.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

