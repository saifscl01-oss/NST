"""Fuzz the whole pipeline across many seeds.

This caught a real generator bug (events in the same minute emitted out of
order), which the validator rejected as CLOCK_REGRESSION.
"""
import unittest

import tests  # noqa: F401
from fmfc_hybrid.adapters.mock_fifa import MockFifa
from fmfc_hybrid.adapters.mock_fm import MockFootballManager
from fmfc_hybrid.bridge import MatchOrchestrator
from fmfc_hybrid.contracts.serialization import from_primitive
from fmfc_hybrid.contracts.models import ExternalMatchRecord
from fmfc_hybrid.contracts.validation import validate_match_record
from fmfc_hybrid.lifecycle import MatchState
from fmfc_hybrid.storage import Database


class PipelineFuzzTests(unittest.TestCase):
    SEEDS = range(60)

    def test_many_seeds_verify(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed), Database() as db:
                fm = MockFootballManager(seed=seed % 17)
                orch = MatchOrchestrator(db, fm, MockFifa(seed=seed))
                rec = orch.begin()
                out = orch.run(rec.match_id)
                self.assertEqual(out.state, MatchState.FM_IMPORT_VERIFIED, out.message)
                self.assertEqual(fm.fixtures[0].import_count, 1)
                raw = orch._snapshot(rec.match_id, "external_match_record")
                issues, replay = validate_match_record(orch.lifecycle.get(rec.match_id).fixture,
                                                       from_primitive(ExternalMatchRecord, raw))
                self.assertEqual(issues.errors, [])
                minutes = [replay.minutes_played(p) for p in replay.state.spells]
                self.assertTrue(all(0 < m <= 90 for m in minutes))


if __name__ == "__main__":
    unittest.main()
