"""Validation of fixtures and match-event streams.

:class:`MatchReplay` replays an event stream against a fixture and enforces
football consistency (who is on the pitch, substitution limits, dismissals,
score reconciliation). It is shared by validation and by the result processor
so both reason about exactly the same reconstructed match.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..errors import IssueCollector
from .models import (
    EventType,
    ExternalMatchRecord,
    Fixture,
    MatchClock,
    MatchEvent,
    MatchRules,
    Period,
    Side,
)

#: FM base position codes used in lineups and tactical plans.
FM_POSITIONS = frozenset(
    {"GK", "DR", "DC", "DL", "WBR", "WBL", "DM", "MR", "MC", "ML", "AMR", "AMC", "AML", "ST"}
)


# ---------------------------------------------------------------------------
# Fixture validation
# ---------------------------------------------------------------------------


def validate_fixture(fixture: Fixture) -> IssueCollector:
    out = IssueCollector()
    if not fixture.fixture_id:
        out.error("FIXTURE_ID_MISSING", "fixture_id is empty", "fixture_id")
    if not fixture.career_id:
        out.error("CAREER_ID_MISSING", "career_id is empty", "career_id")
    if not fixture.fm_fixture_ref:
        out.error("FM_REF_MISSING", "fm_fixture_ref is empty", "fm_fixture_ref")
    if fixture.home.club.hybrid_club_id == fixture.away.club.hybrid_club_id:
        out.error("SAME_CLUB", "home and away clubs are identical", "away.club")
    _validate_rules(fixture.rules, out)

    seen_global: dict[str, str] = {}
    for side in (Side.HOME, Side.AWAY):
        squad = fixture.squad(side)
        base = side.value
        starters = squad.starters
        if len(starters) != 11:
            out.error("STARTERS_COUNT", f"{base}: expected 11 starters, got {len(starters)}", f"{base}.starters")
        slots = [s.slot for s in starters]
        if sorted(slots) != sorted(set(slots)):
            out.error("SLOT_DUPLICATE", f"{base}: duplicate lineup slots", f"{base}.starters")
        if any(not 0 <= s <= 10 for s in slots):
            out.error("SLOT_RANGE", f"{base}: slots must be 0..10", f"{base}.starters")
        gks = [s for s in starters if s.position == "GK"]
        if len(gks) != 1:
            out.error("GOALKEEPER_COUNT", f"{base}: expected exactly one GK starter, got {len(gks)}",
                      f"{base}.starters")
        for i, s in enumerate(starters):
            if s.position not in FM_POSITIONS:
                out.error("POSITION_UNKNOWN", f"{base}: unknown FM position '{s.position}'",
                          f"{base}.starters[{i}].position")
        if len(squad.bench) > fixture.rules.bench_size:
            out.error("BENCH_SIZE", f"{base}: bench has {len(squad.bench)} > {fixture.rules.bench_size}",
                      f"{base}.bench")
        ids = squad.all_player_ids()
        for pid, count in Counter(ids).items():
            if count > 1:
                out.error("PLAYER_DUPLICATE", f"{base}: player {pid} listed {count} times", f"{base}")
        for pid in set(ids):
            if pid in seen_global:
                out.error("PLAYER_BOTH_SQUADS", f"player {pid} appears in both squads", base)
            seen_global[pid] = base
        if squad.captain_id is not None and squad.captain_id not in ids:
            out.error("CAPTAIN_NOT_IN_SQUAD", f"{base}: captain not in matchday squad", f"{base}.captain_id")
        elif squad.captain_id is not None and squad.captain_id in squad.bench:
            out.warning("CAPTAIN_ON_BENCH", f"{base}: captain starts on the bench", f"{base}.captain_id")
        for role, pid in squad.set_piece_takers.items():
            if pid not in ids:
                out.error("SET_PIECE_TAKER_NOT_IN_SQUAD", f"{base}: {role} taker not in squad",
                          f"{base}.set_piece_takers.{role}")
    return out


def _validate_rules(rules: MatchRules, out: IssueCollector) -> None:
    if not 1 <= rules.half_length_minutes <= 60:
        out.error("RULES_HALF_LENGTH", "half_length_minutes must be 1..60", "rules.half_length_minutes")
    if rules.substitutions_allowed < 0:
        out.error("RULES_SUBS", "substitutions_allowed must be >= 0", "rules.substitutions_allowed")
    if rules.substitution_windows is not None and rules.substitution_windows < 0:
        out.error("RULES_WINDOWS", "substitution_windows must be >= 0", "rules.substitution_windows")
    if rules.bench_size < 0:
        out.error("RULES_BENCH", "bench_size must be >= 0", "rules.bench_size")
    if rules.penalty_shootout and not rules.extra_time:
        out.warning("RULES_SHOOTOUT_NO_ET", "penalty shootout without extra time", "rules")


# ---------------------------------------------------------------------------
# Match replay
# ---------------------------------------------------------------------------


@dataclass
class PlayerSpell:
    """One continuous period on the pitch, measured in regulation minutes."""

    entered: float
    left: Optional[float] = None
    left_reason: Optional[str] = None  # substituted | dismissed | injured


@dataclass
class ReplayState:
    score: dict[Side, int] = field(default_factory=lambda: {Side.HOME: 0, Side.AWAY: 0})
    shootout: dict[Side, int] = field(default_factory=lambda: {Side.HOME: 0, Side.AWAY: 0})
    on_pitch: dict[Side, set[str]] = field(default_factory=lambda: {Side.HOME: set(), Side.AWAY: set()})
    used_subs: dict[Side, int] = field(default_factory=lambda: {Side.HOME: 0, Side.AWAY: 0})
    sub_windows: dict[Side, list[tuple[Period, int]]] = field(
        default_factory=lambda: {Side.HOME: [], Side.AWAY: []})
    spells: dict[str, list[PlayerSpell]] = field(default_factory=dict)
    yellow: Counter = field(default_factory=Counter)
    dismissed: set[str] = field(default_factory=set)
    substituted_off: set[str] = field(default_factory=set)
    injured: set[str] = field(default_factory=set)
    goals: Counter = field(default_factory=Counter)
    assists: Counter = field(default_factory=Counter)
    own_goals: Counter = field(default_factory=Counter)
    full_time: Optional[MatchClock] = None
    periods_seen: list[Period] = field(default_factory=list)


class MatchReplay:
    """Replays events for ``fixture`` and collects issues into ``issues``."""

    def __init__(self, fixture: Fixture) -> None:
        self.fixture = fixture
        self.rules = fixture.rules
        self.issues = IssueCollector()
        self.state = ReplayState()
        self._side_of: dict[str, Side] = {}
        self._bench: dict[Side, set[str]] = {}
        for side in (Side.HOME, Side.AWAY):
            squad = fixture.squad(side)
            for pid in squad.all_player_ids():
                self._side_of[pid] = side
            self._bench[side] = set(squad.bench)
            for slot in squad.starters:
                self.state.on_pitch[side].add(slot.hybrid_player_id)
                self.state.spells[slot.hybrid_player_id] = [PlayerSpell(entered=0.0)]

    # -- time ------------------------------------------------------------
    def regulation_minute(self, clock: MatchClock) -> float:
        """Minute on a continuous regulation scale (stoppage time collapses to period end)."""
        half = self.rules.half_length_minutes
        period_end = {
            Period.FIRST_HALF: half,
            Period.SECOND_HALF: 2 * half,
            Period.EXTRA_TIME_FIRST: 2 * half + 15,
            Period.EXTRA_TIME_SECOND: 2 * half + 30,
            Period.PENALTY_SHOOTOUT: 2 * half + 30,
        }[clock.period]
        value = clock.minute + (0 if clock.added_minute else clock.second / 60.0)
        return float(min(value, period_end)) if clock.period is not Period.PENALTY_SHOOTOUT else float(period_end)

    # -- replay ----------------------------------------------------------
    def replay(self, events: Iterable[MatchEvent]) -> ReplayState:
        ordered = sorted(events, key=lambda e: e.sequence)
        seen_ids: set[str] = set()
        seen_seq: set[int] = set()
        match_ids = {e.match_id for e in ordered}
        if len(match_ids) > 1:
            self.issues.error("MIXED_MATCH_IDS", f"events reference several matches: {sorted(match_ids)}")
        last_clock: Optional[MatchClock] = None
        for idx, ev in enumerate(ordered):
            path = f"events[{ev.sequence}]"
            if ev.source_event_id in seen_ids:
                self.issues.error("DUPLICATE_SOURCE_EVENT", f"duplicate source_event_id {ev.source_event_id}", path)
                continue
            seen_ids.add(ev.source_event_id)
            if ev.sequence in seen_seq:
                self.issues.error("DUPLICATE_SEQUENCE", f"duplicate sequence {ev.sequence}", path)
            seen_seq.add(ev.sequence)
            if last_clock is not None and ev.clock.sort_key() < last_clock.sort_key():
                self.issues.error("CLOCK_REGRESSION",
                                  f"{ev.type.value} at {ev.clock.label()} is earlier than previous event", path)
            last_clock = ev.clock
            if self.state.full_time is not None:
                self.issues.error("EVENT_AFTER_FULL_TIME", f"{ev.type.value} after full time", path)
            self._check_period_allowed(ev, path)
            handler = getattr(self, f"_on_{ev.type.value}", None)
            if handler is not None:
                handler(ev, path)
        return self.state

    def _check_period_allowed(self, ev: MatchEvent, path: str) -> None:
        p = ev.clock.period
        if p in (Period.EXTRA_TIME_FIRST, Period.EXTRA_TIME_SECOND) and not self.rules.extra_time:
            self.issues.error("EXTRA_TIME_NOT_ALLOWED", "extra-time event but rules disallow extra time", path)
        if p is Period.PENALTY_SHOOTOUT and not self.rules.penalty_shootout:
            self.issues.error("SHOOTOUT_NOT_ALLOWED", "shootout event but rules disallow a shootout", path)
        if p not in self.state.periods_seen:
            self.state.periods_seen.append(p)

    def _require_player(self, ev: MatchEvent, pid: Optional[str], path: str, *, role: str,
                        on_pitch: bool = True) -> Optional[Side]:
        if pid is None:
            self.issues.error("PLAYER_MISSING", f"{ev.type.value}: {role} is required", path)
            return None
        side = self._side_of.get(pid)
        if side is None:
            self.issues.error("PLAYER_NOT_IN_FIXTURE", f"{ev.type.value}: {role} {pid} not in either squad", path)
            return None
        if ev.side is not None and side is not ev.side:
            self.issues.error("SIDE_MISMATCH", f"{ev.type.value}: {role} {pid} plays for {side.value}", path)
        if on_pitch and pid not in self.state.on_pitch[side]:
            self.issues.error("PLAYER_NOT_ON_PITCH",
                              f"{ev.type.value}: {role} {pid} is not on the pitch at {ev.clock.label()}", path)
        return side

    def _leave(self, pid: str, side: Side, minute: float, reason: str) -> None:
        self.state.on_pitch[side].discard(pid)
        spells = self.state.spells.get(pid)
        if spells and spells[-1].left is None:
            spells[-1].left = minute
            spells[-1].left_reason = reason

    # -- handlers (named _on_<EventType.value>) --------------------------
    def _on_goal(self, ev: MatchEvent, path: str) -> None:
        side = self._require_player(ev, ev.player_id, path, role="scorer")
        if side is None:
            return
        self.state.score[side] += 1
        self.state.goals[ev.player_id] += 1
        if ev.secondary_player_id is not None:
            if ev.secondary_player_id == ev.player_id:
                self.issues.error("SELF_ASSIST", "scorer cannot assist his own goal", path)
                return
            a_side = self._require_player(ev, ev.secondary_player_id, path, role="assister")
            if a_side is not None and a_side is side:
                self.state.assists[ev.secondary_player_id] += 1

    def _on_own_goal(self, ev: MatchEvent, path: str) -> None:
        side = self._require_player(ev, ev.player_id, path, role="own-goal scorer")
        if side is None:
            return
        self.state.score[side.opponent] += 1
        self.state.own_goals[ev.player_id] += 1

    def _on_penalty_missed(self, ev: MatchEvent, path: str) -> None:
        self._require_player(ev, ev.player_id, path, role="penalty taker")

    def _on_substitution(self, ev: MatchEvent, path: str) -> None:
        off_side = self._require_player(ev, ev.player_id, path, role="player off")
        on_pid = ev.secondary_player_id
        if on_pid is None:
            self.issues.error("PLAYER_MISSING", "substitution: player on is required", path)
            return
        on_side = self._side_of.get(on_pid)
        if on_side is None:
            self.issues.error("PLAYER_NOT_IN_FIXTURE", f"substitution: player on {on_pid} not in squad", path)
            return
        if off_side is not None and on_side is not off_side:
            self.issues.error("SUB_CROSS_TEAM", "substitution between different teams", path)
            return
        side = on_side
        if on_pid not in self._bench[side]:
            self.issues.error("SUB_NOT_ON_BENCH",
                              f"substitution: {on_pid} is not an unused substitute", path)
            return
        if self.state.used_subs[side] >= self.rules.substitutions_allowed:
            self.issues.error("SUB_LIMIT", f"{side.value} exceeded {self.rules.substitutions_allowed} substitutions",
                              path)
        window = (ev.clock.period, ev.clock.minute)
        windows = self.state.sub_windows[side]
        if window not in windows:
            # Half-time and pre-extra-time changes do not count as windows (IFAB); we treat a
            # change at a period's first minute as a break change. INFERRED approximation.
            is_break = ev.clock.minute in (self.rules.half_length_minutes, 2 * self.rules.half_length_minutes) \
                and ev.clock.second == 0 and ev.clock.added_minute == 0
            if not is_break:
                windows.append(window)
                if self.rules.substitution_windows is not None and len(windows) > self.rules.substitution_windows:
                    self.issues.error("SUB_WINDOWS", f"{side.value} exceeded substitution windows", path)
        self.state.used_subs[side] += 1
        minute = self.regulation_minute(ev.clock)
        if off_side is not None and ev.player_id is not None:
            self._leave(ev.player_id, side, minute, "substituted")
            self.state.substituted_off.add(ev.player_id)
        self._bench[side].discard(on_pid)
        self.state.on_pitch[side].add(on_pid)
        self.state.spells.setdefault(on_pid, []).append(PlayerSpell(entered=minute))

    def _on_yellow_card(self, ev: MatchEvent, path: str) -> None:
        side = self._require_player(ev, ev.player_id, path, role="booked player", on_pitch=False)
        if side is None:
            return
        if ev.player_id in self.state.dismissed:
            self.issues.error("CARD_AFTER_DISMISSAL", "yellow card for an already dismissed player", path)
        self.state.yellow[ev.player_id] += 1
        if self.state.yellow[ev.player_id] >= 2:
            self.issues.error("SECOND_YELLOW_AS_YELLOW", "second booking must be a second_yellow event", path)

    def _on_second_yellow(self, ev: MatchEvent, path: str) -> None:
        side = self._require_player(ev, ev.player_id, path, role="dismissed player")
        if side is None:
            return
        if self.state.yellow[ev.player_id] != 1:
            self.issues.error("SECOND_YELLOW_WITHOUT_FIRST", "second_yellow without exactly one prior yellow", path)
        self.state.yellow[ev.player_id] += 1
        self._dismiss(ev, side, path)

    def _on_red_card(self, ev: MatchEvent, path: str) -> None:
        side = self._require_player(ev, ev.player_id, path, role="dismissed player", on_pitch=False)
        if side is None:
            return
        self._dismiss(ev, side, path)

    def _dismiss(self, ev: MatchEvent, side: Side, path: str) -> None:
        pid = ev.player_id
        assert pid is not None
        if pid in self.state.dismissed:
            self.issues.error("DOUBLE_DISMISSAL", f"{pid} dismissed twice", path)
            return
        self.state.dismissed.add(pid)
        self._leave(pid, side, self.regulation_minute(ev.clock), "dismissed")

    def _on_injury(self, ev: MatchEvent, path: str) -> None:
        side = self._require_player(ev, ev.player_id, path, role="injured player")
        if side is None:
            return
        self.state.injured.add(ev.player_id)
        # Forced-off injuries are followed by a substitution (or the team plays a man down);
        # the player leaving is represented by that substitution event, not here.

    def _on_shootout_kick(self, ev: MatchEvent, path: str) -> None:
        side = self._require_player(ev, ev.player_id, path, role="kicker")
        if side is not None and ev.detail.get("scored") is True:
            self.state.shootout[side] += 1

    def _on_full_time(self, ev: MatchEvent, path: str) -> None:
        if self.state.full_time is not None:
            self.issues.error("DUPLICATE_FULL_TIME", "more than one full_time event", path)
        self.state.full_time = ev.clock
        end = self.regulation_minute(ev.clock)
        for side in (Side.HOME, Side.AWAY):
            for pid in list(self.state.on_pitch[side]):
                spells = self.state.spells.get(pid)
                if spells and spells[-1].left is None:
                    spells[-1].left = end
                    spells[-1].left_reason = "full_time"

    # -- derived results -------------------------------------------------
    def minutes_played(self, pid: str) -> int:
        spells = self.state.spells.get(pid, [])
        if not spells:
            return 0
        total = 0.0
        end_default = self.regulation_minute(self.state.full_time) if self.state.full_time else 0.0
        for spell in spells:
            left = spell.left if spell.left is not None else end_default
            total += max(0.0, left - spell.entered)
        # Any appearance counts as at least one minute (INFERRED to match FM's appearance records).
        return max(1, int(round(total)))

    def appeared(self, pid: str) -> bool:
        return pid in self.state.spells


def validate_match_record(fixture: Fixture, record: ExternalMatchRecord) -> tuple[IssueCollector, MatchReplay]:
    """Full validation of a captured match against its fixture."""
    replay = MatchReplay(fixture)
    if record.fixture_id != fixture.fixture_id:
        replay.issues.error("FIXTURE_MISMATCH", "record.fixture_id does not match fixture")
    for ev in record.events:
        if ev.match_id != record.match_id:
            replay.issues.error("EVENT_MATCH_MISMATCH", f"event {ev.source_event_id} has foreign match_id")
    replay.replay(record.events)
    st = replay.state
    if record.completed_normally and st.full_time is None:
        replay.issues.error("NO_FULL_TIME", "match marked complete but has no full_time event")
    # Team stats must reconcile with the event-derived score.
    for ts in record.team_stats:
        if ts.goals != st.score[ts.side]:
            replay.issues.error("SCORE_MISMATCH",
                                f"{ts.side.value} team stats say {ts.goals} goals, events say {st.score[ts.side]}",
                                f"team_stats.{ts.side.value}")
    sides = Counter(ts.side for ts in record.team_stats)
    for side, n in sides.items():
        if n > 1:
            replay.issues.error("TEAM_STATS_DUPLICATE", f"multiple team stats for {side.value}")
    # Player stats must reference participants and reconcile goals/assists.
    seen = set()
    for ps in record.player_stats:
        path = f"player_stats.{ps.hybrid_player_id}"
        if ps.hybrid_player_id in seen:
            replay.issues.error("PLAYER_STATS_DUPLICATE", "duplicate player stats", path)
        seen.add(ps.hybrid_player_id)
        if not replay.appeared(ps.hybrid_player_id):
            replay.issues.error("STATS_FOR_NON_PARTICIPANT", "stats for a player who never played", path)
            continue
        if ps.goals != st.goals[ps.hybrid_player_id]:
            replay.issues.warning("PLAYER_GOALS_MISMATCH",
                                  f"player stats goals {ps.goals} vs events {st.goals[ps.hybrid_player_id]}", path)
        if ps.assists != st.assists[ps.hybrid_player_id]:
            replay.issues.warning("PLAYER_ASSISTS_MISMATCH",
                                  f"player stats assists {ps.assists} vs events {st.assists[ps.hybrid_player_id]}",
                                  path)
    if record.completed_normally and fixture.rules.penalty_shootout and st.full_time is not None:
        level = st.score[Side.HOME] == st.score[Side.AWAY]
        if level and Period.PENALTY_SHOOTOUT in st.periods_seen and st.shootout[Side.HOME] == st.shootout[Side.AWAY]:
            replay.issues.error("SHOOTOUT_UNRESOLVED", "shootout ended level")
    return replay.issues, replay
