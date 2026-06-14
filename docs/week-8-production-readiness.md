# Week 8: Production Readiness and Delivery

## Goal

Turn the eight-week prototype into a deployable portfolio project with explicit
security boundaries, observable runtime behavior, repeatable delivery, and an
operator-facing recovery guide.

Week 8 does not change Legal, Policy, Enforcement, or Audit decisions. It wraps
the existing system with controls required to run and evaluate it responsibly.

## Runtime Configuration

Configuration is loaded from environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime environment |
| `COMPLIANCE_API_KEY` | empty | API credential; required in production |
| `WORKFLOW_DB_PATH` | `.data/workflows.db` | Durable SQLite path |
| `LOG_LEVEL` | `INFO` | Python log level |
| `MAX_REQUEST_BYTES` | `1048576` | Maximum HTTP request body |
| `DOCS_ENABLED` | environment-dependent | OpenAPI and documentation routes |

`APP_ENV=production` fails at startup when no API key is configured. API docs
are disabled by default in production and can be explicitly re-enabled.

## Request Security

When an API key is configured, every operational `/v1` endpoint requires:

```text
X-API-Key: <secret>
```

or:

```text
Authorization: Bearer <secret>
```

The synthetic demo-case catalog remains public so the console can display its
non-confidential templates before authentication. Liveness and readiness
probes are also public. Metrics use the same API-key protection.

Every response includes:

- A validated or generated `X-Request-ID`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- A same-origin Content Security Policy
- A strict referrer policy
- No-store caching for `/v1` responses

Requests above the configured body limit are rejected with HTTP 413.

## Observability

Access logs are emitted as one-line JSON with:

- Request ID
- Method and path
- Status code
- Request duration in milliseconds

`GET /metrics` exposes Prometheus counters for request totals and cumulative
duration. Route templates are used after routing to avoid workflow IDs becoming
metric labels.

Health endpoints:

```text
GET /health/live
GET /health/ready
```

Readiness returns HTTP 503 if the workflow database cannot be queried or the
policy index is unavailable.

## Delivery

The Docker image:

- Uses Python 3.12 slim
- Runs as an unprivileged `compliance` user
- Stores SQLite data under `/app/data`
- Includes an image health check
- Uses the existing Uvicorn application server

`docker-compose.yml` mounts a named volume for durable workflow state and
requires `COMPLIANCE_API_KEY`.

GitHub Actions runs:

1. Ruff
2. Pytest
3. All five deterministic benchmark suites
4. A container build

## Acceptance Criteria

- Production startup fails closed without an API key.
- Protected endpoints reject missing or incorrect credentials.
- Development mode remains usable without credentials.
- Oversized requests are rejected before application processing.
- Every response has a request ID and security headers.
- Live and ready probes report separate concerns.
- Prometheus metrics expose request count and duration.
- Docker runs as a non-root user with persistent data.
- CI verifies lint, tests, benchmarks, and image construction.
- Existing Agent and workflow benchmark results remain unchanged.
