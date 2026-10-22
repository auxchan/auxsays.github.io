from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Observation

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS observations (
 observation_id TEXT PRIMARY KEY, indicator_id TEXT NOT NULL, source_id TEXT NOT NULL,
 source_series_id TEXT NOT NULL, release_id TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
 value TEXT NOT NULL, unit TEXT NOT NULL, geography TEXT NOT NULL, valid_time TEXT NOT NULL,
 public_time TEXT NOT NULL, retrieved_time TEXT NOT NULL, accepted_time TEXT NOT NULL,
 vintage_id TEXT NOT NULL, revision_number INTEGER NOT NULL, supersedes_observation_id TEXT,
 publication_time_kind TEXT NOT NULL, provenance_url TEXT NOT NULL, rights_state TEXT NOT NULL,
 UNIQUE(indicator_id, release_id, valid_time)
);
CREATE INDEX IF NOT EXISTS idx_public_asof ON observations(indicator_id, valid_time, public_time, revision_number);
CREATE INDEX IF NOT EXISTS idx_known_asof ON observations(indicator_id, valid_time, accepted_time, revision_number);
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT NOT NULL, source_id TEXT NOT NULL, scheduled_period TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE, attempt INTEGER NOT NULL, status TEXT NOT NULL,
 started_time TEXT NOT NULL, ended_time TEXT, telemetry_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(run_id, source_id, attempt)
);
"""


class ObservationStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def add(self, observation: Observation) -> bool:
        observation.validate()
        columns = list(observation.as_record())
        values = [observation.as_record()[column] for column in columns]
        cursor = self.connection.execute(f"INSERT OR IGNORE INTO observations ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)
        if cursor.rowcount == 1:
            return True
        existing = self.connection.execute("SELECT * FROM observations WHERE observation_id=?", (observation.observation_id,)).fetchone()
        if existing and all(str(existing[column]) == str(observation.as_record()[column]) for column in columns):
            return False
        raise ValueError("duplicate publication identity conflicts with an existing observation")

    def _as_of(self, indicator_id: str, valid_time: str, cutoff_column: str, cutoff: str):
        return self.connection.execute(
            f"SELECT * FROM observations WHERE indicator_id=? AND valid_time=? AND {cutoff_column}<=? AND rights_state='ALLOW' ORDER BY revision_number DESC, {cutoff_column} DESC LIMIT 1",
            (indicator_id, valid_time, cutoff),
        ).fetchone()

    def publicly_available_as_of(self, indicator_id: str, valid_time: str, cutoff: str):
        return self._as_of(indicator_id, valid_time, "public_time", cutoff)

    def operationally_known_as_of(self, indicator_id: str, valid_time: str, cutoff: str):
        return self._as_of(indicator_id, valid_time, "accepted_time", cutoff)

    def latest_revised_truth(self, indicator_id: str, valid_time: str):
        return self.connection.execute("SELECT * FROM observations WHERE indicator_id=? AND valid_time=? AND rights_state='ALLOW' ORDER BY revision_number DESC, public_time DESC LIMIT 1", (indicator_id, valid_time)).fetchone()

    def provenance(self, observation_id: str):
        return self.connection.execute("SELECT source_id,release_id,artifact_sha256,provenance_url FROM observations WHERE observation_id=?", (observation_id,)).fetchone()

    def begin_run(self, run_id: str, source_id: str, scheduled_period: str, idempotency_key: str, attempt: int, started_time: str) -> bool:
        cursor = self.connection.execute("INSERT OR IGNORE INTO runs(run_id,source_id,scheduled_period,idempotency_key,attempt,status,started_time) VALUES(?,?,?,?,?,'RUNNING',?)", (run_id, source_id, scheduled_period, idempotency_key, attempt, started_time))
        return cursor.rowcount == 1

    def finish_run(self, run_id: str, source_id: str, attempt: int, status: str, ended_time: str, telemetry: dict) -> None:
        self.connection.execute("UPDATE runs SET status=?,ended_time=?,telemetry_json=? WHERE run_id=? AND source_id=? AND attempt=?", (status, ended_time, json.dumps(telemetry, sort_keys=True), run_id, source_id, attempt))
