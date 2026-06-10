# Week 6: Durable Orchestration and Human Approval

## Goal

Turn the synchronous compliance pipeline into a resumable workflow with durable
state, human approval boundaries, and an inspectable event timeline.

## State Machine

```text
submitted
  -> analyzing
  -> enforcing
  -> auditing
  -> completed
  -> awaiting_approval -> completed/rejected
  -> failed -> resume
```

Each completed stage is checkpointed before the next stage starts. A retry uses
the stored analysis, enforcement, or audit output and executes only the missing
stages.

## Workflow State

Every `WorkflowRun` stores:

- Stable run and idempotency IDs
- Validated case input
- Current status and stage
- Optimistic concurrency version
- Attempt count
- Analysis, enforcement, audit, and decision-record checkpoints
- Human decision and final outcome
- Error and retryability state
- Creation and update timestamps

## Persistence

The initial repository uses SQLite and Python's standard library. It creates:

- `workflow_runs`: latest materialized workflow state
- `workflow_events`: ordered append-only timeline

`WORKFLOW_DB_PATH` configures the database location. The default is:

```text
.data/workflows.db
```

The repository interface can later be replaced by PostgreSQL without changing
the Orchestrator's business logic.

## Idempotency

Clients may provide an `idempotency_key` when starting a workflow.

- Repeating the same request returns the original run.
- Reusing the key for a different case or `top_k` value returns a conflict.
- A repeated request does not append duplicate events.

## Concurrency

Every state update includes an expected version:

```sql
UPDATE workflow_runs
SET version = version + 1, ...
WHERE run_id = ? AND version = ?
```

If another worker or reviewer has already updated the run, the stale update is
rejected instead of silently overwriting the newer decision.

## Failure Recovery

Exceptions create a `failed` state and a `workflow_failed` event. Retryable
failures can be resumed:

```text
POST /v1/workflows/{run_id}/resume
```

For example, if enforcement fails after analysis was saved, the resumed workflow
starts at enforcement and does not repeat evidence retrieval or agent analysis.
An Audit Agent integrity failure is non-retryable because replaying unchanged
inputs would reproduce the same failure.

## Human Decisions

`escalate`, `deny`, or an audit requiring review pauses in
`awaiting_approval`.

Supported actions:

- `approve`: accept the original enforcement outcome
- `reject`: set the final outcome to deny
- `override`: record a different final outcome and mandatory rationale

The original enforcement and audit records are preserved. Human decisions are
stored separately so overrides remain visible.

## Event Timeline

Every event contains:

- Run ID and sequence
- Event type and workflow stage
- Structured payload
- Previous event hash
- SHA-256 event hash
- Timestamp

The previous hash creates a per-run hash chain. Editing or removing a stored
event makes timeline verification fail. This provides tamper evidence, while
production append-only storage remains a future infrastructure concern.

## APIs

```text
POST /v1/workflows
GET  /v1/workflows/{run_id}
GET  /v1/workflows/{run_id}/events
POST /v1/workflows/{run_id}/resume
POST /v1/workflows/{run_id}/decision
```

## Evaluation

```bash
python scripts/evaluate_workflow.py
```

Week 6 acceptance criteria:

- All 15 benchmark cases reach the expected terminal or approval state.
- Every run contains analysis, enforcement, audit, and record checkpoints.
- Repeated idempotent requests return the same run.
- All event hash chains verify.
- Retry resumes from the latest checkpoint.
- Stale concurrent updates are rejected.

