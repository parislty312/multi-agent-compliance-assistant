# Week 1: MVP Scope and Decision Contract

## Product Goal

Build a decision-support workflow that reviews a proposed generative AI feature
before launch and produces a traceable compliance recommendation.

The MVP is not a legal research product and does not make autonomous legal
decisions. It demonstrates how specialist agents can turn a structured product
case into evidence-backed findings, enforceable controls, and an auditable
launch recommendation.

## Initial Market and Scenario

- Primary market: United States
- Product stage: pre-launch review
- Product types: consumer and workforce-facing generative AI features
- Evidence: synthetic internal policies and public-source summaries
- Decision owner: an authorized human compliance reviewer

The schema retains an `ai_act_role` field so European Union scenarios can be
added later without redesigning the intake contract. EU legal analysis is
outside the first MVP benchmark.

## In Scope

1. Privacy and sensitive-data handling
2. Children and teen safety
3. Employment, education, financial, and health decision support
4. Generated-content safety and misuse controls
5. User transparency, notice, and appeal
6. Human oversight and escalation
7. Evidence citations and immutable decision metadata

## Out of Scope

- Legal advice or attorney replacement
- Live regulatory monitoring
- Automatic production configuration changes
- Criminal justice, military, or medical diagnosis use cases
- Training on confidential employer or customer documents
- A claim of comprehensive coverage for any jurisdiction

## Risk Tiers

| Tier | Meaning | Default handling |
| --- | --- | --- |
| Low | Limited impact with adequate safeguards | Allow |
| Medium | Material compliance gap can be remediated | Conditional allow |
| High | Sensitive or high-impact use needs expert judgment | Escalate |
| Critical | Prohibited use or severe unmitigated harm | Deny |

## Agent Ownership

### Legal Agent

- Identifies potentially applicable legal obligations
- Provides evidence and confidence
- Abstains when facts or authority are insufficient
- Never issues the final launch decision

### Policy Agent

- Maps legal and product risks to synthetic internal policies
- Detects missing or conflicting policy coverage
- Produces candidate controls

### Enforcement Agent

- Evaluates deterministic policy rules
- Returns allow, conditional allow, escalate, or deny
- Does not invent legal requirements

### Audit Agent

- Checks citation support, missing risk categories, and decision consistency
- Cannot silently alter another agent's finding
- Fails the audit or requests rerun when evidence is insufficient

### Orchestrator

- Validates intake
- Runs Legal and Policy analysis in parallel
- Passes normalized controls to Enforcement
- Runs Audit last
- Routes high-risk and uncertain cases to a human

## Acceptance Criteria

- Invalid intake data fails before agent execution.
- Every finding identifies its owner, category, severity, and confidence.
- Legal and policy claims can carry precise citations.
- Conditional approval always includes at least one verifiable control.
- Escalation always requires human approval.
- Benchmark cases contain no confidential or employer-derived content.
- The 15 Week 1 cases cover all four decision outcomes.

## Week 1 Deliverables

- Versioned intake and decision schemas
- API endpoint for intake validation
- Fifteen synthetic benchmark cases with expected outcomes
- Automated schema and benchmark tests
- Architecture and benchmark documentation

