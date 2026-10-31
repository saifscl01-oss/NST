"""End-to-end lifecycle tests against the mock adapters, including failure and crash recovery."""

import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401
from fmfc_hybrid.adapters.base import IntegrationLevel
from fmfc_hybrid.adapters.mock_fifa import MockFifa
from fmfc_hybrid.adapters.mock_fm import MockFootballManager, SimulatedCrash
from fmfc_hybrid.bridge import BridgeConfig, MatchOrchestrator
from fmfc_hybrid.errors import DuplicateImportError, InvalidTransitionError
from fmfc_hybrid.ledger import EventLedger
from fmfc_hybrid.lifecycle import MatchState as S
from fmfc_hybrid.storage import Database


class Harness(unittest.TestCase):
    def make(self, db=None, fm=None, fifa=None, **cfg):
        self.db = db or Database()
        self.addCleanup(self.db.close)
        self.fm = fm or MockFootballManager()
        self.fifa = fifa or MockFifa()
        self.orch = MatchOrchestrator(self.db, self.fm, self.fifa, config=BridgeConfig(**cfg))
        return self.orch

    def states(self, match_id):
        return [t.to_state for t in self.orch.lifecycle.history(match_id)]

    def fixture_record(self):
        return self.fm.fixtures[0]


class HappyPathTests(Harness):
    def test_full_lifecycle(self):
        o = self.make()
        rec = o.begin()
        out = o.run(rec.match_id)
        self.assertEqual(out.state, S.FM_IMPORT_VERIFIED)
        self.assertTrue(out.full_integration)
        self.assertEqual(self.states(rec.match_id), [
            S.FIXTURE_DETECTED, S.FM_STATE_CAPTURED, S.MATCH_PREPARED, S.MATCH_IN_PROGRESS,
            S.MATCH_DATA_CAPTURED, S.MATCH_VALIDATED, S.FM_IMPORT_PENDING, S.FM_IMPORT_COMPLETED,
            S.FM_IMPORT_VERIFIED])
        f = self.fixture_record()
        self.assertEqual(f.import_count, 1)
        self.assertEqual(f.result, out.score)
        self.assertIn(f.ref, self.fm.suppressed)
        self.assertEqual(self.fm.table[self.fm.managed_club]["played"], 1)
        # Every player in both squads is registered with a stable hybrid id and a FIFA link.
        reg = o.registry(rec.career_id)
        final = o.lifecycle.get(rec.match_id)
        for pid in final.fixture.home.all_player_ids() + final.fixture.away.all_player_ids():
            self.assertIsNotNone(reg.get(pid).fifa_player_id)
        # Preservation copy and audit trail exist.
        kinds = {r["kind"] for r in self.db.query_all("SELECT kind FROM state_snapshots WHERE match_id=?",
                                                      (rec.match_id,))}
        self.assertTrue({"fm_pre_match_state", "fifa_match_request", "external_match_record",
                         "fm_import_package", "tactical_translation"} <= kinds)
        self.assertTrue(EventLedger(self.db).is_finalized(final.ledger_match_id))
        self.assertGreaterEqual(len(self.db.audit_trail("match", rec.match_id)), 9)

    def test_whole_season_keeps_identities_stable(self):
        o = self.make()
        seen = {}
        for _ in range(3):
            rec = o.begin()
            self.assertEqual(o.run(rec.match_id).state, S.FM_IMPORT_VERIFIED)
            for p in o.lifecycle.get(rec.match_id).fixture.home.starters:
                fm_id = o.registry(rec.career_id).get(p.hybrid_player_id).fm_player_id
                seen.setdefault(fm_id, p.hybrid_player_id)
                self.assertEqual(seen[fm_id], p.hybrid_player_id)
        self.assertIsNone(o.begin())  # season over
        self.assertEqual(self.fm.table[self.fm.managed_club]["played"], 3)
        self.assertTrue(all(f.import_count == 1 for f in self.fm.fixtures))

    def test_begin_is_idempotent_and_reimport_is_refused(self):
        o = self.make()
        a = o.begin()
        self.assertEqual(o.begin().match_id, a.match_id)
        o.run(a.match_id)
        fixture = o.lifecycle.get(a.match_id).fixture
        with self.assertRaises(DuplicateImportError):
            o.lifecycle.create(fixture)

    def test_partial_integration_is_never_reported_as_full(self):
        o = self.make(fm=MockFootballManager(max_level=IntegrationLevel.SCORE_ONLY))
        out = o.run(o.begin().match_id)
        self.assertEqual(out.state, S.FM_IMPORT_VERIFIED)
        self.assertFalse(out.full_integration)
        self.assertIn("PARTIAL", out.message)

    def test_fm_route_without_suppression_is_refused(self):
        o = self.make(fm=MockFootballManager(can_suppress=False))
        out = o.run(o.begin().match_id)
        self.assertEqual(out.state, S.CAPTURE_FAILED)
        self.assertTrue(out.needs_operator)
        o2 = self.make(fm=MockFootballManager(can_suppress=False), require_simulation_suppression=False)
        self.assertEqual(o2.run(o2.begin().match_id).state, S.FM_IMPORT_VERIFIED)


