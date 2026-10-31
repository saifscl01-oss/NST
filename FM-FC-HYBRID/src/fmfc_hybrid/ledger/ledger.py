"""Match Event Ledger.

* Events are appended in source order; ``(match_id, source_event_id)`` is
  unique, so re-delivering an event (e.g. a FIFA-side script resending after a
  reconnect) is detected. An identical re-delivery is a no-op; a *different*
  payload under the same id is an error.
* Each row stores a hash chain (``chain_hash = sha256(prev_hash + content)``)
  so any tampering with stored rows is detectable by :meth:`verify`.
* :meth:`finalize` freezes the match: the full :class:`ExternalMatchRecord` is
  stored with its hash and further appends are rejected by a database trigger.
* Corrections after finalization are separate, auditable rows. The original
  events are never changed; :meth:`effective_events` applies corrections.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Iterable, Optional

from ..contracts.models import ExternalMatchRecord, MatchEvent
from ..contracts.serialization import canonical_json, content_hash, from_primitive, to_primitive
from ..errors import DuplicateEventError, LedgerError, LedgerFinalizedError
from ..storage.db import Database, utc_now

GENESIS = "0" * 64


@dataclass(frozen=True)
class AppendResult:
    appended: int
    duplicates_ignored: int


@dataclass(frozen=True)
class Finalization:
    match_id: str
    event_count: int
    head_hash: str
    record_sha256: str
    finalized_at: str


@dataclass(frozen=True)
class Correction:
    id: int
    correction_type: str  # replace_event | void_event | add_event
    target_source_event_id: Optional[str]
    replacement: Optional[MatchEvent]
    reason: str
    author: str
    recorded_at: str


class EventLedger:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- writes --------------------------------------------------------
    def append(self, events: Iterable[MatchEvent], *, actor: str = "bridge") -> AppendResult:
        batch = sorted(events, key=lambda e: e.sequence)
        appended = dupes = 0
        with self.db.transaction():
            for ev in batch:
                if self.is_finalized(ev.match_id):
                    raise LedgerFinalizedError(f"ledger for {ev.match_id} is finalized")
                payload = canonical_json(ev)
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                existing = self.db.query_one(
                    "SELECT content_sha256 FROM ledger_events WHERE match_id=? AND source_event_id=?",
                    (ev.match_id, ev.source_event_id),
                )
                if existing is not None:
                    if existing["content_sha256"] == digest:
                        dupes += 1
                        continue
                    raise DuplicateEventError(
                        f"source event {ev.source_event_id} re-delivered with different content",
                        details={"match_id": ev.match_id, "source_event_id": ev.source_event_id},
                    )
                head = self.db.query_one(
                    "SELECT seq, chain_hash FROM ledger_events WHERE match_id=? ORDER BY seq DESC LIMIT 1",
                    (ev.match_id,),
                )
                if head is not None and ev.sequence <= head["seq"]:
                    raise LedgerError(
                        f"event sequence {ev.sequence} is not after ledger head {head['seq']}",
                        details={"match_id": ev.match_id, "source_event_id": ev.source_event_id},
                    )
                prev = head["chain_hash"] if head is not None else GENESIS
                chain = hashlib.sha256((prev + digest).encode("ascii")).hexdigest()
                self.db.execute(
                    "INSERT INTO ledger_events(match_id, seq, source_event_id, event_json, content_sha256, "
                    "prev_hash, chain_hash, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                    (ev.match_id, ev.sequence, ev.source_event_id, payload, digest, prev, chain, utc_now()),
                )
                appended += 1
            if appended or dupes:
                for mid in sorted({e.match_id for e in batch}):
                    self.db.audit(actor, "ledger.append", "match", mid,
                                  {"appended": appended, "duplicates_ignored": dupes})
        return AppendResult(appended, dupes)

    def finalize(self, record: ExternalMatchRecord, *, actor: str = "bridge") -> Finalization:
        """Freeze the ledger. The record's events must equal the ledger's events."""
        with self.db.transaction():
            existing = self.get_finalization(record.match_id)
            record_json = canonical_json(record)
            record_sha = content_hash(record)
            if existing is not None:
                if existing.record_sha256 == record_sha:
                    return existing  # idempotent re-finalization
                raise LedgerFinalizedError(f"ledger for {record.match_id} already finalized with different record")
            stored = self.events(record.match_id)
            if [canonical_json(e) for e in stored] != [canonical_json(e) for e in
                                                        sorted(record.events, key=lambda e: e.sequence)]:
                raise LedgerError("record events differ from ledger events; append them first",
                                  details={"match_id": record.match_id})
            report = self.verify(record.match_id)
            if not report.ok:
                raise LedgerError(f"ledger integrity check failed: {report.problems}")
            head = self.head_hash(record.match_id)
            ts = utc_now()
            self.db.execute(
                "INSERT INTO ledger_finalizations(match_id, event_count, head_hash, record_json, record_sha256, "
                "finalized_at) VALUES (?,?,?,?,?,?)",
                (record.match_id, len(stored), head, record_json, record_sha, ts),
            )
            self.db.audit(actor, "ledger.finalize", "match", record.match_id,
                          {"event_count": len(stored), "head_hash": head, "record_sha256": record_sha})
        return Finalization(record.match_id, len(stored), head, record_sha, ts)

    def add_correction(self, match_id: str, *, correction_type: str, reason: str, author: str,
                       target_source_event_id: Optional[str] = None,
                       replacement: Optional[MatchEvent] = None) -> Correction:
        if correction_type not in ("replace_event", "void_event", "add_event"):
            raise LedgerError(f"unknown correction type {correction_type}")
        if not self.is_finalized(match_id):
            raise LedgerError("corrections apply only to finalized ledgers; append instead")
        if not reason.strip():
            raise LedgerError("a correction requires a reason")
        known = {e.source_event_id for e in self.events(match_id)}
        if correction_type in ("replace_event", "void_event") and target_source_event_id not in known:
            raise LedgerError(f"correction target {target_source_event_id} not in ledger")
        if correction_type in ("replace_event", "add_event"):
            if replacement is None or replacement.match_id != match_id:
                raise LedgerError("replacement event missing or for another match")
        ts = utc_now()
        with self.db.transaction():
            cur = self.db.execute(
                "INSERT INTO ledger_corrections(match_id, correction_type, target_source_event_id, "
                "replacement_json, reason, author, recorded_at) VALUES (?,?,?,?,?,?,?)",
                (match_id, correction_type, target_source_event_id,
                 canonical_json(replacement) if replacement else None, reason, author, ts),
            )
            self.db.audit(author, "ledger.correction", "match", match_id,
                          {"type": correction_type, "target": target_source_event_id, "reason": reason})
        return Correction(int(cur.lastrowid), correction_type, target_source_event_id, replacement, reason,
                          author, ts)

    # -- reads ---------------------------------------------------------
    def events(self, match_id: str) -> list[MatchEvent]:
        rows = self.db.query_all("SELECT event_json FROM ledger_events WHERE match_id=? ORDER BY seq", (match_id,))
        return [from_primitive(MatchEvent, json.loads(r["event_json"])) for r in rows]

    def corrections(self, match_id: str) -> list[Correction]:
        rows = self.db.query_all("SELECT * FROM ledger_corrections WHERE match_id=? ORDER BY id", (match_id,))
        out = []
        for r in rows:
            rep = from_primitive(MatchEvent, json.loads(r["replacement_json"])) if r["replacement_json"] else None
            out.append(Correction(r["id"], r["correction_type"], r["target_source_event_id"], rep, r["reason"],
                                  r["author"], r["recorded_at"]))
        return out

    def effective_events(self, match_id: str) -> list[MatchEvent]:
        """Original events with corrections applied, in sequence order."""
        by_id = {e.source_event_id: e for e in self.events(match_id)}
        for c in self.corrections(match_id):
            if c.correction_type == "void_event":
                by_id.pop(c.target_source_event_id or "", None)
            elif c.correction_type == "replace_event" and c.replacement is not None:
                by_id.pop(c.target_source_event_id or "", None)
                by_id[c.replacement.source_event_id] = c.replacement
            elif c.correction_type == "add_event" and c.replacement is not None:
                by_id[c.replacement.source_event_id] = c.replacement
        return sorted(by_id.values(), key=lambda e: e.sequence)

    def finalized_record(self, match_id: str, *, with_corrections: bool = True) -> ExternalMatchRecord:
        row = self.db.query_one("SELECT record_json FROM ledger_finalizations WHERE match_id=?", (match_id,))
        if row is None:
            raise LedgerError(f"ledger for {match_id} is not finalized")
        record = from_primitive(ExternalMatchRecord, json.loads(row["record_json"]))
        if with_corrections and self.corrections(match_id):
            record = replace(record, events=tuple(self.effective_events(match_id)))
        return record

    def is_finalized(self, match_id: str) -> bool:
        return self.db.query_one("SELECT 1 FROM ledger_finalizations WHERE match_id=?", (match_id,)) is not None

    def get_finalization(self, match_id: str) -> Optional[Finalization]:
        r = self.db.query_one("SELECT * FROM ledger_finalizations WHERE match_id=?", (match_id,))
        if r is None:
            return None
        return Finalization(r["match_id"], r["event_count"], r["head_hash"], r["record_sha256"], r["finalized_at"])

    def head_hash(self, match_id: str) -> str:
        r = self.db.query_one(
            "SELECT chain_hash FROM ledger_events WHERE match_id=? ORDER BY seq DESC LIMIT 1", (match_id,))
        return r["chain_hash"] if r else GENESIS

    def verify(self, match_id: str) -> "IntegrityReport":
        problems: list[str] = []
        prev = GENESIS
        rows = self.db.query_all(
            "SELECT seq, source_event_id, event_json, content_sha256, prev_hash, chain_hash "
            "FROM ledger_events WHERE match_id=? ORDER BY seq", (match_id,))
        for r in rows:
            digest = hashlib.sha256(r["event_json"].encode("utf-8")).hexdigest()
            if digest != r["content_sha256"]:
                problems.append(f"seq {r['seq']}: content hash mismatch")
            if r["prev_hash"] != prev:
                problems.append(f"seq {r['seq']}: broken chain link")
            expected = hashlib.sha256((r["prev_hash"] + r["content_sha256"]).encode("ascii")).hexdigest()
            if expected != r["chain_hash"]:
                problems.append(f"seq {r['seq']}: chain hash mismatch")
            prev = r["chain_hash"]
        fin = self.get_finalization(match_id)
        if fin is not None:
            if fin.head_hash != prev:
                problems.append("finalization head hash does not match ledger head")
            if fin.event_count != len(rows):
                problems.append("finalization event count does not match ledger")
        return IntegrityReport(match_id, len(rows), not problems, problems)

    def export(self, match_id: str) -> dict:
        """Audit export of the full ledger, finalization and corrections."""
        fin = self.get_finalization(match_id)
        return {
            "match_id": match_id,
            "events": [to_primitive(e) for e in self.events(match_id)],
            "finalization": None if fin is None else fin.__dict__,
            "corrections": [
                {**{k: v for k, v in c.__dict__.items() if k != "replacement"},
                 "replacement": to_primitive(c.replacement) if c.replacement else None}
                for c in self.corrections(match_id)
            ],
            "integrity": self.verify(match_id).__dict__,
        }


@dataclass(frozen=True)
class IntegrityReport:
    match_id: str
    event_count: int
    ok: bool
    problems: list[str]
