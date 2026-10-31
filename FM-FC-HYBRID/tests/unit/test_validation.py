import unittest
from dataclasses import replace

import tests  # noqa: F401
from fmfc_hybrid.contracts.models import EventType, LineupSlot, Period, PlayerMatchStats, Side
from fmfc_hybrid.contracts.validation import MatchReplay, validate_fixture, validate_match_record
from tests.fixtures.builders import Events, fixture, record, simple_match


def codes(collector):
    return {i.code for i in collector.errors}


class FixtureValidationTests(unittest.TestCase):
    def test_valid_fixture(self):
        self.assertEqual(validate_fixture(fixture()).errors, [])

    def test_structural_errors(self):
        f = fixture()
        cases = {
            "STARTERS_COUNT": replace(f, home=replace(f.home, starters=f.home.starters[:10])),
            "GOALKEEPER_COUNT": replace(f, home=replace(f.home, starters=(LineupSlot(0, "h0", "DC"),)
                                                        + f.home.starters[1:])),
            "PLAYER_DUPLICATE": replace(f, home=replace(f.home, bench=("h1",) + f.home.bench)),
            "PLAYER_BOTH_SQUADS": replace(f, away=replace(f.away, bench=("h1",))),
            "BENCH_SIZE": replace(f, home=replace(f.home, bench=tuple(f"x{i}" for i in range(10)))),
            "SAME_CLUB": replace(f, away=replace(f.away, club=f.home.club)),
            "CAPTAIN_NOT_IN_SQUAD": replace(f, home=replace(f.home, captain_id="ghost")),
            "POSITION_UNKNOWN": replace(f, home=replace(f.home, starters=f.home.starters[:10]
                                                        + (LineupSlot(10, "h10", "XX"),))),
            "SLOT_DUPLICATE": replace(f, home=replace(f.home, starters=f.home.starters[:10]
                                                      + (LineupSlot(9, "h10", "ST"),))),
            "FIXTURE_ID_MISSING": replace(f, fixture_id=""),
        }
        for code, bad in cases.items():
            with self.subTest(code=code):
                self.assertIn(code, codes(validate_fixture(bad)))

    def test_captain_on_bench_is_warning(self):
        f = fixture()
        out = validate_fixture(replace(f, home=replace(f.home, captain_id="hb0")))
        self.assertEqual(out.errors, [])
        self.assertIn("CAPTAIN_ON_BENCH", {w.code for w in out.warnings})


