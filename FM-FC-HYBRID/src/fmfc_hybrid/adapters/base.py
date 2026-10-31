"""Adapter protocols: the only place the bridge meets a real game.

These protocols are capability-shaped, not game-shaped. They describe what the
bridge *needs*, never how a particular FM/FIFA build provides it; there are no
invented game functions here. Each real adapter (e.g. an FM26 plugin client, a
FIFA 22 Live-Editor client) declares honestly which capabilities it has via
:class:`FmCapabilities` / :class:`FifaCapabilities`, and the bridge records
the resulting :class:`IntegrationLevel` for every imported match, so a
score-editing route can never be reported as full integration.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from ..contracts.models import (
    ExternalMatchRecord,
    Fixture,
    FmImportPackage,
    MatchEvent,
    PlayerProfile,
    Side,
    TacticalPlan,
)


class IntegrationLevel(int, enum.Enum):
    """How deeply an external match was integrated into FM (ordered)."""

    NONE = 0
    SCORE_ONLY = 1           # fixture scoreline edited; FM consequences not driven by the match
    RESULT_AND_STATS = 2     # score + per-player appearances/goals/cards written into FM data
    EVENTS_INJECTED = 3      # FM's own match representation populated with external events
    NATIVE_PROCESSING = 4    # FM ran its native post-match processing on the external match (target)

    @property
    def is_full_integration(self) -> bool:
        return self is IntegrationLevel.NATIVE_PROCESSING


class ControlMode(str, enum.Enum):
    USER_CONTROLS_MANAGED_SIDE = "user_controls_managed_side"
    AI_VS_AI = "ai_vs_ai"


@dataclass(frozen=True)
class FmCapabilities:
    detect_fixture: bool = False
    capture_squads: bool = False
    capture_tactics: bool = False
    capture_hidden_attributes: bool = False
    suppress_native_simulation: bool = False
    max_integration_level: IntegrationLevel = IntegrationLevel.NONE
    verify_import: bool = False
    evidence: dict[str, str] = field(default_factory=dict)  # capability -> evidence classification/link


@dataclass(frozen=True)
class FifaCapabilities:
    create_players: bool = False
    edit_player_attributes: bool = False
    set_lineups: bool = False
    set_team_tactics: bool = False
    set_player_instructions: bool = False
    launch_match: bool = False
    user_control: bool = False
    ai_vs_ai: bool = False
    stream_events: bool = False
    capture_player_stats: bool = False
    capture_team_stats: bool = False
    detect_full_time: bool = False
    evidence: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FmMatchContext:
    """Everything captured from FM for one fixture, before any change is made."""

    fixture: Fixture
    players: tuple[PlayerProfile, ...]          # both matchday squads
    tactics: dict[str, TacticalPlan]            # Side.value -> plan
    hybrid_ids_by_fm: dict[int, str] = field(default_factory=dict)
    raw_state: dict[str, Any] = field(default_factory=dict)  # opaque preservation copy


@dataclass(frozen=True)
class ImportReceipt:
    idempotency_key: str
    fm_fixture_ref: str
    integration_level: IntegrationLevel
    applied_at: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    expected: Any = None
    actual: Any = None


@dataclass(frozen=True)
class VerificationReport:
    idempotency_key: str
    checks: tuple[VerificationCheck, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def failures(self) -> list[VerificationCheck]:
        return [c for c in self.checks if not c.passed]


@runtime_checkable
class FmAdapter(Protocol):
    name: str

    def capabilities(self) -> FmCapabilities: ...

    def detect_upcoming_fixture(self) -> Optional[Fixture]:
        """Return the next managed-club fixture with the squads FM currently has selected, if any."""

    def capture_match_context(self, fm_fixture_ref: str) -> FmMatchContext: ...

    def suppress_native_simulation(self, fm_fixture_ref: str) -> None:
        """Ensure FM will not simulate this fixture itself (raise if impossible)."""

    def import_result(self, package: FmImportPackage) -> ImportReceipt: ...

    def lookup_import(self, fm_fixture_ref: str) -> Optional[ImportReceipt]:
        """Ask FM whether a result for this fixture is already applied (crash recovery)."""

    def verify_import(self, package: FmImportPackage) -> VerificationReport: ...


@dataclass(frozen=True)
class FifaPlayerSpec:
    """A player as the FIFA adapter should materialize him (version-neutral targets)."""

    hybrid_player_id: str
    fifa_player_id: int
    display_name: str
    must_create: bool
    attributes: dict[str, int]       # FIFA 1-99 attribute names (target profile from mapping config)
    positions: tuple[str, ...]       # FIFA position names, preferred first
    preferred_foot: str
    weak_foot: int                   # 1-5
    skill_moves: int                 # 1-5
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    traits: tuple[str, ...] = ()


@dataclass(frozen=True)
class FifaTeamSetup:
    side: Side
    hybrid_club_id: str
    starters: tuple[tuple[str, str], ...]  # (hybrid_player_id, FIFA position)
    bench: tuple[str, ...]
    team_settings: dict[str, Any]          # translated tactics: knob -> value
    player_instructions: dict[str, dict[str, Any]]  # hybrid_player_id -> instruction -> value
    captain_id: Optional[str] = None


@dataclass(frozen=True)
class FifaMatchRequest:
    ledger_match_id: str
    fixture: Fixture
    players: tuple[FifaPlayerSpec, ...]
    home: FifaTeamSetup
    away: FifaTeamSetup
    control_mode: ControlMode
    half_length_minutes: int = 6  # FIFA real-time half length; configuration, not FM rules


@dataclass(frozen=True)
class PreparationReceipt:
    ledger_match_id: str
    created_players: tuple[str, ...]
    updated_players: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class FifaAdapter(Protocol):
    name: str

    def capabilities(self) -> FifaCapabilities: ...

    def prepare_match(self, request: FifaMatchRequest) -> PreparationReceipt: ...

    def launch_match(self, ledger_match_id: str) -> None: ...

    def poll_events(self, ledger_match_id: str, after_sequence: int) -> list[MatchEvent]: ...

    def collect_result(self, ledger_match_id: str) -> ExternalMatchRecord:
        """Block until full time (or failure) and return the complete record."""

    def has_completed_record(self, ledger_match_id: str) -> bool: ...
