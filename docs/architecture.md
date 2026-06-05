# Architecture

The assistant follows a controlled manager workflow:

1. Intake validates and normalizes an AI product launch case.
2. Legal and Policy agents analyze the case in parallel.
3. Their structured findings are mapped into enforceable controls.
4. The Enforcement agent evaluates deterministic policy rules.
5. The Audit agent independently reviews the evidence and decision.
6. High-risk or uncertain cases are escalated to a human reviewer.
7. Every input, finding, policy version, decision, and override is recorded.

Agent outputs will use strict schemas and evidence references. The language model
may identify and explain requirements, but deterministic rules or authorized
humans own final enforcement actions.

## Decision Flow

```mermaid
flowchart LR
    A["Case Intake"] --> B["Schema Validation"]
    B --> C["Legal Agent"]
    B --> D["Policy Agent"]
    C --> E["Control Mapping"]
    D --> E
    E --> F["Enforcement Agent"]
    F --> G["Audit Agent"]
    G --> H{"Human approval?"}
    H -->|Yes| I["Compliance Reviewer"]
    H -->|No| J["Final Decision"]
    I --> J
    J --> K["Decision Record"]
```

## Contract Boundary

- `CaseIntake` is the only accepted input to orchestration.
- `AgentFinding` is the shared evidence-bearing analysis unit.
- `ControlRequirement` translates findings into verifiable action.
- `ComplianceDecision` is the final versioned workflow result.
- Schema validation happens before and after every agent handoff.

## Evidence Layer

```mermaid
flowchart LR
    A["Versioned Policy JSON"] --> B["Schema Validation"]
    B --> C["Section Evidence Chunks"]
    D["Case Intake"] --> E["Metadata and Lexical Query"]
    C --> F["Deterministic Retriever"]
    E --> F
    F --> G["Evidence Response"]
    G --> H["Legal and Policy Agents"]
```

The Week 2 retriever is intentionally deterministic. It exposes scoring reasons
and preserves exact policy section text, allowing future embedding retrieval to
be evaluated against a transparent baseline.

## Parallel Analysis Layer

```mermaid
flowchart LR
    A["Validated Case"] --> B["Evidence Retriever"]
    B --> C["Immutable Evidence Snapshot"]
    C --> D["Legal Agent"]
    C --> E["Policy Agent"]
    D --> F["Citation Validator"]
    E --> F
    F --> G["Parallel Analysis Response"]
```

Legal and Policy agents run independently against the same evidence snapshot.
They cannot query unversioned sources during analysis. Findings that cannot cite
an exact retrieved section are rejected, while missing evidence is represented
as an explicit abstention.

## Enforcement Layer

```mermaid
flowchart LR
    A["Case Facts"] --> C["Enforcement Agent"]
    B["Legal and Policy Analysis"] --> C
    D["Versioned Rule Set"] --> C
    C --> E["Rule Trace"]
    E --> F{"Winning Outcome"}
    F --> G["Allow"]
    F --> H["Conditional Allow"]
    F --> I["Human Escalation"]
    F --> J["Deny"]
```

The enforcement layer is deterministic and does not invoke a language model.
It applies explicit rule priorities, requires supporting analysis categories,
and records every evaluated predicate and input fact.

## Audit Layer

```mermaid
flowchart LR
    A["Case"] --> D["Audit Agent"]
    B["Evidence and Agent Analysis"] --> D
    C["Enforcement Result"] --> D
    E["Independent Rule Engine"] --> D
    D --> F["Audit Verdict"]
    D --> G["Canonical Decision Record"]
    G --> H["SHA-256 Content Hash"]
```

The Audit Agent validates lineage and independently replays enforcement. The
resulting content hash makes later changes detectable, while durable
immutability remains the responsibility of a future storage layer.