class ReplayTests(unittest.TestCase):
    def test_valid_match(self):
        issues, replay = validate_match_record(fixture(), record(simple_match(), 1, 1))
        self.assertEqual(issues.errors, [])
        st = replay.state
        self.assertEqual(st.score, {Side.HOME: 1, Side.AWAY: 1})
        self.assertEqual(st.assists["h9"], 1)
        self.assertEqual(replay.minutes_played("h9"), 60)
        self.assertEqual(replay.minutes_played("hb0"), 30)
        self.assertEqual(replay.minutes_played("h0"), 90)
        self.assertFalse(replay.appeared("hb1"))

    def run_events(self, events, **rules):
        r = MatchReplay(fixture(**rules))
        r.replay(events)
        return codes(r.issues), r

    def test_player_must_be_on_pitch(self):
        c, _ = self.run_events(Events().add(EventType.GOAL, 10, Side.HOME, "hb0").items)
        self.assertIn("PLAYER_NOT_ON_PITCH", c)

    def test_subbed_off_player_cannot_return_or_score(self):
        ev = (Events().add(EventType.SUBSTITUTION, 50, Side.HOME, "h9", "hb0")
              .add(EventType.GOAL, 70, Side.HOME, "h9")
              .add(EventType.SUBSTITUTION, 75, Side.HOME, "h8", "h9"))
        c, _ = self.run_events(ev.items)
        self.assertIn("PLAYER_NOT_ON_PITCH", c)
        self.assertIn("SUB_NOT_ON_BENCH", c)

    def test_substitution_limit_and_windows(self):
        ev = Events()
        for i, minute in enumerate((50, 55, 60, 65)):
            ev.add(EventType.SUBSTITUTION, minute, Side.HOME, f"h{i + 1}", f"hb{i}")
        c, _ = self.run_events(ev.items, substitutions_allowed=3)
        self.assertIn("SUB_LIMIT", c)
        self.assertIn("SUB_WINDOWS", c)

    def test_half_time_change_does_not_use_a_window(self):
        ev = Events().add(EventType.SUBSTITUTION, 45, Side.HOME, "h1", "hb0", period=Period.SECOND_HALF)
        for i, minute in enumerate((60, 70, 80)):
            ev.add(EventType.SUBSTITUTION, minute, Side.HOME, f"h{i + 2}", f"hb{i + 1}")
        c, _ = self.run_events(ev.items)
        self.assertNotIn("SUB_WINDOWS", c)

    def test_cards(self):
        c, r = self.run_events(Events().add(EventType.SECOND_YELLOW, 20, Side.AWAY, "a3").items)
        self.assertIn("SECOND_YELLOW_WITHOUT_FIRST", c)
        ev = (Events().add(EventType.YELLOW_CARD, 10, Side.AWAY, "a3")
              .add(EventType.SECOND_YELLOW, 40, Side.AWAY, "a3")
              .add(EventType.GOAL, 50, Side.AWAY, "a3"))
        c, r = self.run_events(ev.items)
        self.assertIn("PLAYER_NOT_ON_PITCH", c)
        self.assertIn("a3", r.state.dismissed)
        self.assertEqual(r.minutes_played("a3"), 40)
        c, _ = self.run_events(Events().add(EventType.YELLOW_CARD, 10, Side.AWAY, "a3")
                               .add(EventType.YELLOW_CARD, 20, Side.AWAY, "a3").items)
        self.assertIn("SECOND_YELLOW_AS_YELLOW", c)

    def test_own_goal_credits_opponent(self):
        _, r = self.run_events(Events().add(EventType.OWN_GOAL, 33, Side.AWAY, "a2").items)
        self.assertEqual(r.state.score, {Side.HOME: 1, Side.AWAY: 0})

    def test_assist_rules(self):
        c, _ = self.run_events(Events().add(EventType.GOAL, 5, Side.HOME, "h10", "h10").items)
        self.assertIn("SELF_ASSIST", c)
        c, _ = self.run_events(Events().add(EventType.GOAL, 5, Side.HOME, "h10", "a4").items)
        self.assertIn("SIDE_MISMATCH", c)

    def test_ordering_and_duplicates(self):
        ev = Events().add(EventType.GOAL, 50, Side.HOME, "h10").add(EventType.GOAL, 20, Side.HOME, "h10")
        c, _ = self.run_events(ev.items)
        self.assertIn("CLOCK_REGRESSION", c)
        items = Events().add(EventType.GOAL, 5, Side.HOME, "h10").items
        dup = replace(items[0], sequence=2)
        c, r = self.run_events(items + [dup])
        self.assertIn("DUPLICATE_SOURCE_EVENT", c)
        self.assertEqual(r.state.score[Side.HOME], 1)

    def test_events_after_full_time_and_unknown_players(self):
        ev = Events().full_time().add(EventType.GOAL, 90, Side.HOME, "h10", added=5)
        c, _ = self.run_events(ev.items)
        self.assertIn("EVENT_AFTER_FULL_TIME", c)
        c, _ = self.run_events(Events().add(EventType.GOAL, 5, Side.HOME, "stranger").items)
        self.assertIn("PLAYER_NOT_IN_FIXTURE", c)

    def test_extra_time_requires_rules(self):
        ev = Events().add(EventType.GOAL, 100, Side.HOME, "h10", period=Period.EXTRA_TIME_FIRST)
        self.assertIn("EXTRA_TIME_NOT_ALLOWED", self.run_events(ev.items)[0])
        self.assertNotIn("EXTRA_TIME_NOT_ALLOWED", self.run_events(ev.items, extra_time=True)[0])

    def test_record_level_checks(self):
        f = fixture()
        issues, _ = validate_match_record(f, record(simple_match(), 2, 1))
        self.assertIn("SCORE_MISMATCH", codes(issues))
        no_ft = [e for e in simple_match() if e.type is not EventType.FULL_TIME]
        issues, _ = validate_match_record(f, record(no_ft, 1, 1))
        self.assertIn("NO_FULL_TIME", codes(issues))
        issues, _ = validate_match_record(f, record(simple_match(), 1, 1, player_stats=[
            PlayerMatchStats("hb5", Side.HOME)]))
        self.assertIn("STATS_FOR_NON_PARTICIPANT", codes(issues))
        issues, _ = validate_match_record(f, record(simple_match(), 1, 1, player_stats=[
            PlayerMatchStats("h10", Side.HOME, goals=3)]))
        self.assertIn("PLAYER_GOALS_MISMATCH", {w.code for w in issues.warnings})


if __name__ == "__main__":
    unittest.main()
