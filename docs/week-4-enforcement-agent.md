# Week 4: Deterministic Enforcement Agent

## Goal

Convert evidence-backed Legal and Policy analysis into a reproducible launch
decision:

- `allow`
- `conditional_allow`
- `escalate`
- `deny`

The Enforcement Agent does not interpret policy text or generate new
requirements. It evaluates versioned rules against structured case facts and
the validated outputs of the Legal and Policy agents.

## Policy-as-Code Rules

The initial ruleset is stored in:

```text
rules/enforcement_rules.json
```

Each rule includes:

- Stable rule ID
- Ruleset version and effective date
- Explicit priority
- Named predicate
- Outcome and risk level
- Human-readable explanation
- Required analysis categories

Rules use business predicates implemented in Python rather than arbitrary
expression evaluation. Unknown predicate names fail engine initialization.

## Priority

Rules are evaluated in descending priority:

```text
deny > escalate > conditional_allow > allow
```

The first matched rule becomes the winning rule. Lower-priority rules remain in
the trace for explanation, except the fallback allow rule is suppressed whenever
a higher-priority rule matches.

## Initial Rules

| Rule | Outcome | Purpose |
| --- | --- | --- |
| `RULE-DENY-001` | Deny | Unsafe under-thirteen companion launch |
| `RULE-DENY-002` | Deny | Autonomous employee termination |
| `RULE-ESC-001` | Escalate | High-impact automated decision |
| `RULE-ESC-002` | Escalate | Biometric identity decision |
| `RULE-COND-001` | Conditional | Material launch safeguards missing |
| `RULE-COND-002` | Conditional | Minor safeguards incomplete |
| `RULE-COND-003` | Conditional | Sensitive-data approval unresolved |
| `RULE-ALLOW-001` | Allow | Controlled low-risk fallback |

Rules are based on case facts, not benchmark case IDs.

## Rule Trace

Every evaluation records:

- Whether each rule matched
- Priority and proposed outcome
- Predicate name
- Facts used by the predicate
- Explanation
- Winning rule ID
- Ruleset ID and version

This trace allows the same case and analysis snapshot to be replayed against the
same ruleset.

## Human Boundary

- `allow`: no human approval required
- `conditional_allow`: controls must be completed before launch
- `escalate`: an authorized human must approve or reject
- `deny`: a human confirms the denial and owns any exception process

The Enforcement Agent does not directly change production configuration.

## API

`POST /v1/enforcement/evaluate`

The request may contain:

- A case only, causing the Legal and Policy workflow to run first
- A case plus an existing `ParallelAnalysisResponse` for deterministic replay

## Evaluation

```bash
python scripts/evaluate_enforcement.py
```

Current benchmark:

- 15 of 15 outcomes match the expected labels
- Outcome accuracy is `1.0`
- Expected and actual distributions are identical
- All decisions include a complete eight-rule trace

