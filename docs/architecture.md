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

