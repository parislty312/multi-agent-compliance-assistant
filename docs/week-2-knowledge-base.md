# Week 2: Versioned Policy Knowledge Base

## Goal

Provide Legal and Policy agents with precise, versioned evidence instead of
allowing them to rely on model memory. The Week 2 implementation establishes a
deterministic retrieval baseline that can later be compared with embedding and
hybrid retrieval.

## Policy Corpus

The corpus contains six synthetic internal policies:

| Policy | Primary coverage |
| --- | --- |
| `POL-PRIV-001` | Privacy, retention, sensitive data, model providers |
| `POL-CHILD-001` | Children, teens, parental controls, minor monitoring |
| `POL-HIGH-001` | Employment, credit, health, identity decisions |
| `POL-SAFE-001` | Generative content evaluation and incident response |
| `POL-TRANS-001` | Notice, explanation, appeal, personalization |
| `POL-GOV-001` | Ownership, human oversight, audit records |

All policy files set `synthetic: true`. They are product requirements for this
prototype, not quotations or summaries that should be treated as legal advice.

## Evidence Unit

Each policy section becomes one immutable evidence chunk containing:

- Policy ID, title, version, and effective date
- Section ID and exact section text
- Jurisdiction and risk categories
- Applicable feature, data, age, and decision-domain metadata
- Control IDs

The section is intentionally the smallest retrieval unit so an agent can cite
the exact text that supports a finding.

## Baseline Retrieval

The baseline combines:

1. Lexical overlap with policy titles, section text, keywords, and domains
2. Structured matches for feature type, data categories, age group, and market
3. Risk signals such as automated decisions, missing notice, missing safety
   evaluation, and missing human oversight
4. Category coverage selection so a result set does not over-focus on one risk

Every match returns a numeric score and a `matched_on` explanation. This makes
the baseline debuggable and gives future semantic retrieval a measurable point
of comparison.

## API

### Retrieve evidence

`POST /v1/evidence/retrieve`

```json
{
  "case": {
    "...": "A valid CaseIntake payload"
  },
  "categories": ["privacy"],
  "jurisdictions": ["US"],
  "top_k": 8
}
```

### List policy versions

`GET /v1/policies`

## Week 2 Acceptance Criteria

- All six policy documents pass strict schema validation.
- All 19 active sections receive unique evidence chunk IDs.
- Every evidence result includes exact section text and version metadata.
- The Top-8 result set covers every expected risk category in all 15 benchmark
  cases.
- Retrieval remains deterministic for the same corpus and request.

Run the benchmark:

```bash
python scripts/evaluate_retrieval.py
```

The current baseline covers all 38 expected category labels across the 15 cases
at Top-8.

## Next Iteration

Week 3 agents should consume only `EvidenceResponse` records. A Legal or Policy
finding without a retrieved section should be marked unsupported or require
human review.
