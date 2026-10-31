"""In-memory stand-in for the FIFA match engine.

Generates a deterministic, football-consistent match (respecting who is on the
pitch, substitution limits and dismissals) from the prepared squads, and
exposes it through the same streaming/collection protocol a real FIFA adapter
must implement. It says nothing about how FIFA itself works.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Optional

from ..contracts.models import (
    EventType,
    ExternalMatchRecord,
    MatchClock,
    MatchEvent,
    Period,
    PlayerMatchStats,
    Side,
    TeamMatchStats,
)
from ..errors import DataCaptureError, LaunchError, MatchInterruptedError, PreparationError
from ..storage.db import utc_now
from .base import ControlMode, FifaCapabilities, FifaMatchRequest, PreparationReceipt


@dataclass
class _Prepared:
    request: FifaMatchRequest
    events: list[MatchEvent] = field(default_factory=list)
    record: Optional[ExternalMatchRecord] = None
    launched: bool = False


class MockFifa:
    name = "mock-fifa"

    def __init__(self, *, seed: int = 11) -> None:
        self.seed = seed
        self.faults: set[str] = set()
        self.created_players: dict[int, str] = {}  # fifa id -> hybrid id
        self.matches: dict[str, _Prepared] = {}

    def capabilities(self) -> FifaCapabilities:
        return FifaCapabilities(create_players=True, edit_player_attributes=True, set_lineups=True,
                                set_team_tactics=True, set_player_instructions=True, launch_match=True,
                                user_control=True, ai_vs_ai=True, stream_events=True, capture_player_stats=True,
                                capture_team_stats=True, detect_full_time=True,
                                evidence={"all": "MOCK - test double, not evidence about FIFA"})

    # -- preparation -------------------------------------------------------
    def prepare_match(self, request: FifaMatchRequest) -> PreparationReceipt:
        if "prepare_fail_once" in self.faults:
            self.faults.discard("prepare_fail_once")
            raise PreparationError("mock FIFA could not write squads", retryable=True)
        specs = {p.hybrid_player_id: p for p in request.players}
        needed = [pid for t in (request.home, request.away) for pid in [s[0] for s in t.starters] + list(t.bench)]
        missing = [pid for pid in needed if pid not in specs]
        if missing:
            raise PreparationError(f"no player spec for {missing[:3]}")
        created, updated = [], []
        for spec in request.players:
            owner = self.created_players.get(spec.fifa_player_id)
            if owner is not None and owner != spec.hybrid_player_id:
                raise PreparationError(f"FIFA id {spec.fifa_player_id} already used by {owner}")
            (created if owner is None else updated).append(spec.hybrid_player_id)
            self.created_players[spec.fifa_player_id] = spec.hybrid_player_id
        self.matches[request.ledger_match_id] = _Prepared(request)
        return PreparationReceipt(request.ledger_match_id, tuple(created), tuple(updated))

    def launch_match(self, ledger_match_id: str) -> None:
        prepared = self.matches.get(ledger_match_id)
        if prepared is None:
            raise LaunchError(f"match {ledger_match_id} was not prepared")
        if "launch_fail_once" in self.faults:
            self.faults.discard("launch_fail_once")
            raise LaunchError("mock FIFA failed to start", retryable=True)
        prepared.launched = True
        prepared.events, prepared.record = self._simulate(prepared.request)

    def poll_events(self, ledger_match_id: str, after_sequence: int) -> list[MatchEvent]:
        prepared = self.matches[ledger_match_id]
        return [e for e in prepared.events if e.sequence > after_sequence]

    def collect_result(self, ledger_match_id: str) -> ExternalMatchRecord:
        prepared = self.matches.get(ledger_match_id)
        if prepared is None or not prepared.launched or prepared.record is None:
            raise DataCaptureError(f"no running match {ledger_match_id}")
        if "interrupt_once" in self.faults:
            self.faults.discard("interrupt_once")
            raise MatchInterruptedError("mock FIFA match quit before full time")
        if "capture_fail_once" in self.faults:
            self.faults.discard("capture_fail_once")
            raise DataCaptureError("mock FIFA stats export failed", retryable=True)
        record = prepared.record
        if "drop_full_time" in self.faults:
            from dataclasses import replace
            record = replace(record, events=tuple(e for e in record.events if e.type is not EventType.FULL_TIME))
        return record

    def has_completed_record(self, ledger_match_id: str) -> bool:
        p = self.matches.get(ledger_match_id)
        return bool(p and p.record is not None and "interrupt_once" not in self.faults)

    # -- simulation ----------------------------------------------------------
    def _simulate(self, req: FifaMatchRequest) -> tuple[list[MatchEvent], ExternalMatchRecord]:
        digest = hashlib.sha256(f"{self.seed}|{req.ledger_match_id}".encode()).hexdigest()
        rng = random.Random(int(digest[:12], 16))
        mid = req.ledger_match_id
        specs = {p.hybrid_player_id: p for p in req.players}
        teams = {Side.HOME: req.home, Side.AWAY: req.away}
        on_pitch = {s: [pid for pid, _ in teams[s].starters] for s in teams}
        bench = {s: list(teams[s].bench) for s in teams}
        gk = {s: next(pid for pid, pos in teams[s].starters if pos == "GK") for s in teams}
        subs_used = {s: 0 for s in teams}
        yellow: dict[str, int] = {}
        events: list[MatchEvent] = []
        seq = 0

        def emit(clock: MatchClock, etype: EventType, side: Optional[Side] = None, pid: Optional[str] = None,
                 pid2: Optional[str] = None, **detail) -> None:
            nonlocal seq
            seq += 1
            events.append(MatchEvent(mid, f"mock-{seq:04d}", seq, clock, etype, side, pid, pid2, dict(detail)))

        strength = {s: sum(sum(specs[p].attributes.values()) for p, _ in teams[s].starters) for s in teams}
        home_share = strength[Side.HOME] / (strength[Side.HOME] + strength[Side.AWAY])

        # Build a sorted timeline of happenings, then play it forward with state checks.
        timeline: list[tuple[Period, int, str, Side, int]] = []
        for period, lo, hi in ((Period.FIRST_HALF, 1, 45), (Period.SECOND_HALF, 46, 90)):
            for _ in range(rng.randint(0, 3)):
                timeline.append((period, rng.randint(lo, hi), "goal",
                                 Side.HOME if rng.random() < home_share + 0.05 else Side.AWAY, rng.randint(0, 59)))
            for _ in range(rng.randint(0, 2)):
                timeline.append((period, rng.randint(lo, hi), "yellow", rng.choice([Side.HOME, Side.AWAY]),
                                 rng.randint(0, 59)))
        for side in (Side.HOME, Side.AWAY):
            for minute in sorted(rng.sample(range(58, 86), 3)):
                timeline.append((Period.SECOND_HALF, minute, "sub", side, rng.randint(0, 59)))
        if rng.random() < 0.15:
            timeline.append((Period.SECOND_HALF, rng.randint(50, 88), "injury", rng.choice([Side.HOME, Side.AWAY]),
                             rng.randint(0, 59)))
        timeline.sort(key=lambda t: (t[0].order, t[1], t[4]))

        emit(MatchClock(Period.FIRST_HALF, 0), EventType.PERIOD_START)
        stats: dict[str, dict[str, float]] = {}
        half_end_emitted = False
        for period, minute, kind, side, second in timeline:
            if period is Period.SECOND_HALF and not half_end_emitted:
                emit(MatchClock(Period.FIRST_HALF, 45, rng.randint(1, 3)), EventType.PERIOD_END)
                emit(MatchClock(Period.SECOND_HALF, 45), EventType.PERIOD_START)
                half_end_emitted = True
            clock = MatchClock(period, minute, 0, second)
            outfield = [p for p in on_pitch[side] if p != gk[side]]
            if kind == "goal" and outfield:
                scorer = rng.choice(outfield)
                mates = [p for p in outfield if p != scorer]
                assister = rng.choice(mates) if mates and rng.random() < 0.7 else None
                emit(clock, EventType.GOAL, side, scorer, assister)
                stats.setdefault(scorer, {}).setdefault("goals", 0)
                stats[scorer]["goals"] += 1
                if assister:
                    stats.setdefault(assister, {}).setdefault("assists", 0)
                    stats[assister]["assists"] += 1
            elif kind == "yellow" and outfield:
                pid = rng.choice(outfield)
                if yellow.get(pid):
                    emit(clock, EventType.SECOND_YELLOW, side, pid)
                    on_pitch[side].remove(pid)
                else:
                    yellow[pid] = 1
                    emit(clock, EventType.YELLOW_CARD, side, pid)
            elif kind in ("sub", "injury") and outfield and bench[side] and subs_used[side] < 3:
                off = rng.choice(outfield)
                if kind == "injury":
                    emit(clock, EventType.INJURY, side, off, severity="minor", forced_off=True)
                on = bench[side].pop(0)
                emit(clock, EventType.SUBSTITUTION, side, off, on)
                on_pitch[side].remove(off)
                on_pitch[side].append(on)
                subs_used[side] += 1
        if not half_end_emitted:
            emit(MatchClock(Period.FIRST_HALF, 45, 1), EventType.PERIOD_END)
            emit(MatchClock(Period.SECOND_HALF, 45), EventType.PERIOD_START)
        emit(MatchClock(Period.SECOND_HALF, 90, rng.randint(1, 5)), EventType.FULL_TIME)

        score = {Side.HOME: 0, Side.AWAY: 0}
        participants: dict[str, Side] = {}
        for s in teams:
            for pid, _ in teams[s].starters:
                participants[pid] = s
        for e in events:
            if e.type is EventType.GOAL and e.side is not None:
                score[e.side] += 1
            if e.type is EventType.SUBSTITUTION and e.secondary_player_id and e.side is not None:
                participants[e.secondary_player_id] = e.side

        player_stats = []
        for pid, s in participants.items():
            g = int(stats.get(pid, {}).get("goals", 0))
            a = int(stats.get(pid, {}).get("assists", 0))
            shots = g + rng.randint(0, 3)
            passes = rng.randint(15, 70)
            player_stats.append(PlayerMatchStats(
                hybrid_player_id=pid, side=s, rating=round(min(10.0, rng.uniform(5.8, 7.6) + 0.8 * g + 0.4 * a), 1),
                goals=g, assists=a, shots=shots, shots_on_target=min(shots, g + rng.randint(0, 2)),
                passes_attempted=passes, passes_completed=int(passes * rng.uniform(0.7, 0.92)),
                tackles=rng.randint(0, 5), interceptions=rng.randint(0, 4),
                saves=rng.randint(1, 6) if pid == gk[s] else 0))
        home_pos = round(40 + 20 * home_share + rng.uniform(-5, 5), 1)
        team_stats = []
        for s, pos in ((Side.HOME, home_pos), (Side.AWAY, round(100 - home_pos, 1))):
            mine = [p for p in player_stats if p.side is s]
            team_stats.append(TeamMatchStats(
                side=s, goals=score[s], possession_pct=pos, shots=sum(p.shots for p in mine),
                shots_on_target=sum(p.shots_on_target for p in mine), corners=rng.randint(1, 9),
                fouls=rng.randint(6, 16), passes_attempted=sum(p.passes_attempted for p in mine),
                passes_completed=sum(p.passes_completed for p in mine)))
        user_side = req.fixture.managed_side if req.control_mode is ControlMode.USER_CONTROLS_MANAGED_SIDE else None
        record = ExternalMatchRecord(
            match_id=mid, fixture_id=req.fixture.fixture_id, source=self.name, source_version="mock-1",
            events=tuple(events), player_stats=tuple(player_stats), team_stats=tuple(team_stats),
            completed_normally=True, rating_scale="0-10", user_controlled_side=user_side, captured_at=utc_now())
        return events, record
