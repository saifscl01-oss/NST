"""Shared domain models exchanged between FM-side and FIFA-side components.

These models are deliberately *game-neutral*. FM-specific vocabulary appears
only where FM is the authority (e.g. FM position codes and FM role names in a
:class:`TacticalPlan`, FM 1-20 attributes), because FM is the source of truth.
FIFA-specific values never appear here; they are produced by the mappers and
consumed by a FIFA adapter.

All identifiers that cross component boundaries are *hybrid* identifiers
(``hybrid_player_id`` etc.). Game identifiers are carried only as references
resolved through the identity registry.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, Union

DetailValue = Union[str, int, float, bool]


class Side(str, enum.Enum):
    HOME = "home"
    AWAY = "away"

    @property
    def opponent(self) -> "Side":
        return Side.AWAY if self is Side.HOME else Side.HOME


class Period(str, enum.Enum):
    FIRST_HALF = "1H"
    SECOND_HALF = "2H"
    EXTRA_TIME_FIRST = "ET1"
    EXTRA_TIME_SECOND = "ET2"
    PENALTY_SHOOTOUT = "PSO"

    @property
    def order(self) -> int:
        return list(Period).index(self)


class EventType(str, enum.Enum):
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"
    GOAL = "goal"                    # player_id = scorer, secondary_player_id = assister (optional)
    OWN_GOAL = "own_goal"            # side/player_id = the player who put it in his own net
    PENALTY_MISSED = "penalty_missed"
    SUBSTITUTION = "substitution"    # player_id = player off, secondary_player_id = player on
    YELLOW_CARD = "yellow_card"
    SECOND_YELLOW = "second_yellow"  # implies dismissal
    RED_CARD = "red_card"
    INJURY = "injury"                # detail: severity, forced_off
    SHOOTOUT_KICK = "shootout_kick"  # detail: scored (bool)
    FULL_TIME = "full_time"


class Duty(str, enum.Enum):
    DEFEND = "defend"
    SUPPORT = "support"
    ATTACK = "attack"
    STOPPER = "stopper"
    COVER = "cover"
    AUTOMATIC = "automatic"


class PlayerOrigin(str, enum.Enum):
    """How a player came to exist, which decides how he is created in FIFA."""

    FM_DATABASE = "fm_database"    # real player present in the FM database
    REGEN = "regen"                # FM-generated newgen
    YOUTH_INTAKE = "youth_intake"  # FM youth academy graduate
    FM_EDITOR = "fm_editor"        # created via the FM editor / IGE


class FifaLinkStatus(str, enum.Enum):
    UNLINKED = "unlinked"          # no FIFA record yet
    MATCHED = "matched"            # mapped onto an existing FIFA database player
    CREATED = "created"            # created by the bridge in FIFA
    STALE = "stale"                # FIFA record exists but needs re-sync


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttributeSnapshot:
    """FM attributes on FM's native 1-20 scale (CA/PA on FM's 1-200 scale).

    Keys are FM attribute identifiers in snake_case (e.g. ``finishing``,
    ``off_the_ball``). Hidden attributes are optional because not every FM
    access route exposes them.
    """

    technical: dict[str, int] = field(default_factory=dict)
    mental: dict[str, int] = field(default_factory=dict)
    physical: dict[str, int] = field(default_factory=dict)
    goalkeeping: dict[str, int] = field(default_factory=dict)
    hidden: dict[str, int] = field(default_factory=dict)
    current_ability: Optional[int] = None
    potential_ability: Optional[int] = None

    def all_visible(self) -> dict[str, int]:
        merged: dict[str, int] = {}
        for group in (self.technical, self.mental, self.physical, self.goalkeeping):
            merged.update(group)
        return merged


@dataclass(frozen=True)
class Appearance:
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    preferred_foot: str = "right"  # right | left | either
    left_foot: Optional[int] = None   # FM 1-20 weak/strong foot rating
    right_foot: Optional[int] = None
    extra: dict[str, str] = field(default_factory=dict)  # skin tone, hair etc. once a source exists


@dataclass(frozen=True)
class PlayerProfile:
    """A player as FM describes him at capture time (FM is authoritative)."""

    fm_player_id: int
    first_name: str
    last_name: str
    date_of_birth: str  # ISO date
    nationality: str
    origin: PlayerOrigin
    positions: dict[str, int]  # FM position code -> familiarity 1-20
    attributes: AttributeSnapshot
    appearance: Appearance = field(default_factory=Appearance)
    common_name: Optional[str] = None
    club_fm_id: Optional[int] = None
    traits: tuple[str, ...] = ()  # FM player traits ("PPMs"), snake_case
    shirt_number: Optional[int] = None

    @property
    def display_name(self) -> str:
        return self.common_name or f"{self.first_name} {self.last_name}".strip()


# ---------------------------------------------------------------------------
# Fixtures and squads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClubRef:
    hybrid_club_id: str
    fm_club_id: int
    name: str


@dataclass(frozen=True)
class CompetitionRef:
    fm_competition_id: int
    name: str
    stage: Optional[str] = None


@dataclass(frozen=True)
class MatchRules:
    half_length_minutes: int = 45
    substitutions_allowed: int = 5
    substitution_windows: Optional[int] = 3  # None = unlimited windows
    bench_size: int = 9
    extra_time: bool = False
    penalty_shootout: bool = False


@dataclass(frozen=True)
class LineupSlot:
    slot: int               # 0..10, 0 is the goalkeeper slot
    hybrid_player_id: str
    position: str           # FM position code, e.g. "GK", "DC", "WBR", "DM", "AMC", "STC"


@dataclass(frozen=True)
class MatchdaySquad:
    club: ClubRef
    starters: tuple[LineupSlot, ...]
    bench: tuple[str, ...]
    captain_id: Optional[str] = None
    set_piece_takers: dict[str, str] = field(default_factory=dict)  # role -> hybrid id

    def all_player_ids(self) -> list[str]:
        return [s.hybrid_player_id for s in self.starters] + list(self.bench)


@dataclass(frozen=True)
class Fixture:
    fixture_id: str        # hybrid fixture id (stable, generated by the bridge)
    career_id: str
    fm_fixture_ref: str    # opaque reference understood only by the FM adapter
    competition: CompetitionRef
    kickoff: str           # in-game ISO datetime
    home: MatchdaySquad
    away: MatchdaySquad
    managed_side: Side
    rules: MatchRules = field(default_factory=MatchRules)
    venue: Optional[str] = None

    def squad(self, side: Side) -> MatchdaySquad:
        return self.home if side is Side.HOME else self.away


# ---------------------------------------------------------------------------
# Tactics (FM vocabulary: FM is the tactical authority)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleAssignment:
    slot: int
    position: str                 # FM position code
    role: str                     # FM role id, snake_case, e.g. "inverted_wing_back"
    duty: Duty
    individual_instructions: tuple[str, ...] = ()


@dataclass(frozen=True)
class TacticalPlan:
    name: str
    formation: str                # FM formation label, e.g. "4-2-3-1 DM Wide"
    mentality: str                # very_defensive .. very_attacking
    roles: tuple[RoleAssignment, ...]
    in_possession: tuple[str, ...] = ()
    in_transition: tuple[str, ...] = ()
    out_of_possession: tuple[str, ...] = ()
    source_version: Optional[str] = None  # FM edition the plan was captured from


# ---------------------------------------------------------------------------
# Match events and statistics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchClock:
    period: Period
    minute: int          # regulation minute, e.g. 45 for "45+2"
    added_minute: int = 0
    second: int = 0

    def sort_key(self) -> tuple[int, int, int, int]:
        return (self.period.order, self.minute, self.added_minute, self.second)

    def elapsed_minutes(self) -> float:
        """Approximate playing minutes elapsed, counting stoppage time."""
        return self.minute + self.added_minute + self.second / 60.0

    def label(self) -> str:
        return f"{self.minute}+{self.added_minute}'" if self.added_minute else f"{self.minute}'"


@dataclass(frozen=True)
class MatchEvent:
    match_id: str
    source_event_id: str      # id assigned by the source; the de-duplication key
    sequence: int             # source ordering, monotonic per match
    clock: MatchClock
    type: EventType
    side: Optional[Side] = None
    player_id: Optional[str] = None
    secondary_player_id: Optional[str] = None
    detail: dict[str, DetailValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PlayerMatchStats:
    hybrid_player_id: str
    side: Side
    rating: Optional[float] = None          # source rating, scale recorded in ExternalMatchRecord
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    tackles: int = 0
    interceptions: int = 0
    saves: int = 0
    fouls: int = 0
    offsides: int = 0
    distance_km: Optional[float] = None
    extra: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TeamMatchStats:
    side: Side
    goals: int
    possession_pct: Optional[float] = None
    shots: int = 0
    shots_on_target: int = 0
    corners: int = 0
    fouls: int = 0
    offsides: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    extra: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ExternalMatchRecord:
    """Everything the FIFA side captured about one played match."""

    match_id: str
    fixture_id: str
    source: str                 # e.g. "mock-fifa"; real adapters name game + version
    source_version: str
    events: tuple[MatchEvent, ...]
    player_stats: tuple[PlayerMatchStats, ...]
    team_stats: tuple[TeamMatchStats, ...]
    completed_normally: bool    # False if the match was abandoned / quit early
    rating_scale: Optional[str] = None  # e.g. "0-10"
    user_controlled_side: Optional[Side] = None  # None = AI vs AI
    captured_at: str = ""


# ---------------------------------------------------------------------------
# FM import package (what the FM adapter is asked to apply)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlayerAppearance:
    hybrid_player_id: str
    fm_player_id: int
    side: Side
    started: bool
    minutes_played: int
    goals: int = 0
    assists: int = 0
    own_goals: int = 0
    yellow_cards: int = 0
    red_card: bool = False
    injured: bool = False
    rating: Optional[float] = None  # converted to FM's rating scale by the result processor


@dataclass(frozen=True)
class FmImportPackage:
    """Idempotent unit of work handed to the FM adapter.

    ``idempotency_key`` is derived from the career, fixture and the finalized
    ledger hash. The FM adapter must refuse (or no-op) a second import with
    the same fixture, and the bridge refuses a second package for a fixture
    whose import is already completed.
    """

    idempotency_key: str
    career_id: str
    fixture_id: str
    fm_fixture_ref: str
    home_goals: int
    away_goals: int
    events: tuple[MatchEvent, ...]
    appearances: tuple[PlayerAppearance, ...]
    team_stats: tuple[TeamMatchStats, ...]
    ledger_hash: str
    shootout_home: Optional[int] = None
    shootout_away: Optional[int] = None
