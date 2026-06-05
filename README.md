# Multi-Agent Compliance Assistant

An auditable compliance decision system for reviewing AI product launches.

The project coordinates specialist agents for legal analysis, policy mapping,
control enforcement, and independent audit. It is designed to demonstrate
reliable multi-agent orchestration rather than unrestricted agent conversation.

## Agents

- **Legal Agent** identifies applicable legal obligations and unresolved questions.
- **Policy Agent** maps obligations to internal policies and required controls.
- **Enforcement Agent** evaluates controls and returns allow, deny, conditional
  approval, or human escalation decisions.
- **Audit Agent** independently checks evidence, consistency, and decision quality.
- **Orchestrator** manages the workflow and human-review boundary.

## Initial Scope

The first use case is an AI feature launch review. A product team submits a
feature description, target markets, data usage, model behavior, and existing
safeguards. The system produces a structured decision with supporting evidence,
required controls, open questions, and an audit trail.

## Planned Stack

- Python 3.12
- FastAPI
- Pydantic
- OpenAI Agents SDK
- PostgreSQL and pgvector
- Open Policy Agent
- pytest

## Project Status

Week 1 foundations are implemented:

- Strict case intake and compliance decision schemas
- Explicit Legal, Policy, Enforcement, Audit, and Orchestrator ownership
- Four decision outcomes and a six-category risk taxonomy
- Fifteen synthetic launch-review benchmark cases
- API-level intake validation
- Automated schema and benchmark acceptance tests

See [Week 1 scope](docs/week-1-scope.md) and
[benchmark documentation](benchmarks/README.md).

## Safety

This project is a decision-support prototype and does not provide legal advice.
Examples must use public or synthetic policies and must not contain confidential
employer or customer information.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Start the API:

```bash
uvicorn src.main:app --reload
```

Validate an intake payload with `POST /v1/cases/validate`.
