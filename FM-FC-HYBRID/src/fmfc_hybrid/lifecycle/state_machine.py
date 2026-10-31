"""Formal match lifecycle (see docs/MATCH_LIFECYCLE.md for the diagram).

The happy path::

    FIXTURE_DETECTED -> FM_STATE_CAPTURED -> MATCH_PREPARED -> MATCH_IN_PROGRESS
    -> MATCH_DATA_CAPTURED -> MATCH_VALIDATED -> FM_IMPORT_PENDING
    -> FM_IMPORT_COMPLETED -> FM_IMPORT_VERIFIED

Every failure has its own state with explicit recovery edges. All transitions
are persisted (append-only ``match_transitions``) with optimistic concurrency on
``matches.version`` so two bridge processes can never both advance one match.
"""

from __future__ import annotations

import enum
import json
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from ..contracts.models import Fixture
from ..contracts.serialization import canonical_json, from_primitive
from ..errors import ConcurrencyError, DuplicateImportError, InvalidTransitionError
from ..storage.db import Database, utc_now


class MatchState(str, enum.Enum):
    FIXTURE_DETECTED = "FIXTURE_DETECTED"
    FM_STATE_CAPTURED = "FM_STATE_CAPTURED"
    MATCH_PREPARED = "MATCH_PREPARED"
    MATCH_IN_PROGRESS = "MATCH_IN_PROGRESS"
    MATCH_DATA_CAPTURED = "MATCH_DATA_CAPTURED"
    MATCH_VALIDATED = "MATCH_VALIDATED"
    FM_IMPORT_PENDING = "FM_IMPORT_PENDING"
    FM_IMPORT_COMPLETED = "FM_IMPORT_COMPLETED"
    FM_IMPORT_VERIFIED = "FM_IMPORT_VERIFIED"
    # failure states
    CAPTURE_FAILED = "CAPTURE_FAILED"
    MAPPING_INVALID = "MAPPING_INVALID"
    PREPARATION_FAILED = "PREPARATION_FAILED"
    LAUNCH_FAILED = "LAUNCH_FAILED"
    MATCH_INTERRUPTED = "MATCH_INTERRUPTED"
    DATA_CAPTURE_FAILED = "DATA_CAPTURE_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    IMPORT_FAILED = "IMPORT_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    # terminal
    ABANDONED = "ABANDONED"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATES

    @property
    def is_failure(self) -> bool:
        return self in FAILURE_STATES


S = MatchState

TERMINAL_STATES = frozenset({S.FM_IMPORT_VERIFIED, S.ABANDONED})
FAILURE_STATES = frozenset({
    S.CAPTURE_FAILED, S.MAPPING_INVALID, S.PREPARATION_FAILED, S.LAUNCH_FAILED, S.MATCH_INTERRUPTED,
    S.DATA_CAPTURE_FAILED, S.VALIDATION_FAILED, S.IMPORT_FAILED, S.VERIFICATION_FAILED,
})
#: States from which abandoning is *unsafe* because FM may already hold the result.
IMPORT_SENSITIVE_STATES = frozenset({S.FM_IMPORT_PENDING, S.FM_IMPORT_COMPLETED, S.IMPORT_FAILED,
                                     S.VERIFICATION_FAILED})

