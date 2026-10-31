"""Persistent player identity registry.

FM is the authority on who a player *is*. The registry assigns each FM player a
**Hybrid Player ID** the first time he is seen in a career and never changes
it: transfers, retirements and re-captures update the record, they never
create a new identity. FIFA ids are links that can be added, refreshed or
marked stale, but a FIFA id once allocated by the bridge is never reused for
another player in the same career.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from ..contracts.models import FifaLinkStatus, PlayerProfile
from ..contracts.serialization import canonical_json, content_hash, from_primitive
from ..errors import IdentityError
from ..storage.db import Database, utc_now


@dataclass(frozen=True)
class FifaIdPolicy:
    """Where bridge-created FIFA players get their ids.

    The real safe range depends on the chosen FIFA version's database and is
    UNKNOWN until verified locally (see docs/PLAYER_MAPPING.md); it therefore
    comes from configuration, never from code.
    """

    range_start: int
    range_end: int

    def __post_init__(self) -> None:
        if not 0 < self.range_start <= self.range_end:
            raise ValueError("invalid FIFA id range")


@dataclass(frozen=True)
class PlayerRecord:
    hybrid_player_id: str
    career_id: str
    fm_player_id: int
    fifa_player_id: Optional[int]
    fifa_link_status: FifaLinkStatus
    status: str  # active | retired
    profile: PlayerProfile
    profile_sha256: str
    created_at: str
    last_synced_at: str
    last_fifa_sync_at: Optional[str]


class PlayerRegistry:
    def __init__(self, db: Database, career_id: str, fifa_policy: Optional[FifaIdPolicy] = None) -> None:
        if not career_id:
            raise IdentityError("career_id is required")
        self.db = db
        self.career_id = career_id
        self.fifa_policy = fifa_policy

    # -- registration --------------------------------------------------
    def register(self, profile: PlayerProfile, *, reason: str = "fm_capture", actor: str = "bridge") -> PlayerRecord:
        """Insert or refresh a player from an FM capture. Returns the stable record."""
        digest = content_hash(profile)
        now = utc_now()
        with self.db.transaction():
            existing = self.get_by_fm(profile.fm_player_id)
            if existing is None:
                hybrid_id = f"HP-{uuid.uuid4().hex[:20]}"
                self.db.execute(
                    "INSERT INTO players(hybrid_player_id, career_id, fm_player_id, fifa_player_id, "
                    "fifa_link_status, display_name, date_of_birth, origin, club_fm_id, primary_position, status, "
                    "profile_json, profile_sha256, created_at, last_synced_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (hybrid_id, self.career_id, profile.fm_player_id, None, FifaLinkStatus.UNLINKED.value,
                     profile.display_name, profile.date_of_birth, profile.origin.value, profile.club_fm_id,
                     _primary_position(profile), "active", canonical_json(profile), digest, now, now),
                )
                self._snapshot(hybrid_id, profile, digest, f"created:{reason}")
                self.db.audit(actor, "player.register", "player", hybrid_id,
                              {"fm_player_id": profile.fm_player_id, "origin": profile.origin.value})
                return self.get(hybrid_id)

            if existing.profile.date_of_birth != profile.date_of_birth:
                # Same FM id but a different person would corrupt identity; refuse loudly.
                raise IdentityError(
                    f"FM player {profile.fm_player_id} changed date of birth; refusing to merge identities",
                    details={"hybrid_player_id": existing.hybrid_player_id})
            if digest == existing.profile_sha256:
                self.db.execute("UPDATE players SET last_synced_at=? WHERE hybrid_player_id=?",
                                (now, existing.hybrid_player_id))
                return self.get(existing.hybrid_player_id)

            link = existing.fifa_link_status
            if link in (FifaLinkStatus.MATCHED, FifaLinkStatus.CREATED):
                link = FifaLinkStatus.STALE  # FIFA copy no longer reflects FM
            self.db.execute(
                "UPDATE players SET display_name=?, club_fm_id=?, primary_position=?, profile_json=?, "
                "profile_sha256=?, last_synced_at=?, fifa_link_status=? WHERE hybrid_player_id=?",
                (profile.display_name, profile.club_fm_id, _primary_position(profile), canonical_json(profile),
                 digest, now, link.value, existing.hybrid_player_id),
            )
            self._snapshot(existing.hybrid_player_id, profile, digest, reason)
            changes = _diff_profiles(existing.profile, profile)
            self.db.audit(actor, "player.update", "player", existing.hybrid_player_id, {"changes": changes})
            return self.get(existing.hybrid_player_id)

    def register_many(self, profiles: Iterable[PlayerProfile], **kw) -> list[PlayerRecord]:
        with self.db.transaction():
            return [self.register(p, **kw) for p in profiles]

    # -- FIFA links ----------------------------------------------------
    def link_fifa(self, hybrid_id: str, fifa_player_id: int, *, status: FifaLinkStatus = FifaLinkStatus.MATCHED,
                  relink: bool = False, actor: str = "bridge") -> PlayerRecord:
        if status not in (FifaLinkStatus.MATCHED, FifaLinkStatus.CREATED):
            raise IdentityError("link status must be MATCHED or CREATED")
        with self.db.transaction():
            rec = self.get(hybrid_id)
            if rec.fifa_player_id is not None and rec.fifa_player_id != fifa_player_id and not relink:
                raise IdentityError(f"{hybrid_id} already linked to FIFA id {rec.fifa_player_id}")
            other = self.get_by_fifa(fifa_player_id)
            if other is not None and other.hybrid_player_id != hybrid_id:
                raise IdentityError(f"FIFA id {fifa_player_id} already belongs to {other.hybrid_player_id}")
            allocated = self.db.query_one(
                "SELECT hybrid_player_id FROM fifa_id_allocations WHERE career_id=? AND fifa_player_id=?",
                (self.career_id, fifa_player_id))
            if allocated is not None and allocated["hybrid_player_id"] != hybrid_id:
                raise IdentityError(f"FIFA id {fifa_player_id} was allocated to {allocated['hybrid_player_id']}")
            try:
                self.db.execute(
                    "UPDATE players SET fifa_player_id=?, fifa_link_status=? WHERE hybrid_player_id=?",
                    (fifa_player_id, status.value, hybrid_id))
            except sqlite3.IntegrityError as exc:
                raise IdentityError(f"cannot link FIFA id {fifa_player_id}: {exc}") from exc
            self.db.audit(actor, "player.link_fifa", "player", hybrid_id,
                          {"fifa_player_id": fifa_player_id, "status": status.value,
                           "previous": rec.fifa_player_id})
        return self.get(hybrid_id)

    def allocate_fifa_id(self, hybrid_id: str, *, occupied: Callable[[int], bool] = lambda _id: False,
                         actor: str = "bridge") -> PlayerRecord:
        """Allocate a never-before-used FIFA id for a player FIFA does not know.

        ``occupied`` lets the FIFA adapter veto ids already present in the
        game's database (the registry cannot know those on its own).
        """
        if self.fifa_policy is None:
            raise IdentityError("no FIFA id policy configured")
        with self.db.transaction():
            rec = self.get(hybrid_id)
            if rec.fifa_player_id is not None:
                return rec
            row = self.db.query_one(
                "SELECT MAX(fifa_player_id) AS m FROM fifa_id_allocations WHERE career_id=? "
                "AND fifa_player_id BETWEEN ? AND ?",
                (self.career_id, self.fifa_policy.range_start, self.fifa_policy.range_end))
            candidate = (row["m"] + 1) if row and row["m"] is not None else self.fifa_policy.range_start
            while candidate <= self.fifa_policy.range_end and (occupied(candidate) or self.get_by_fifa(candidate)):
                candidate += 1
            if candidate > self.fifa_policy.range_end:
                raise IdentityError("FIFA id range exhausted", details={"range_end": self.fifa_policy.range_end})
            self.db.execute(
                "INSERT INTO fifa_id_allocations(career_id, fifa_player_id, hybrid_player_id, allocated_at) "
                "VALUES (?,?,?,?)", (self.career_id, candidate, hybrid_id, utc_now()))
            self.db.audit(actor, "player.allocate_fifa_id", "player", hybrid_id, {"fifa_player_id": candidate})
            return self.link_fifa(hybrid_id, candidate, status=FifaLinkStatus.CREATED, actor=actor)

    def mark_fifa_synced(self, hybrid_id: str, *, actor: str = "bridge") -> PlayerRecord:
        with self.db.transaction():
            rec = self.get(hybrid_id)
            if rec.fifa_player_id is None:
                raise IdentityError(f"{hybrid_id} has no FIFA link to sync")
            status = rec.fifa_link_status
            if status is FifaLinkStatus.STALE:
                created = self.db.query_one(
                    "SELECT 1 FROM fifa_id_allocations WHERE career_id=? AND hybrid_player_id=?",
                    (self.career_id, hybrid_id))
                status = FifaLinkStatus.CREATED if created else FifaLinkStatus.MATCHED
            self.db.execute(
                "UPDATE players SET fifa_link_status=?, last_fifa_sync_at=? WHERE hybrid_player_id=?",
                (status.value, utc_now(), hybrid_id))
            self.db.audit(actor, "player.fifa_synced", "player", hybrid_id, {"profile_sha256": rec.profile_sha256})
        return self.get(hybrid_id)

    # -- lifecycle events ----------------------------------------------
    def retire(self, hybrid_id: str, *, actor: str = "bridge") -> PlayerRecord:
        with self.db.transaction():
            self.get(hybrid_id)
            self.db.execute("UPDATE players SET status='retired' WHERE hybrid_player_id=?", (hybrid_id,))
            self.db.audit(actor, "player.retire", "player", hybrid_id, {})
        return self.get(hybrid_id)

    # -- queries -------------------------------------------------------
    def get(self, hybrid_id: str) -> PlayerRecord:
        row = self.db.query_one("SELECT * FROM players WHERE hybrid_player_id=? AND career_id=?",
                                (hybrid_id, self.career_id))
        if row is None:
            raise IdentityError(f"unknown hybrid player {hybrid_id}")
        return _row(row)

    def get_by_fm(self, fm_player_id: int) -> Optional[PlayerRecord]:
        row = self.db.query_one("SELECT * FROM players WHERE career_id=? AND fm_player_id=?",
                                (self.career_id, fm_player_id))
        return _row(row) if row else None

    def get_by_fifa(self, fifa_player_id: int) -> Optional[PlayerRecord]:
        row = self.db.query_one("SELECT * FROM players WHERE career_id=? AND fifa_player_id=?",
                                (self.career_id, fifa_player_id))
        return _row(row) if row else None

    def needing_fifa_sync(self) -> list[PlayerRecord]:
        rows = self.db.query_all(
            "SELECT * FROM players WHERE career_id=? AND status='active' AND fifa_link_status IN ('unlinked','stale')",
            (self.career_id,))
        return [_row(r) for r in rows]

    def snapshot_history(self, hybrid_id: str) -> list[tuple[str, str, PlayerProfile]]:
        rows = self.db.query_all(
            "SELECT captured_at, reason, profile_json FROM player_snapshots WHERE hybrid_player_id=? ORDER BY id",
            (hybrid_id,))
        return [(r["captured_at"], r["reason"], from_primitive(PlayerProfile, json.loads(r["profile_json"])))
                for r in rows]

    def _snapshot(self, hybrid_id: str, profile: PlayerProfile, digest: str, reason: str) -> None:
        self.db.execute(
            "INSERT INTO player_snapshots(hybrid_player_id, profile_json, profile_sha256, reason, captured_at) "
            "VALUES (?,?,?,?,?)", (hybrid_id, canonical_json(profile), digest, reason, utc_now()))


def _primary_position(profile: PlayerProfile) -> Optional[str]:
    if not profile.positions:
        return None
    return max(sorted(profile.positions.items()), key=lambda kv: kv[1])[0]


def _diff_profiles(old: PlayerProfile, new: PlayerProfile) -> dict[str, list]:
    changes: dict[str, list] = {}
    if old.club_fm_id != new.club_fm_id:
        changes["club_fm_id"] = [old.club_fm_id, new.club_fm_id]
    if old.display_name != new.display_name:
        changes["display_name"] = [old.display_name, new.display_name]
    o, n = old.attributes.all_visible(), new.attributes.all_visible()
    for key in sorted(set(o) | set(n)):
        if o.get(key) != n.get(key):
            changes[f"attr.{key}"] = [o.get(key), n.get(key)]
    if old.attributes.current_ability != new.attributes.current_ability:
        changes["current_ability"] = [old.attributes.current_ability, new.attributes.current_ability]
    return changes


def _row(row) -> PlayerRecord:
    return PlayerRecord(
        hybrid_player_id=row["hybrid_player_id"], career_id=row["career_id"], fm_player_id=row["fm_player_id"],
        fifa_player_id=row["fifa_player_id"], fifa_link_status=FifaLinkStatus(row["fifa_link_status"]),
        status=row["status"], profile=from_primitive(PlayerProfile, json.loads(row["profile_json"])),
        profile_sha256=row["profile_sha256"], created_at=row["created_at"], last_synced_at=row["last_synced_at"],
        last_fifa_sync_at=row["last_fifa_sync_at"],
    )
