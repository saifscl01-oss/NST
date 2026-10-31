import unittest
from dataclasses import replace

import tests  # noqa: F401
from fmfc_hybrid.adapters.base import ImportReceipt, IntegrationLevel
from fmfc_hybrid.contracts.models import PlayerMatchStats, Side
from fmfc_hybrid.errors import DuplicateImportError, ImportFailedError, ValidationError
from fmfc_hybrid.result_processor import ImportGuard, RatingScale, ResultProcessor, idempotency_key
from fmfc_hybrid.storage import Database
from tests.fixtures.builders import fixture, record, simple_match


def fm_id(pid: str) -> int:
    return abs(hash(pid)) % 100000


class ProcessorTests(unittest.TestCase):
    def test_package_contents(self):
        rec = record(simple_match(), 1, 1, player_stats=[PlayerMatchStats("h10", Side.HOME, rating=8.0, goals=1)])
        pkg = ResultProcessor().build_package(fixture(), rec, "abc", fm_id)
        self.assertEqual((pkg.home_goals, pkg.away_goals), (1, 1))
        apps = {a.hybrid_player_id: a for a in pkg.appearances}
        self.assertEqual(len(apps), 23)  # 22 starters + one substitute
        self.assertEqual(apps["h9"].minutes_played, 60)
        self.assertEqual(apps["h9"].assists, 1)
        self.assertTrue(apps["hb0"].minutes_played == 30 and not apps["hb0"].started)
        self.assertEqual(apps["a5"].yellow_cards, 1)
        self.assertEqual(apps["h10"].rating, 8.2)  # 0-10 -> 1-10 linear
        self.assertIsNone(apps["h0"].rating)
        self.assertNotIn("hb1", apps)
        self.assertEqual(pkg.idempotency_key, idempotency_key("career-test", "FX-test", "abc"))

    def test_invalid_record_cannot_become_a_package(self):
        with self.assertRaises(ValidationError):
            ResultProcessor().build_package(fixture(), record(simple_match(), 3, 0), "x", fm_id)

    def test_rating_scale(self):
        scale = RatingScale(0, 10, 1, 10)
        self.assertEqual(scale.convert(0), 1.0)
        self.assertEqual(scale.convert(10), 10.0)
        self.assertEqual(scale.convert(15), 10.0)
        self.assertIsNone(scale.convert(None))


class ImportGuardTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.addCleanup(self.db.close)
        self.guard = ImportGuard(self.db)
        self.pkg = ResultProcessor().build_package(fixture(), record(simple_match(), 1, 1), "h1", fm_id)

    def receipt(self, key=None):
        return ImportReceipt(key or self.pkg.idempotency_key, "fm-ref-1", IntegrationLevel.RESULT_AND_STATS, "t")

    def test_once_only(self):
        self.assertEqual(self.guard.begin(self.pkg, "M1"), "new")
        self.assertEqual(self.guard.begin(self.pkg, "M1"), "resume")  # crash before completion
        self.guard.complete(self.receipt())
        with self.assertRaises(DuplicateImportError):
            self.guard.begin(self.pkg, "M1")
        self.guard.verified(self.pkg.idempotency_key)
        self.assertEqual(self.guard.status("career-test", "FX-test")["status"], "verified")
        self.assertEqual(self.guard.receipt("career-test", "FX-test")["integration_level_name"], "RESULT_AND_STATS")

    def test_different_record_for_same_fixture_refused(self):
        self.guard.begin(self.pkg, "M1")
        other = replace(self.pkg, idempotency_key="different")
        with self.assertRaises(DuplicateImportError):
            self.guard.begin(other, "M2")

    def test_failed_import_can_resume(self):
        self.guard.begin(self.pkg, "M1")
        self.guard.failed(self.pkg.idempotency_key, ImportFailedError("boom", retryable=True))
        self.assertEqual(self.guard.begin(self.pkg, "M1"), "resume")
        log = [r["action"] for r in self.db.query_all("SELECT action FROM import_attempts_log ORDER BY id")]
        self.assertEqual(log, ["begin", "failed", "resume"])


if __name__ == "__main__":
    unittest.main()
