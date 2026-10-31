"""Result Processor: finalized external match -> idempotent FM import package.

Also owns the ``imports`` table, the persistent guard that makes a fixture
importable at most once per career, and survives crashes between "FM applied
it" and "bridge recorded it" (see :meth:`ImportGuard.begin`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Optional

from ..adapters.base import ImportReceipt, IntegrationLevel
from ..contracts.models import (
    EventType,
    ExternalMatchRecord,
    Fixture,
    FmImportPackage,
    Period,
    PlayerAppearance,
    Side,
)
from ..contracts.serialization import to_primitive
from ..contracts.validation import validate_match_record
from ..errors import DuplicateImportError, HybridError
from ..storage.db import Database, utc_now


def idempotency_key(career_id: str, fixture_id: str, record_sha256: str) -> str:
    return hashlib.sha256(f"{career_id}|{fixture_id}|{record_sha256}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RatingScale:
    """Linear conversion from the source rating scale to FM's (configurable)."""

    source_min: float = 0.0
    source_max: float = 10.0
    fm_min: float = 1.0
    fm_max: float = 10.0

    def convert(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        t = (value - self.source_min) / (self.source_max - self.source_min)
        t = max(0.0, min(1.0, t))
        return round(self.fm_min + t * (self.fm_max - self.fm_min), 1)


class ResultProcessor:
    def __init__(self, rating_scale: RatingScale | None = None) -> None:
        self.rating_scale = rating_scale or RatingScale()

    def build_package(self, fixture: Fixture, record: ExternalMatchRecord, record_sha256: str,
                      fm_id_of: Callable[[str], int]) -> FmImportPackage:
        issues, replay = validate_match_record(fixture, record)
        issues.raise_if_errors(f"match {record.match_id} failed validation; cannot build FM package")
        st = replay.state
        stats_by_player = {ps.hybrid_player_id: ps for ps in record.player_stats}
        starters = {s.hybrid_player_id for side in (Side.HOME, Side.AWAY) for s in fixture.squad(side).starters}

        appearances = []
        for side in (Side.HOME, Side.AWAY):
            for pid in fixture.squad(side).all_player_ids():
                if not replay.appeared(pid):
                    continue
                ps = stats_by_player.get(pid)
                appearances.append(PlayerAppearance(
                    hybrid_player_id=pid,
                    fm_player_id=fm_id_of(pid),
                    side=side,
                    started=pid in starters,
                    minutes_played=replay.minutes_played(pid),
                    goals=st.goals[pid],
                    assists=st.assists[pid],
                    own_goals=st.own_goals[pid],
                    yellow_cards=min(st.yellow[pid], 2),
                    red_card=pid in st.dismissed,
                    injured=pid in st.injured,
                    rating=self.rating_scale.convert(ps.rating if ps else None),
                ))
        shootout = Period.PENALTY_SHOOTOUT in st.periods_seen
        return FmImportPackage(
            idempotency_key=idempotency_key(fixture.career_id, fixture.fixture_id, record_sha256),
            career_id=fixture.career_id,
            fixture_id=fixture.fixture_id,
            fm_fixture_ref=fixture.fm_fixture_ref,
            home_goals=st.score[Side.HOME],
            away_goals=st.score[Side.AWAY],
            events=tuple(e for e in sorted(record.events, key=lambda e: e.sequence)
                         if e.type not in (EventType.PERIOD_START,)),
            appearances=tuple(appearances),
            team_stats=record.team_stats,
            ledger_hash=record_sha256,
            shootout_home=st.shootout[Side.HOME] if shootout else None,
            shootout_away=st.shootout[Side.AWAY] if shootout else None,
        )


class ImportGuard:
    """Persistent once-only import protocol.

    ``begin`` must be called (and committed) *before* the FM adapter is asked
    to apply anything. If the bridge crashes afterwards, recovery sees a
    ``pending`` row and must ask FM (``lookup_import``) before re-applying.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def status(self, career_id: str, fixture_id: str) -> Optional[dict]:
        row = self.db.query_one("SELECT * FROM imports WHERE career_id=? AND fixture_id=?", (career_id, fixture_id))
        return dict(row) if row else None

    def begin(self, package: FmImportPackage, match_id: str) -> str:
        """Returns 'new' or 'resume'. Raises DuplicateImportError if already applied."""
        with self.db.transaction():
            row = self.status(package.career_id, package.fixture_id)
            if row is None:
                now = utc_now()
                self.db.execute(
                    "INSERT INTO imports(career_id, fixture_id, match_id, idempotency_key, status, created_at, "
                    "updated_at) VALUES (?,?,?,?, 'pending', ?, ?)",
                    (package.career_id, package.fixture_id, match_id, package.idempotency_key, now, now))
                self._log(package.idempotency_key, "begin")
                return "new"
            if row["status"] in ("completed", "verified"):
                raise DuplicateImportError(
                    f"fixture {package.fixture_id} already imported ({row['status']})",
                    details={"idempotency_key": row["idempotency_key"]})
            if row["idempotency_key"] != package.idempotency_key:
                raise DuplicateImportError(
                    f"fixture {package.fixture_id} has an unresolved import of a different match record",
                    details={"existing_key": row["idempotency_key"], "new_key": package.idempotency_key})
            if row["status"] == "failed":
                self.db.execute("UPDATE imports SET status='pending', updated_at=? WHERE idempotency_key=?",
                                (utc_now(), package.idempotency_key))
            self._log(package.idempotency_key, "resume")
            return "resume"

    def complete(self, receipt: ImportReceipt) -> None:
        self._set(receipt.idempotency_key, "completed", receipt)

    def verified(self, key: str) -> None:
        self._set(key, "verified")

    def failed(self, key: str, error: HybridError) -> None:
        self._set(key, "failed", detail=error.to_dict())

    def receipt(self, career_id: str, fixture_id: str) -> Optional[dict]:
        row = self.status(career_id, fixture_id)
        return json.loads(row["receipt_json"]) if row and row["receipt_json"] else None

    def _set(self, key: str, status: str, receipt: ImportReceipt | None = None, detail: dict | None = None) -> None:
        with self.db.transaction():
            if receipt is not None:
                body = json.dumps({**to_primitive(receipt),
                                   "integration_level_name": receipt.integration_level.name}, sort_keys=True)
                cur = self.db.execute(
                    "UPDATE imports SET status=?, receipt_json=?, updated_at=? WHERE idempotency_key=?",
                    (status, body, utc_now(), key))
            else:
                cur = self.db.execute("UPDATE imports SET status=?, updated_at=? WHERE idempotency_key=?",
                                      (status, utc_now(), key))
            if cur.rowcount != 1:
                raise HybridError(f"no import row for key {key}")
            self._log(key, status, detail)

    def _log(self, key: str, action: str, detail: dict | None = None) -> None:
        self.db.execute("INSERT INTO import_attempts_log(idempotency_key, action, detail, ts) VALUES (?,?,?,?)",
                        (key, action, json.dumps(detail or {}, sort_keys=True), utc_now()))


def integration_summary(level: IntegrationLevel) -> str:
    if level.is_full_integration:
        return "FULL: FM natively processed the external match"
    return f"PARTIAL ({level.name}): not full integration"
