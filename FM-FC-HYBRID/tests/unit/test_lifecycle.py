import unittest

import tests  # noqa: F401
from fmfc_hybrid.errors import ConcurrencyError, DuplicateImportError, InvalidTransitionError
from fmfc_hybrid.lifecycle import FAILURE_STATES, TERMINAL_STATES, TRANSITIONS, MatchLifecycle, MatchState as S
from fmfc_hybrid.storage import Database
from tests.fixtures.builders import fixture

HAPPY = [S.FM_STATE_CAPTURED, S.MATCH_PREPARED, S.MATCH_IN_PROGRESS, S.MATCH_DATA_CAPTURED, S.MATCH_VALIDATED,
         S.FM_IMPORT_PENDING, S.FM_IMPORT_COMPLETED, S.FM_IMPORT_VERIFIED]


class StateTableTests(unittest.TestCase):
    def test_every_state_has_an_entry(self):
        self.assertEqual(set(TRANSITIONS), set(S))

    def test_terminal_states_have_no_exits(self):
        for state in TERMINAL_STATES:
            self.assertEqual(TRANSITIONS[state], frozenset())

    def test_every_failure_state_can_recover_or_abandon(self):
        for state in FAILURE_STATES:
            with self.subTest(state=state):
                self.assertIn(S.ABANDONED, TRANSITIONS[state])
                self.assertTrue(TRANSITIONS[state] - {S.ABANDONED})

    def test_all_states_reachable_from_detection(self):
        seen, frontier = {S.FIXTURE_DETECTED}, [S.FIXTURE_DETECTED]
        while frontier:
            for nxt in TRANSITIONS[frontier.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        self.assertEqual(seen, set(S))


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.addCleanup(self.db.close)
        self.lc = MatchLifecycle(self.db)

    def test_happy_path_is_persisted(self):
        rec = self.lc.create(fixture())
        for state in HAPPY:
            rec = self.lc.transition(rec.match_id, state, expected_version=rec.version, reason=state.value)
        self.assertEqual(rec.state, S.FM_IMPORT_VERIFIED)
        self.assertEqual(rec.version, len(HAPPY))
        history = self.lc.history(rec.match_id)
        self.assertEqual([t.to_state for t in history], [S.FIXTURE_DETECTED] + HAPPY)
        self.assertEqual(self.lc.unfinished(), [])

    def test_illegal_transition(self):
        rec = self.lc.create(fixture())
        with self.assertRaises(InvalidTransitionError):
            self.lc.transition(rec.match_id, S.FM_IMPORT_PENDING, expected_version=0)
        self.assertEqual(self.lc.get(rec.match_id).state, S.FIXTURE_DETECTED)

    def test_optimistic_concurrency(self):
        rec = self.lc.create(fixture())
        self.lc.transition(rec.match_id, S.FM_STATE_CAPTURED, expected_version=0)
        with self.assertRaises(ConcurrencyError):  # a second worker holding the stale version
            self.lc.transition(rec.match_id, S.MATCH_PREPARED, expected_version=0)

    def test_one_live_match_per_fixture(self):
        rec = self.lc.create(fixture())
        with self.assertRaises(DuplicateImportError):
            self.lc.create(fixture())
        self.lc.transition(rec.match_id, S.ABANDONED, expected_version=0, reason="test")
        self.assertNotEqual(self.lc.create(fixture()).match_id, rec.match_id)

    def test_abandon_after_import_started_needs_confirmation(self):
        rec = self.lc.create(fixture())
        for state in HAPPY[:6]:
            rec = self.lc.transition(rec.match_id, state, expected_version=rec.version)
        with self.assertRaises(InvalidTransitionError):
            self.lc.transition(rec.match_id, S.ABANDONED, expected_version=rec.version)
        rec = self.lc.transition(rec.match_id, S.IMPORT_FAILED, expected_version=rec.version)
        rec = self.lc.transition(rec.match_id, S.ABANDONED, expected_version=rec.version,
                                 allow_unsafe_abandon=True, reason="operator verified FM untouched")
        self.assertEqual(rec.state, S.ABANDONED)

    def test_replay_after_interruption_starts_new_attempt(self):
        rec = self.lc.create(fixture())
        for state in HAPPY[:3]:
            rec = self.lc.transition(rec.match_id, state, expected_version=rec.version)
        self.assertEqual(rec.ledger_match_id, f"{rec.match_id}:1")
        rec = self.lc.transition(rec.match_id, S.MATCH_INTERRUPTED, expected_version=rec.version,
                                 error={"code": "MATCH_INTERRUPTED", "message": "quit"})
        self.assertEqual(rec.last_error["code"], "MATCH_INTERRUPTED")
        rec = self.lc.transition(rec.match_id, S.FM_STATE_CAPTURED, expected_version=rec.version)
        self.assertEqual(rec.attempt, 2)
        self.assertEqual(rec.ledger_match_id, f"{rec.match_id}:2")
        self.assertIsNone(rec.last_error)

    def test_fixture_rebinding_rules(self):
        rec = self.lc.create(fixture())
        from dataclasses import replace
        with self.assertRaises(InvalidTransitionError):
            self.lc.transition(rec.match_id, S.FM_STATE_CAPTURED, expected_version=0,
                               fixture=replace(fixture(), fixture_id="other"))
        rec = self.lc.transition(rec.match_id, S.FM_STATE_CAPTURED, expected_version=0,
                                 fixture=replace(fixture(), venue="Rebound Park"))
        self.assertEqual(rec.fixture.venue, "Rebound Park")

    def test_state_survives_reopen(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "career.sqlite"
            with Database(path) as db:
                lc = MatchLifecycle(db)
                rec = lc.create(fixture())
                lc.transition(rec.match_id, S.FM_STATE_CAPTURED, expected_version=0)
            with Database(path) as db:
                again = MatchLifecycle(db).get(rec.match_id)
                self.assertEqual(again.state, S.FM_STATE_CAPTURED)
                self.assertEqual(again.fixture, fixture())


if __name__ == "__main__":
    unittest.main()
