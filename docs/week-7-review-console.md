# Week 7: Compliance Review Console

## Goal

Make the multi-agent workflow understandable and operable by product,
compliance, legal, and audit reviewers without requiring direct API calls.

The console is served by FastAPI at `/` and uses the existing durable workflow
APIs. It has no separate build tool or JavaScript framework.

## Information Architecture

### Case Intake

- Select one of 15 synthetic benchmark scenarios
- Review owner, feature type, market, and expected benchmark outcome
- Inspect or edit the complete `CaseIntake` JSON
- Submit the case with a fresh idempotency key

### Decision Workspace

- Workflow status and final or proposed outcome
- Risk level
- Legal and Policy finding counts
- Required control and Audit check counts
- Winning rule, ruleset version, evidence index, record ID, and content hash

### Detail Views

1. **Overview**: decision basis, versions, and unresolved questions
2. **Agent findings**: Legal and Policy analysis with exact citations
3. **Evidence**: retrieved policy sections and scoring reasons
4. **Controls**: blocking remediation requirements and verification methods
5. **Audit**: eight independent Audit Agent checks
6. **Timeline**: durable workflow events and hash-chain status

### Human Review

When a workflow reaches `awaiting_approval`, the console provides:

- Approve original outcome
- Reject and set final outcome to deny
- Override to conditional approval
- Reviewer identity and mandatory rationale

The original enforcement outcome remains visible after an override.

## Visual System

- Professional neutral surfaces with accessible teal as the primary action color
- Muted terracotta for escalation and warm amber for conditional decisions
- Minimal shadows and compact 6 to 8 pixel radii
- High-density dashboard layout without decorative gradients
- Responsive single-column layout below tablet widths
- Visible keyboard focus, semantic landmarks, labels, and a skip link

## Delivery

FastAPI serves:

```text
GET /                     Review Console
GET /static/styles.css    Console styles
GET /static/app.js        Console behavior
GET /v1/demo/cases        Synthetic scenario templates
```

All workflow data remains on the existing API surface.

## Acceptance Criteria

- The console loads all 15 synthetic scenarios.
- A reviewer can run a case from intake through Audit.
- High-risk cases expose human decision controls.
- All Agent findings include their citations.
- Evidence, controls, Audit checks, and timeline are independently inspectable.
- The interface is usable at desktop and mobile viewport widths.
- There is no horizontal overflow at 390 pixels.
- Existing backend benchmarks remain unchanged.

