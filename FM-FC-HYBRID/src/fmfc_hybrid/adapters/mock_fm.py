"""In-memory stand-in for Football Manager.

This is a *test double*, not a model of FM's real internals. It provides a tiny
consistent football world (clubs, players, fixtures, a league table, season
stats, morale, suspensions, injuries) so the bridge's full lifecycle, including
"FM applies the result and its consequences", can be exercised without FM.

Fault injection (``faults``) simulates the failure modes the bridge must
survive. ``SimulatedCrash`` derives from BaseException so the orchestrator's
error handling does not swallow it, imitating a process crash.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..contracts.models import (
    Appearance,
    AttributeSnapshot,
    ClubRef,
    CompetitionRef,
    Duty,
    Fixture,
    FmImportPackage,
    LineupSlot,
    MatchdaySquad,
    MatchRules,
    PlayerOrigin,
    PlayerProfile,
    RoleAssignment,
    Side,
    TacticalPlan,
)
from ..storage.db import utc_now
from .base import (
    FmCapabilities,
    FmMatchContext,
    ImportReceipt,
    IntegrationLevel,
    VerificationCheck,
    VerificationReport,
)
from .ids import fm_ref, stable_fixture_id
from ..errors import AdapterError, DataCaptureError, DuplicateImportError, ImportFailedError


class SimulatedCrash(BaseException):
    """Simulates the bridge process dying at a precise point."""


TECHNICAL = ["corners", "crossing", "dribbling", "finishing", "first_touch", "free_kick_taking", "heading",
             "long_shots", "marking", "passing", "penalty_taking", "tackling", "technique"]
MENTAL = ["aggression", "anticipation", "bravery", "composure", "concentration", "decisions", "flair",
          "off_the_ball", "positioning", "teamwork", "vision", "work_rate"]
PHYSICAL = ["acceleration", "agility", "balance", "jumping_reach", "natural_fitness", "pace", "stamina",
            "strength"]
GOALKEEPING = ["aerial_reach", "command_of_area", "handling", "kicking", "one_on_ones", "reflexes"]

# 4-2-3-1 used by every mock club: (slot, FM position, FM role, duty)
MOCK_SHAPE = [
    (0, "GK", "goalkeeper", Duty.DEFEND), (1, "DR", "wing_back", Duty.SUPPORT),
    (2, "DC", "central_defender", Duty.DEFEND), (3, "DC", "ball_playing_defender", Duty.DEFEND),
    (4, "DL", "inverted_wing_back", Duty.SUPPORT), (5, "DM", "half_back", Duty.DEFEND),
    (6, "DM", "segundo_volante", Duty.ATTACK), (7, "AMR", "inside_forward", Duty.ATTACK),
    (8, "AMC", "trequartista", Duty.ATTACK), (9, "AML", "inside_forward", Duty.SUPPORT),
    (10, "ST", "pressing_forward", Duty.ATTACK),
]
SQUAD_POSITIONS = [p for _, p, _, _ in MOCK_SHAPE] + ["GK", "DC", "DR", "DM", "MC", "AMC", "AML", "ST", "MC"]


@dataclass
class MockClub:
    fm_club_id: int
    name: str
    player_ids: list[int]
    morale: float = 0.5


@dataclass
class MockFixtureRecord:
    ref: str
    home_club: int
    away_club: int
    kickoff: str
    result: Optional[tuple[int, int]] = None
    import_key: Optional[str] = None
    import_count: int = 0
    receipt: Optional[ImportReceipt] = None


@dataclass
class SeasonStats:
    appearances: int = 0
    starts: int = 0
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    ratings: list[float] = field(default_factory=list)


class MockFootballManager:
    name = "mock-fm"

    def __init__(self, career_id: str = "career-mock", *, seed: int = 7, n_clubs: int = 4,
                 max_level: IntegrationLevel = IntegrationLevel.NATIVE_PROCESSING,
                 can_suppress: bool = True) -> None:
        self.career_id = career_id
        self.rng = random.Random(seed)
        self.max_level = max_level
        self.can_suppress = can_suppress
        self.faults: set[str] = set()
        self.players: dict[int, PlayerProfile] = {}
        self.clubs: dict[int, MockClub] = {}
        self.fixtures: list[MockFixtureRecord] = []
        self.table: dict[int, dict[str, int]] = {}
        self.season: dict[int, SeasonStats] = defaultdict(SeasonStats)
        self.injured: set[int] = set()
        self.suspended: dict[int, int] = {}
        self.suppressed: set[str] = set()
        self.managed_club = 100
        self._build_world(n_clubs)

    # -- world ----------------------------------------------------------
    def _build_world(self, n_clubs: int) -> None:
        next_pid = 1000
        for c in range(n_clubs):
            club_id = 100 + c
            ids = []
            for pos in SQUAD_POSITIONS:
                ids.append(next_pid)
                self.players[next_pid] = self._make_player(next_pid, club_id, pos)
                next_pid += 1
            self.clubs[club_id] = MockClub(club_id, f"Mock Club {c + 1}", ids)
            self.table[club_id] = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "points": 0}
        others = [cid for cid in self.clubs if cid != self.managed_club]
        for i, opp in enumerate(others):
            home, away = (self.managed_club, opp) if i % 2 == 0 else (opp, self.managed_club)
            self.fixtures.append(MockFixtureRecord(f"mockfm-fixture-{i + 1}", home, away,
                                                   f"2026-08-{10 + 7 * i:02d}T15:00:00"))

    def _make_player(self, pid: int, club_id: int, pos: str) -> PlayerProfile:
        r = self.rng
        base = r.randint(9, 15)

        def roll(names: list[str]) -> dict[str, int]:
            return {n: max(1, min(20, base + r.randint(-4, 4))) for n in names}

        is_gk = pos == "GK"
        attrs = AttributeSnapshot(
            technical=roll(TECHNICAL), mental=roll(MENTAL), physical=roll(PHYSICAL),
            goalkeeping=roll(GOALKEEPING) if is_gk else {},
            hidden={"consistency": r.randint(5, 18), "important_matches": r.randint(5, 18)},
            current_ability=base * 8, potential_ability=min(200, base * 8 + r.randint(0, 40)),
        )
        positions = {pos: 20}
        if pos in ("DR", "DL"):
            positions["WBR" if pos == "DR" else "WBL"] = 16
        if pos in ("MC", "DM"):
            positions["DM" if pos == "MC" else "MC"] = 15
        foot = r.choice(["right", "right", "left"])
        weak = r.randint(4, 16)
        origin = PlayerOrigin.REGEN if pid % 7 == 0 else PlayerOrigin.FM_DATABASE
        return PlayerProfile(
            fm_player_id=pid, first_name=f"First{pid}", last_name=f"Last{pid}",
            date_of_birth=f"{r.randint(1990, 2008)}-0{r.randint(1, 9)}-1{r.randint(0, 9)}",
            nationality=r.choice(["ENG", "ESP", "FRA", "BRA", "GER"]), origin=origin, positions=positions,
            attributes=attrs,
            appearance=Appearance(height_cm=r.randint(168, 196), weight_kg=r.randint(62, 92), preferred_foot=foot,
                                  left_foot=20 if foot == "left" else weak, right_foot=20 if foot == "right" else weak),
            club_fm_id=club_id, traits=("tries_long_range_shots",) if pid % 5 == 0 else (),
        )

    # -- FmAdapter --------------------------------------------------------
    def capabilities(self) -> FmCapabilities:
        return FmCapabilities(detect_fixture=True, capture_squads=True, capture_tactics=True,
                              capture_hidden_attributes=True, suppress_native_simulation=self.can_suppress,
                              max_integration_level=self.max_level, verify_import=True,
                              evidence={"all": "MOCK - test double, not evidence about FM"})

    def _next_fixture(self) -> Optional[MockFixtureRecord]:
        return next((f for f in self.fixtures if f.result is None), None)

    def _record(self, ref: str) -> MockFixtureRecord:
        for f in self.fixtures:
            if f.ref == ref:
                return f
        raise AdapterError(f"unknown fixture {ref}")

    def _squad(self, club_id: int) -> MatchdaySquad:
        club = self.clubs[club_id]
        available = [p for p in club.player_ids if p not in self.injured and self.suspended.get(p, 0) == 0]
        starters, used = [], set()
        for slot, pos, _, _ in MOCK_SHAPE:
            cand = next((p for p in available if p not in used and pos in self.players[p].positions), None)
            if cand is None:
                cand = next(p for p in available if p not in used and (pos == "GK") == (
                    "GK" in self.players[p].positions))
            used.add(cand)
            starters.append(LineupSlot(slot, fm_ref(cand), pos))
        bench = [fm_ref(p) for p in available if p not in used][:9]
        return MatchdaySquad(ClubRef(f"HC-{club_id}", club_id, club.name), tuple(starters), tuple(bench),
                             captain_id=starters[2].hybrid_player_id)

    def detect_upcoming_fixture(self) -> Optional[Fixture]:
        f = self._next_fixture()
        if f is None:
            return None
        side = Side.HOME if f.home_club == self.managed_club else Side.AWAY
        return Fixture(
            fixture_id=stable_fixture_id(self.career_id, f.ref), career_id=self.career_id, fm_fixture_ref=f.ref,
            competition=CompetitionRef(1, "Mock League", None), kickoff=f.kickoff,
            home=self._squad(f.home_club), away=self._squad(f.away_club), managed_side=side,
            rules=MatchRules(), venue=f"{self.clubs[f.home_club].name} Stadium",
        )

    def _plan(self, club_id: int) -> TacticalPlan:
        return TacticalPlan(
            name=f"{self.clubs[club_id].name} 4-2-3-1", formation="4-2-3-1 DM Wide", mentality="positive",
            roles=tuple(RoleAssignment(s, p, role, duty) for s, p, role, duty in MOCK_SHAPE),
            in_possession=("shorter_passing", "play_out_of_defence"), in_transition=("counter_press",),
            out_of_possession=("higher_defensive_line", "much_more_urgent_pressing"), source_version="mock",
        )

    def capture_match_context(self, fm_fixture_ref: str) -> FmMatchContext:
        if "capture_fail_once" in self.faults:
            self.faults.discard("capture_fail_once")
            raise DataCaptureError("mock FM capture failed", retryable=True)
        f = self._record(fm_fixture_ref)
        fixture = self.detect_upcoming_fixture()
        if fixture is None or fixture.fm_fixture_ref != fm_fixture_ref:
            raise AdapterError(f"fixture {fm_fixture_ref} is not the upcoming fixture")
        ids = [int(r.split(":")[1]) for sq in (fixture.home, fixture.away) for r in sq.all_player_ids()]
        raw = {
            "table": {str(k): dict(v) for k, v in self.table.items()},
            "season": {str(k): {"apps": v.appearances, "goals": v.goals} for k, v in self.season.items()},
            "fixture_ref": f.ref,
        }
        return FmMatchContext(
            fixture=fixture, players=tuple(self.players[i] for i in ids),
            tactics={Side.HOME.value: self._plan(f.home_club), Side.AWAY.value: self._plan(f.away_club)},
            raw_state=raw,
        )

    def suppress_native_simulation(self, fm_fixture_ref: str) -> None:
        if not self.can_suppress:
            raise AdapterError("this FM route cannot suppress native simulation")
        self._record(fm_fixture_ref)
        self.suppressed.add(fm_fixture_ref)

    def import_result(self, package: FmImportPackage) -> ImportReceipt:
        f = self._record(package.fm_fixture_ref)
        if f.result is not None:
            if f.import_key == package.idempotency_key and f.receipt is not None:
                return f.receipt  # idempotent: same package again is a no-op
            raise DuplicateImportError(f"fixture {f.ref} already has a result")
        if "import_fail_once" in self.faults:
            self.faults.discard("import_fail_once")
            raise ImportFailedError("mock FM rejected the import", retryable=True)
        self._apply(f, package)
        receipt = ImportReceipt(package.idempotency_key, f.ref, self.max_level, utc_now(),
                                {"mock": True})
        f.receipt = receipt
        if "crash_after_apply_once" in self.faults:
            self.faults.discard("crash_after_apply_once")
            raise SimulatedCrash("bridge died after FM applied the result")
        return receipt

    def _apply(self, f: MockFixtureRecord, p: FmImportPackage) -> None:
        f.result = (p.home_goals, p.away_goals)
        f.import_key = p.idempotency_key
        f.import_count += 1
        for club, gf, ga in ((f.home_club, p.home_goals, p.away_goals), (f.away_club, p.away_goals, p.home_goals)):
            row = self.table[club]
            row["played"] += 1
            row["gf"] += gf
            row["ga"] += ga
            if gf > ga:
                row["won"] += 1
                row["points"] += 3
                self.clubs[club].morale = min(1.0, self.clubs[club].morale + 0.1)
            elif gf == ga:
                row["drawn"] += 1
                row["points"] += 1
            else:
                row["lost"] += 1
                self.clubs[club].morale = max(0.0, self.clubs[club].morale - 0.1)
        for club in (f.home_club, f.away_club):  # serve suspensions for clubs that played
            for pid in self.clubs[club].player_ids:
                if self.suspended.get(pid, 0) > 0:
                    self.suspended[pid] -= 1
        for a in p.appearances:
            s = self.season[a.fm_player_id]
            s.appearances += 1
            s.starts += int(a.started)
            s.minutes += a.minutes_played
            s.goals += a.goals
            s.assists += a.assists
            s.yellow_cards += a.yellow_cards
            s.red_cards += int(a.red_card)
            if a.rating is not None:
                s.ratings.append(a.rating)
            if a.red_card:
                self.suspended[a.fm_player_id] = 1
            if a.injured:
                self.injured.add(a.fm_player_id)

    def lookup_import(self, fm_fixture_ref: str) -> Optional[ImportReceipt]:
        return self._record(fm_fixture_ref).receipt

    def verify_import(self, package: FmImportPackage) -> VerificationReport:
        f = self._record(package.fm_fixture_ref)
        checks = [
            VerificationCheck("fixture_has_result", f.result is not None),
            VerificationCheck("scoreline", f.result == (package.home_goals, package.away_goals),
                              (package.home_goals, package.away_goals), f.result),
            VerificationCheck("applied_exactly_once", f.import_count == 1, 1, f.import_count),
            VerificationCheck("idempotency_key", f.import_key == package.idempotency_key,
                              package.idempotency_key, f.import_key),
        ]
        if "tamper_verification" in self.faults:
            checks.append(VerificationCheck("tampered", False))
        for a in package.appearances:
            if self.season[a.fm_player_id].appearances < 1:
                checks.append(VerificationCheck(f"appearance:{a.fm_player_id}", False, ">=1", 0))
        return VerificationReport(package.idempotency_key, tuple(checks))
