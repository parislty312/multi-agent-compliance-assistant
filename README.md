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

Week 2 evidence foundations are implemented:

- Six versioned synthetic policies with 19 citable sections
- Strict policy, evidence chunk, query, and response schemas
- Explainable metadata and lexical retrieval baseline
- Evidence retrieval and policy inventory APIs
- Complete expected-category recall across the 15-case benchmark at Top-8

Week 3 analysis foundations are implemented:

- Parallel Legal and Policy agents sharing one evidence snapshot
- Evidence-bound findings with strict citation validation
- Abstention when required evidence is missing
- Policy-to-control mapping with ownership and verification methods
- Agent analysis API and benchmark evaluation

See [Week 1 scope](docs/week-1-scope.md) and
[Week 3 Legal and Policy agents](docs/week-3-legal-policy-agents.md).

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
Retrieve versioned evidence with `POST /v1/evidence/retrieve`.
Run parallel analysis with `POST /v1/analysis/run`.

Run the deterministic retrieval benchmark:

```bash
python scripts/evaluate_retrieval.py
python scripts/evaluate_agents.py
```
