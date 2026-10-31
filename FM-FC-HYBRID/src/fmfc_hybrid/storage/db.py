"""SQLite persistence: one local database file per career.

Design points:

* Schema migrations are tracked with ``PRAGMA user_version``.
* Append-only tables (audit log, transitions, ledger events, finalizations,
  snapshots) are protected by triggers that ABORT on UPDATE/DELETE, so even
  a buggy caller cannot rewrite history.
* Transactions use ``BEGIN IMMEDIATE`` to take the write lock up front; WAL
  journaling keeps readers non-blocking and makes crash recovery safe.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


_APPEND_ONLY_TABLES = (
    "audit_log",
    "match_transitions",
    "state_snapshots",
    "ledger_events",
    "ledger_finalizations",
    "ledger_corrections",
    "player_snapshots",
    "import_attempts_log",
)

_SCHEMA_V1 = """
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);

CREATE TABLE matches (
    match_id TEXT PRIMARY KEY,
    career_id TEXT NOT NULL,
    fixture_id TEXT NOT NULL,
    fm_fixture_ref TEXT NOT NULL,
    state TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    attempt INTEGER NOT NULL DEFAULT 1,
    fixture_json TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_matches_fixture ON matches(career_id, fixture_id);
-- At most one live (non-abandoned) match per career fixture: the primary duplicate-processing guard.
CREATE UNIQUE INDEX uq_matches_live_fixture ON matches(career_id, fixture_id) WHERE state != 'ABANDONED';
CREATE INDEX idx_matches_state ON matches(state);

CREATE TABLE match_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    from_state TEXT,
    to_state TEXT NOT NULL,
    ts TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_transitions_match ON match_transitions(match_id);

CREATE TABLE state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    content TEXT NOT NULL,
    ts TEXT NOT NULL
);
CREATE INDEX idx_snapshots_match ON state_snapshots(match_id, kind);

CREATE TABLE ledger_events (
    match_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    source_event_id TEXT NOT NULL,
    event_json TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    chain_hash TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (match_id, seq),
    UNIQUE (match_id, source_event_id)
);

CREATE TABLE ledger_finalizations (
    match_id TEXT PRIMARY KEY,
    event_count INTEGER NOT NULL,
    head_hash TEXT NOT NULL,
    record_json TEXT NOT NULL,
    record_sha256 TEXT NOT NULL,
    finalized_at TEXT NOT NULL
);

CREATE TABLE ledger_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES ledger_finalizations(match_id),
    correction_type TEXT NOT NULL,
    target_source_event_id TEXT,
    replacement_json TEXT,
    reason TEXT NOT NULL,
    author TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE players (
    hybrid_player_id TEXT PRIMARY KEY,
    career_id TEXT NOT NULL,
    fm_player_id INTEGER NOT NULL,
    fifa_player_id INTEGER,
    fifa_link_status TEXT NOT NULL,
    display_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    origin TEXT NOT NULL,
    club_fm_id INTEGER,
    primary_position TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    profile_json TEXT NOT NULL,
    profile_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_synced_at TEXT NOT NULL,       -- last capture from FM (the authority)
    last_fifa_sync_at TEXT,             -- last time the FIFA record was written from this profile
    UNIQUE (career_id, fm_player_id),
    UNIQUE (career_id, fifa_player_id)
);

CREATE TABLE player_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hybrid_player_id TEXT NOT NULL REFERENCES players(hybrid_player_id),
    profile_json TEXT NOT NULL,
    profile_sha256 TEXT NOT NULL,
    reason TEXT NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE TABLE fifa_id_allocations (
    career_id TEXT NOT NULL,
    fifa_player_id INTEGER NOT NULL,
    hybrid_player_id TEXT NOT NULL,
    allocated_at TEXT NOT NULL,
    PRIMARY KEY (career_id, fifa_player_id)
);

CREATE TABLE imports (
    career_id TEXT NOT NULL,
    fixture_id TEXT NOT NULL,
    match_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,            -- pending | completed | verified | failed
    receipt_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (career_id, fixture_id)
);

CREATE TABLE import_attempts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}',
    ts TEXT NOT NULL
);
"""


def _immutability_triggers() -> str:
    parts = []
    for table in _APPEND_ONLY_TABLES:
        for op in ("UPDATE", "DELETE"):
            parts.append(
                f"CREATE TRIGGER trg_{table}_no_{op.lower()} BEFORE {op} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;"
            )
    parts.append(
        "CREATE TRIGGER trg_ledger_events_finalized BEFORE INSERT ON ledger_events "
        "WHEN EXISTS (SELECT 1 FROM ledger_finalizations f WHERE f.match_id = NEW.match_id) "
        "BEGIN SELECT RAISE(ABORT, 'ledger is finalized for this match'); END;"
    )
    return "\n".join(parts)


_MIGRATIONS = {1: _SCHEMA_V1 + _immutability_triggers()}


class Database:
    """Thin wrapper around a sqlite3 connection with migrations and transactions."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._depth = 0
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = FULL")
        self._migrate()

    def _migrate(self) -> None:
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"Database schema {current} is newer than supported {SCHEMA_VERSION}")
        for version in range(current + 1, SCHEMA_VERSION + 1):
            with self.transaction():
                for statement in _split_sql(_MIGRATIONS[version]):
                    self._conn.execute(statement)
                self._conn.execute(f"PRAGMA user_version = {version}")

    @property
    def schema_version(self) -> int:
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Re-entrant write transaction (nested calls join the outer one)."""
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self._conn
            except BaseException:
                self._depth -= 1
                if outer:
                    self._conn.execute("ROLLBACK")
                raise
            else:
                self._depth -= 1
                if outer:
                    self._conn.execute("COMMIT")

    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    def audit(self, actor: str, action: str, entity_type: str, entity_id: str,
              payload: dict[str, Any] | None = None) -> None:
        self.execute(
            "INSERT INTO audit_log(ts, actor, action, entity_type, entity_id, payload) VALUES (?,?,?,?,?,?)",
            (utc_now(), actor, action, entity_type, entity_id, json.dumps(payload or {}, sort_keys=True)),
        )

    def audit_trail(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        rows = self.query_all(
            "SELECT ts, actor, action, payload FROM audit_log WHERE entity_type=? AND entity_id=? ORDER BY id",
            (entity_type, entity_id),
        )
        return [{"ts": r["ts"], "actor": r["actor"], "action": r["action"], "payload": json.loads(r["payload"])}
                for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _split_sql(script: str) -> list[str]:
    """Split a schema script into statements (trigger bodies contain ';')."""
    statements, buf = [], []
    for line in script.splitlines():
        buf.append(line)
        candidate = "\n".join(buf).strip()
        if candidate and sqlite3.complete_statement(candidate):
            statements.append(candidate)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements
