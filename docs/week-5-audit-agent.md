# Week 5: Independent Audit Agent

## Goal

Independently verify that a launch review is supported, internally consistent,
reproducible, and unchanged after the audit record is created.

The Audit Agent cannot edit Legal, Policy, or Enforcement output. It returns one
of three verdicts:

- `pass`
- `review_required`
- `fail`

## Audit Checks

| Check | Purpose | Failure severity |
| --- | --- | --- |
| `CASE_IDENTITY` | All stages refer to the same case | Critical |
| `CITATION_INTEGRITY` | Every finding cites exact retrieved evidence | Critical |
| `EVIDENCE_VERSION` | Agents share one evidence snapshot | High |
| `CONTROL_LINKAGE` | Controls retain policy finding lineage | High |
| `RISK_COVERAGE` | Winning rule has required categories | High |
| `ENFORCEMENT_REPLAY` | Independent rule replay matches exactly | Critical |
| `HUMAN_APPROVAL_BOUNDARY` | Escalation and denial require humans | High |
| `ANALYSIS_ABSTENTION` | Missing evidence is explicitly reviewed | Medium |

High or critical check failures produce `fail`. Medium or low failures produce
`review_required`.

## Independent Replay

The Audit Agent loads the versioned enforcement rules independently and
recalculates the result from the case and analysis. Any change to the submitted
outcome, winning rule, rule trace, summary, controls, or open questions causes
the replay check to fail.

## Citation Verification

Every Legal and Policy finding is checked against this exact tuple:

```text
(policy_id@version, section_id, exact_section_text)
```

Fabricated policy IDs, altered excerpts, or citations outside the evidence
snapshot produce a critical audit failure.

## Tamper-Evident Decision Record

After audit, the workflow stores these values in a `DecisionRecord`:

- Validated case input
- Complete launch review
- Audit report
- Creation timestamp
- SHA-256 content hash

The payload is serialized as canonical JSON with sorted keys before hashing.
Changing any stored case, analysis, evidence, enforcement, or audit value causes
verification to fail.

This is a tamper-evident record, not an immutable storage system. Production
immutability would additionally require append-only database controls, object
retention, or an external ledger.

## APIs

Run or audit a supplied launch review:

```text
POST /v1/audit/run
```

Verify a stored decision record:

```text
POST /v1/audit/verify
```

## Adversarial Coverage

The test suite verifies detection of:

- Fabricated citations
- Modified enforcement output
- Altered required controls
- Post-audit record changes
- Agent abstention

## Evaluation

```bash
python scripts/evaluate_audit.py
```

Current benchmark:

- 15 of 15 valid cases pass all audit checks
- All 15 decision record hashes verify
- Check pass rate is `1.0`
- Fabricated citation detection succeeds

