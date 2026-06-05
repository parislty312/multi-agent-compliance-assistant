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

The repository is in its initial architecture phase. The next milestone is to
define the case intake schema, agent output contracts, and a benchmark set of
synthetic compliance scenarios.

## Safety

This project is a decision-support prototype and does not provide legal advice.
Examples must use public or synthetic policies and must not contain confidential
employer or customer information.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