TRANSITIONS: dict[MatchState, frozenset[MatchState]] = {
    S.FIXTURE_DETECTED: frozenset({S.FM_STATE_CAPTURED, S.CAPTURE_FAILED, S.ABANDONED}),
    S.FM_STATE_CAPTURED: frozenset({S.MATCH_PREPARED, S.PREPARATION_FAILED, S.MAPPING_INVALID, S.ABANDONED}),
    S.MATCH_PREPARED: frozenset({S.MATCH_IN_PROGRESS, S.LAUNCH_FAILED, S.ABANDONED}),
    S.MATCH_IN_PROGRESS: frozenset({S.MATCH_DATA_CAPTURED, S.MATCH_INTERRUPTED, S.DATA_CAPTURE_FAILED}),
    S.MATCH_DATA_CAPTURED: frozenset({S.MATCH_VALIDATED, S.VALIDATION_FAILED}),
    S.MATCH_VALIDATED: frozenset({S.FM_IMPORT_PENDING}),
    S.FM_IMPORT_PENDING: frozenset({S.FM_IMPORT_COMPLETED, S.IMPORT_FAILED}),
    S.FM_IMPORT_COMPLETED: frozenset({S.FM_IMPORT_VERIFIED, S.VERIFICATION_FAILED}),
    S.FM_IMPORT_VERIFIED: frozenset(),
    # recovery edges
    S.CAPTURE_FAILED: frozenset({S.FIXTURE_DETECTED, S.ABANDONED}),
    S.MAPPING_INVALID: frozenset({S.FM_STATE_CAPTURED, S.ABANDONED}),
    S.PREPARATION_FAILED: frozenset({S.FM_STATE_CAPTURED, S.ABANDONED}),
    S.LAUNCH_FAILED: frozenset({S.MATCH_PREPARED, S.FM_STATE_CAPTURED, S.ABANDONED}),
    S.MATCH_INTERRUPTED: frozenset({S.FM_STATE_CAPTURED, S.ABANDONED}),
    S.DATA_CAPTURE_FAILED: frozenset({S.MATCH_IN_PROGRESS, S.FM_STATE_CAPTURED, S.ABANDONED}),
    S.VALIDATION_FAILED: frozenset({S.FM_STATE_CAPTURED, S.ABANDONED}),
    S.IMPORT_FAILED: frozenset({S.FM_IMPORT_PENDING, S.FM_IMPORT_COMPLETED, S.ABANDONED}),
    S.VERIFICATION_FAILED: frozenset({S.FM_IMPORT_COMPLETED, S.ABANDONED}),
    S.ABANDONED: frozenset(),
}

#: Re-entering these states from a failure starts a new FIFA attempt (fresh ledger stream).
NEW_ATTEMPT_ENTRY = frozenset({S.FM_STATE_CAPTURED})


@dataclass(frozen=True)
class MatchRecord:
    match_id: str
    career_id: str
    fixture_id: str
    fm_fixture_ref: str
    state: MatchState
    version: int
    attempt: int
    fixture: Fixture
    last_error: Optional[dict[str, Any]]
    created_at: str
    updated_at: str

    @property
    def ledger_match_id(self) -> str:
        """Ledger stream id for the current attempt (replays never mix events)."""
        return f"{self.match_id}:{self.attempt}"


@dataclass(frozen=True)
class Transition:
    from_state: Optional[MatchState]
    to_state: MatchState
    ts: str
    reason: str
    payload: dict[str, Any]


