# Week 3: Legal and Policy Agents

## Goal

Turn a validated case and one versioned evidence snapshot into two independent,
structured analyses:

- Legal Agent: identifies issues requiring legal review
- Policy Agent: maps policy requirements into verifiable controls

The agents are evidence-bound decision-support components. They do not provide
legal advice and do not make the final enforcement decision.

## Execution Model

1. Validate the case.
2. Retrieve one immutable `EvidenceResponse`.
3. Run Legal and Policy agents in parallel against that same response.
4. Validate every citation against the retrieved policy ID, version, section,
   and exact section text.
5. Return abstentions when a required category has no supporting evidence.

The current implementation uses deterministic analyzers so tests and benchmark
results are repeatable. The business contracts are provider-neutral, allowing a
future LLM implementation without changing API consumers or audit logic.

## Legal Agent

The Legal Agent:

- Determines review categories from case facts
- Produces issue-spotting findings with severity and confidence
- Escalates high-impact, biometric, and critical child-safety cases
- Adds a jurisdiction-specific legal review question for high-risk findings
- Abstains rather than producing an unsupported claim

## Policy Agent

The Policy Agent:

- Maps case risks to retrieved synthetic policy sections
- Produces one or more controls from section control IDs
- Assigns a control owner and verification method
- Marks controls blocking when a material launch gap exists
- Links every control to a finding from the same analysis

## Citation Guardrail

A citation is accepted only when this complete tuple exists in the supplied
evidence response:

```text
(policy_id@version, section_id, exact_section_text)
```

Policy IDs or quotes invented by an agent fail validation.

## API

`POST /v1/analysis/run`

```json
{
  "case": {
    "...": "A valid CaseIntake payload"
  },
  "top_k": 8
}
```

The response contains the shared evidence snapshot plus Legal and Policy agent
outputs.

## Evaluation

```bash
python scripts/evaluate_agents.py
```

Week 3 acceptance criteria:

- All 15 benchmark cases produce Legal and Policy findings.
- All policy analyses produce controls.
- Every finding has a valid citation from the shared evidence snapshot.
- Missing evidence produces abstention rather than an unsupported finding.
- Expected benchmark risk categories are covered by the combined analyses.

Current deterministic benchmark:

- 15 of 15 cases pass expected-category coverage.
- Citation validity rate is 1.0.
- No analysis contains duplicate control IDs.
- The full test suite contains 22 passing tests.
