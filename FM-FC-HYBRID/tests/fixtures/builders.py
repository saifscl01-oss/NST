"""Hand-built, deterministic test data (no game data involved)."""
from __future__ import annotations

from fmfc_hybrid.contracts.models import (
    ClubRef, CompetitionRef, EventType, ExternalMatchRecord, Fixture, LineupSlot, MatchClock, MatchdaySquad,
    MatchEvent, MatchRules, Period, PlayerMatchStats, Side, TeamMatchStats,
)

POSITIONS = ["GK", "DR", "DC", "DC", "DL", "DM", "MC", "MC", "AMR", "AML", "ST"]
MATCH = "M-test:1"


def squad(prefix: str, club_id: int, bench: int = 7) -> MatchdaySquad:
    starters = tuple(LineupSlot(i, f"{prefix}{i}", pos) for i, pos in enumerate(POSITIONS))
    return MatchdaySquad(ClubRef(f"HC-{club_id}", club_id, f"Club {club_id}"), starters,
                         tuple(f"{prefix}b{i}" for i in range(bench)), captain_id=f"{prefix}2")


def fixture(**rules) -> Fixture:
    return Fixture("FX-test", "career-test", "fm-ref-1", CompetitionRef(1, "Test League"), "2026-08-10T15:00:00",
                   squad("h", 1), squad("a", 2), Side.HOME, MatchRules(**rules))


class Events:
    """Fluent builder producing sequential MatchEvents."""

    def __init__(self, match_id: str = MATCH) -> None:
        self.match_id = match_id
        self.items: list[MatchEvent] = []

    def add(self, etype: EventType, minute: int, side=None, pid=None, pid2=None, period=None, added=0, **detail):
        if period is None:
            period = Period.FIRST_HALF if minute <= 45 and not (minute == 45 and etype is EventType.PERIOD_START) \
                else Period.SECOND_HALF
        seq = len(self.items) + 1
        self.items.append(MatchEvent(self.match_id, f"e{seq}", seq, MatchClock(period, minute, added), etype,
                                     side, pid, pid2, detail))
        return self

    def full_time(self, minute: int = 90, added: int = 3):
        return self.add(EventType.FULL_TIME, minute, period=Period.SECOND_HALF, added=added)


def record(events: list[MatchEvent], home: int, away: int, completed: bool = True,
           player_stats=()) -> ExternalMatchRecord:
    return ExternalMatchRecord(MATCH, "FX-test", "unit-test", "1", tuple(events), tuple(player_stats),
                               (TeamMatchStats(Side.HOME, home), TeamMatchStats(Side.AWAY, away)), completed)


def simple_match():
    """1-1 with an assist, a sub and a booking."""
    ev = (Events()
          .add(EventType.GOAL, 12, Side.HOME, "h10", "h9")
          .add(EventType.YELLOW_CARD, 30, Side.AWAY, "a5")
          .add(EventType.SUBSTITUTION, 60, Side.HOME, "h9", "hb0")
          .add(EventType.GOAL, 75, Side.AWAY, "a10")
          .full_time())
    return ev.items
