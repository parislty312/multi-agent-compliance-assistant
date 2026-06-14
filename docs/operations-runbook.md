# Operations Runbook

## Local Production Check

```bash
export APP_ENV=production
export COMPLIANCE_API_KEY="replace-with-a-long-random-secret"
export WORKFLOW_DB_PATH=".data/production-workflows.db"
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Verify:

```bash
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
curl --fail -H "X-API-Key: $COMPLIANCE_API_KEY" \
  http://127.0.0.1:8000/v1/policies
curl --fail -H "X-API-Key: $COMPLIANCE_API_KEY" \
  http://127.0.0.1:8000/metrics
```

## Docker Deployment

```bash
export COMPLIANCE_API_KEY="replace-with-a-long-random-secret"
docker compose up --build -d
docker compose ps
```

The `compliance-data` volume contains the SQLite database. Do not remove the
volume during a routine application upgrade.

## Monitoring

Alert on:

- `/health/ready` returning HTTP 503
- Sustained HTTP 5xx responses
- Unexpected increases in HTTP 401 or 413 responses
- Workflow `failed` events
- Audit verdicts other than `pass`
- Event-chain verification failures

Use `X-Request-ID` to correlate a client error with the structured access log.
Do not log API keys, full case payloads, evidence contents, or human-review
rationales.

## Backup and Restore

For this single-instance SQLite deployment:

1. Stop the application or use SQLite's online backup facility.
2. Copy the workflow database and its `-wal` and `-shm` files together.
3. Record the application, policy-index, and ruleset versions.
4. Restore into a separate path.
5. Start the application and verify `/health/ready`.
6. Verify representative workflow event chains before serving traffic.

For multiple replicas, migrate the repository boundary to PostgreSQL rather
than sharing the SQLite file over a network filesystem.

## Credential Rotation

1. Generate a new high-entropy secret.
2. Update the deployment secret.
3. Restart the application.
4. Verify authenticated access with the new key.
5. Confirm the old key receives HTTP 401.

The current prototype supports one active API key. A production identity
provider should replace this mechanism when per-user authorization is needed.

## Incident Response

If record or event tampering is suspected:

1. Remove the service from traffic.
2. Preserve the database and application logs.
3. Run event-chain and decision-record verification.
4. Identify affected run IDs and policy/ruleset versions.
5. Do not overwrite or delete the original records.
6. Restore from a verified backup or rebuild affected reviews from source
   inputs under a new run ID.

This prototype provides tamper evidence, not immutable storage. Regulated
deployment should export records to append-only storage with independent
retention controls.