class MatchLifecycle:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- creation ------------------------------------------------------
    def create(self, fixture: Fixture, *, actor: str = "bridge") -> MatchRecord:
        """Register a detected fixture. Refuses a second live match for the same fixture."""
        with self.db.transaction():
            live = self.find_live(fixture.career_id, fixture.fixture_id)
            if live is not None:
                raise DuplicateImportError(
                    f"fixture {fixture.fixture_id} already has live match {live.match_id} in {live.state.value}",
                    details={"match_id": live.match_id, "state": live.state.value},
                )
            completed = self.db.query_one(
                "SELECT status FROM imports WHERE career_id=? AND fixture_id=? AND status IN ('completed','verified')",
                (fixture.career_id, fixture.fixture_id))
            if completed is not None:
                raise DuplicateImportError(f"fixture {fixture.fixture_id} was already imported into FM")
            match_id = f"M-{uuid.uuid4().hex[:16]}"
            ts = utc_now()
            self.db.execute(
                "INSERT INTO matches(match_id, career_id, fixture_id, fm_fixture_ref, state, version, attempt, "
                "fixture_json, created_at, updated_at) VALUES (?,?,?,?,?,0,1,?,?,?)",
                (match_id, fixture.career_id, fixture.fixture_id, fixture.fm_fixture_ref,
                 S.FIXTURE_DETECTED.value, canonical_json(fixture), ts, ts),
            )
            self.db.execute(
                "INSERT INTO match_transitions(match_id, from_state, to_state, ts, reason) VALUES (?,?,?,?,?)",
                (match_id, None, S.FIXTURE_DETECTED.value, ts, "fixture detected"),
            )
            self.db.audit(actor, "match.create", "match", match_id,
                          {"fixture_id": fixture.fixture_id, "fm_fixture_ref": fixture.fm_fixture_ref})
        return self.get(match_id)

    # -- transitions ---------------------------------------------------
    def transition(self, match_id: str, to_state: MatchState, *, expected_version: int, reason: str = "",
                   payload: dict[str, Any] | None = None, error: dict[str, Any] | None = None,
                   actor: str = "bridge", allow_unsafe_abandon: bool = False,
                   fixture: Optional[Fixture] = None) -> MatchRecord:
        """Advance a match. ``fixture`` may replace the stored fixture only when entering
        FM_STATE_CAPTURED (binding FM references to hybrid ids); the change is audited."""
        with self.db.transaction():
            current = self.get(match_id)
            if current.version != expected_version:
                raise ConcurrencyError(
                    f"match {match_id} is at version {current.version}, expected {expected_version}",
                    details={"state": current.state.value})
            if to_state not in TRANSITIONS[current.state]:
                raise InvalidTransitionError(
                    f"{current.state.value} -> {to_state.value} is not a permitted transition",
                    details={"match_id": match_id})
            if (to_state is S.ABANDONED and current.state in IMPORT_SENSITIVE_STATES
                    and not allow_unsafe_abandon):
                raise InvalidTransitionError(
                    f"abandoning from {current.state.value} requires explicit confirmation that FM did not "
                    "apply the result (allow_unsafe_abandon=True)", details={"match_id": match_id})
            attempt = current.attempt
            if to_state in NEW_ATTEMPT_ENTRY and current.state.is_failure:
                attempt += 1
            ts = utc_now()
            if error:
                last_error = json.dumps(error, sort_keys=True)
            elif to_state.is_failure and current.last_error:
                last_error = json.dumps(current.last_error, sort_keys=True)
            else:
                last_error = None  # leaving failure clears the error
            cur = self.db.execute(
                "UPDATE matches SET state=?, version=version+1, attempt=?, last_error=?, updated_at=? "
                "WHERE match_id=? AND version=?",
                (to_state.value, attempt, last_error, ts, match_id, expected_version),
            )
            if cur.rowcount != 1:
                raise ConcurrencyError(f"match {match_id} changed concurrently")
            body = dict(payload or {})
            if fixture is not None:
                if to_state is not S.FM_STATE_CAPTURED:
                    raise InvalidTransitionError("the fixture may only be replaced when entering FM_STATE_CAPTURED")
                if fixture.fixture_id != current.fixture_id or fixture.career_id != current.career_id:
                    raise InvalidTransitionError("replacement fixture must keep fixture_id and career_id")
                self.db.execute("UPDATE matches SET fixture_json=? WHERE match_id=?",
                                (canonical_json(fixture), match_id))
                body["fixture_rebound"] = True
            if error:
                body["error"] = error
            self.db.execute(
                "INSERT INTO match_transitions(match_id, from_state, to_state, ts, reason, payload) "
                "VALUES (?,?,?,?,?,?)",
                (match_id, current.state.value, to_state.value, ts, reason, json.dumps(body, sort_keys=True)),
            )
            self.db.audit(actor, "match.transition", "match", match_id,
                          {"from": current.state.value, "to": to_state.value, "reason": reason,
                           "attempt": attempt, **({"error": error} if error else {})})
        return self.get(match_id)

    # -- queries -------------------------------------------------------
    def get(self, match_id: str) -> MatchRecord:
        row = self.db.query_one("SELECT * FROM matches WHERE match_id=?", (match_id,))
        if row is None:
            raise KeyError(match_id)
        return self._row_to_record(row)

    def find_live(self, career_id: str, fixture_id: str) -> Optional[MatchRecord]:
        row = self.db.query_one(
            "SELECT * FROM matches WHERE career_id=? AND fixture_id=? AND state != 'ABANDONED'",
            (career_id, fixture_id))
        return self._row_to_record(row) if row else None

    def unfinished(self) -> list[MatchRecord]:
        rows = self.db.query_all(
            "SELECT * FROM matches WHERE state NOT IN ('FM_IMPORT_VERIFIED','ABANDONED') ORDER BY created_at")
        return [self._row_to_record(r) for r in rows]

    def history(self, match_id: str) -> list[Transition]:
        rows = self.db.query_all(
            "SELECT from_state, to_state, ts, reason, payload FROM match_transitions WHERE match_id=? ORDER BY id",
            (match_id,))
        return [Transition(S(r["from_state"]) if r["from_state"] else None, S(r["to_state"]), r["ts"], r["reason"],
                           json.loads(r["payload"])) for r in rows]

    @staticmethod
    def _row_to_record(row: Any) -> MatchRecord:
        return MatchRecord(
            match_id=row["match_id"], career_id=row["career_id"], fixture_id=row["fixture_id"],
            fm_fixture_ref=row["fm_fixture_ref"], state=S(row["state"]), version=row["version"],
            attempt=row["attempt"], fixture=from_primitive(Fixture, json.loads(row["fixture_json"])),
            last_error=json.loads(row["last_error"]) if row["last_error"] else None,
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