class FailureRecoveryTests(Harness):
    def test_retryable_faults_recover_automatically(self):
        cases = [("fm", "capture_fail_once", S.CAPTURE_FAILED), ("fifa", "prepare_fail_once", S.PREPARATION_FAILED),
                 ("fifa", "launch_fail_once", S.LAUNCH_FAILED), ("fifa", "capture_fail_once", S.DATA_CAPTURE_FAILED),
                 ("fm", "import_fail_once", S.IMPORT_FAILED)]
        for target, fault, failure_state in cases:
            with self.subTest(fault=fault):
                o = self.make()
                (self.fm if target == "fm" else self.fifa).faults.add(fault)
                rec = o.begin()
                out = o.run(rec.match_id)
                self.assertEqual(out.state, S.FM_IMPORT_VERIFIED)
                self.assertIn(failure_state, self.states(rec.match_id))
                self.assertEqual(self.fixture_record().import_count, 1)

    def test_retries_are_bounded(self):
        o = self.make(max_automatic_retries=1)
        rec = o.begin()
        self.fm.faults.add("capture_fail_once")
        o.step(rec.match_id)                       # fails
        self.fm.faults.add("capture_fail_once")
        out = o.run(rec.match_id)                  # retry 1 fails again -> stop
        self.assertEqual(out.state, S.CAPTURE_FAILED)
        self.assertTrue(out.needs_operator)
        o.retry(rec.match_id, "operator checked FM")
        self.assertEqual(o.run(rec.match_id).state, S.FM_IMPORT_VERIFIED)

    def test_interrupted_match_waits_for_operator_then_replays_cleanly(self):
        o = self.make()
        self.fifa.faults.add("interrupt_once")
        rec = o.begin()
        out = o.run(rec.match_id)
        self.assertEqual(out.state, S.MATCH_INTERRUPTED)
        self.assertEqual(self.fixture_record().import_count, 0)  # FM untouched
        o.replay(rec.match_id, "user quit the FIFA match")
        out = o.run(rec.match_id)
        self.assertEqual(out.state, S.FM_IMPORT_VERIFIED)
        final = o.lifecycle.get(rec.match_id)
        self.assertEqual(final.attempt, 2)
        ledger = EventLedger(self.db)
        self.assertFalse(ledger.is_finalized(f"{rec.match_id}:1"))  # partial attempt kept for audit only
        self.assertTrue(ledger.is_finalized(f"{rec.match_id}:2"))

    def test_invalid_capture_is_not_imported(self):
        o = self.make()
        self.fifa.faults.add("drop_full_time")
        rec = o.begin()
        out = o.run(rec.match_id)
        self.assertEqual(out.state, S.VALIDATION_FAILED)
        codes = {i["code"] for i in o.lifecycle.get(rec.match_id).last_error["details"]["issues"]}
        self.assertIn("NO_FULL_TIME", codes)
        self.assertEqual(self.fixture_record().import_count, 0)

    def test_verification_failure_stops_for_operator(self):
        o = self.make()
        self.fm.faults.add("tamper_verification")
        rec = o.begin()
        out = o.run(rec.match_id)
        self.assertEqual(out.state, S.VERIFICATION_FAILED)
        with self.assertRaises(InvalidTransitionError):
            o.abandon(rec.match_id, "give up")  # FM may hold the result: unsafe without confirmation

    def test_crash_after_fm_applied_result_never_double_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "career.sqlite"
            fm, fifa = MockFootballManager(), MockFifa()
            fm.faults.add("crash_after_apply_once")
            db1 = Database(path)
            o1 = MatchOrchestrator(db1, fm, fifa)
            rec = o1.begin()
            with self.assertRaises(SimulatedCrash):
                o1.run(rec.match_id)
            db1.close()
            self.assertEqual(fm.fixtures[0].import_count, 1)
            # Restart: new process, same database and game.
            db2 = Database(path)
            self.addCleanup(db2.close)
            o2 = MatchOrchestrator(db2, fm, fifa)
            self.assertEqual(o2.lifecycle.get(rec.match_id).state, S.FM_IMPORT_PENDING)
            outcomes = o2.recover_all()
            self.assertEqual([x.state for x in outcomes], [S.FM_IMPORT_VERIFIED])
            self.assertEqual(fm.fixtures[0].import_count, 1)
            reasons = [t.reason for t in o2.lifecycle.history(rec.match_id)]
            self.assertIn("recovered: FM already applied this package", reasons)

    def test_crash_mid_match_resumes_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "career.sqlite"
            fm, fifa = MockFootballManager(), MockFifa()
            db1 = Database(path)
            o1 = MatchOrchestrator(db1, fm, fifa)
            rec = o1.begin()
            for _ in range(3):
                o1.step(rec.match_id)
            self.assertEqual(o1.lifecycle.get(rec.match_id).state, S.MATCH_IN_PROGRESS)
            db1.close()
            db2 = Database(path)
            self.addCleanup(db2.close)
            out = MatchOrchestrator(db2, fm, fifa).recover_all()
            self.assertEqual(out[0].state, S.FM_IMPORT_VERIFIED)
            self.assertEqual(fm.fixtures[0].import_count, 1)

    def test_fm_holding_foreign_result_is_a_conflict(self):
        o = self.make()
        rec = o.begin()
        for _ in range(6):
            o.step(rec.match_id)
        self.assertEqual(o.lifecycle.get(rec.match_id).state, S.FM_IMPORT_PENDING)
        from fmfc_hybrid.adapters.base import ImportReceipt
        self.fixture_record().receipt = ImportReceipt("someone-else", self.fixture_record().ref,
                                                      IntegrationLevel.SCORE_ONLY, "now")
        out = o.run(rec.match_id)
        self.assertEqual(out.state, S.IMPORT_FAILED)
        self.assertEqual(o.lifecycle.get(rec.match_id).last_error["code"], "DUPLICATE_IMPORT")


if __name__ == "__main__":
    unittest.main()
