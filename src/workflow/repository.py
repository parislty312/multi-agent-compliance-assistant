import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.models import WorkflowEvent, WorkflowRun, WorkflowStage


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowConflictError(RuntimeError):
    pass


class SQLiteWorkflowRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    case_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, sequence),
                    FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
                );
                """
            )

    def create(self, run: WorkflowRun) -> WorkflowRun:
        state_json = run.model_dump_json()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO workflow_runs (
                        run_id, idempotency_key, case_id, status, current_stage,
                        version, state_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.run_id,
                        run.idempotency_key,
                        run.case.case_id,
                        run.status.value,
                        run.current_stage.value,
                        run.version,
                        state_json,
                        run.created_at.isoformat(),
                        run.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            existing = self.get_by_idempotency_key(run.idempotency_key)
            if existing:
                return existing
            raise WorkflowConflictError(str(error)) from error
        return run

    def get(self, run_id: str) -> WorkflowRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM workflow_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise WorkflowNotFoundError(run_id)
        return WorkflowRun.model_validate_json(row["state_json"])

    def get_by_idempotency_key(self, key: str) -> WorkflowRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM workflow_runs WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
        return (
            WorkflowRun.model_validate_json(row["state_json"])
            if row is not None
            else None
        )

    def save(self, run: WorkflowRun, *, expected_version: int) -> WorkflowRun:
        next_run = run.model_copy(
            update={
                "version": expected_version + 1,
                "updated_at": datetime.now(UTC),
            }
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE workflow_runs
                SET status = ?, current_stage = ?, version = ?, state_json = ?,
                    updated_at = ?
                WHERE run_id = ? AND version = ?
                """,
                (
                    next_run.status.value,
                    next_run.current_stage.value,
                    next_run.version,
                    next_run.model_dump_json(),
                    next_run.updated_at.isoformat(),
                    next_run.run_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise WorkflowConflictError(
                    f"workflow {run.run_id} changed after version {expected_version}"
                )
        return next_run

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        stage: WorkflowStage,
        payload: dict[str, object],
    ) -> WorkflowEvent:
        created_at = datetime.now(UTC)
        with self._connect() as connection:
            latest = connection.execute(
                """
                SELECT sequence, event_hash
                FROM workflow_events
                WHERE run_id = ?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            sequence = (latest["sequence"] + 1) if latest else 1
            previous_hash = latest["event_hash"] if latest else ""
            payload_json = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            hash_payload = json.dumps(
                {
                    "run_id": run_id,
                    "sequence": sequence,
                    "event_type": event_type,
                    "stage": stage.value,
                    "payload": json.loads(payload_json),
                    "previous_hash": previous_hash,
                    "created_at": created_at.isoformat(),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
            event_hash = hashlib.sha256(hash_payload).hexdigest()
            cursor = connection.execute(
                """
                INSERT INTO workflow_events (
                    run_id, sequence, event_type, stage, payload_json,
                    previous_hash, event_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    event_type,
                    stage.value,
                    payload_json,
                    previous_hash,
                    event_hash,
                    created_at.isoformat(),
                ),
            )
            event_id = cursor.lastrowid
        return WorkflowEvent(
            event_id=event_id,
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            stage=stage,
            payload=payload,
            previous_hash=previous_hash,
            event_hash=event_hash,
            created_at=created_at,
        )

    def list_events(self, run_id: str) -> list[WorkflowEvent]:
        self.get(run_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, run_id, sequence, event_type, stage,
                       payload_json, previous_hash, event_hash, created_at
                FROM workflow_events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return [
            WorkflowEvent(
                event_id=row["event_id"],
                run_id=row["run_id"],
                sequence=row["sequence"],
                event_type=row["event_type"],
                stage=row["stage"],
                payload=json.loads(row["payload_json"]),
                previous_hash=row["previous_hash"],
                event_hash=row["event_hash"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def verify_event_chain(self, run_id: str) -> bool:
        events = self.list_events(run_id)
        previous_hash = ""
        for event in events:
            if event.previous_hash != previous_hash:
                return False
            hash_payload = json.dumps(
                {
                    "run_id": event.run_id,
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                    "stage": event.stage.value,
                    "payload": event.payload,
                    "previous_hash": event.previous_hash,
                    "created_at": event.created_at.isoformat(),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
            if hashlib.sha256(hash_payload).hexdigest() != event.event_hash:
                return False
            previous_hash = event.event_hash
        return True
