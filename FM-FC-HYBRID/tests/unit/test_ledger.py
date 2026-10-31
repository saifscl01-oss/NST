import sqlite3
import unittest
from dataclasses import replace

import tests  # noqa: F401
from fmfc_hybrid.contracts.models import EventType, MatchClock, MatchEvent, Period, Side
from fmfc_hybrid.errors import DuplicateEventError, LedgerError, LedgerFinalizedError
from fmfc_hybrid.ledger import EventLedger
from fmfc_hybrid.storage import Database
from tests.fixtures.builders import MATCH, record, simple_match


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.addCleanup(self.db.close)
        self.ledger = EventLedger(self.db)
        self.events = simple_match()

    def test_append_and_read_back_in_order(self):
        res = self.ledger.append(reversed(self.events))
        self.assertEqual(res.appended, len(self.events))
        self.assertEqual(self.ledger.events(MATCH), self.events)
        self.assertTrue(self.ledger.verify(MATCH).ok)

    def test_identical_redelivery_is_ignored(self):
        self.ledger.append(self.events[:3])
        res = self.ledger.append(self.events)
        self.assertEqual((res.appended, res.duplicates_ignored), (len(self.events) - 3, 3))
        self.assertEqual(len(self.ledger.events(MATCH)), len(self.events))

    def test_conflicting_redelivery_rejected(self):
        self.ledger.append(self.events)
        tampered = replace(self.events[0], player_id="h7")
        with self.assertRaises(DuplicateEventError):
            self.ledger.append([tampered])

    def test_sequence_must_advance(self):
        self.ledger.append(self.events[2:])
        with self.assertRaises(LedgerError):
            self.ledger.append(self.events[:1])

    def test_finalize_freezes_ledger(self):
        self.ledger.append(self.events)
        fin = self.ledger.finalize(record(self.events, 1, 1))
        self.assertEqual(fin.event_count, len(self.events))
        self.assertEqual(self.ledger.finalize(record(self.events, 1, 1)), fin)  # idempotent
        late = MatchEvent(MATCH, "late", 99, MatchClock(Period.SECOND_HALF, 90, 9), EventType.GOAL, Side.HOME, "h10")
        with self.assertRaises(LedgerFinalizedError):
            self.ledger.append([late])
        with self.assertRaises(sqlite3.IntegrityError):  # database-level guard, bypassing the API
            self.db.execute("INSERT INTO ledger_events VALUES (?,?,?,?,?,?,?,?)",
                            (MATCH, 99, "raw", "{}", "x", "y", "z", "now"))
        with self.assertRaises(LedgerFinalizedError):
            self.ledger.finalize(record(self.events, 1, 1, completed=False))

    def test_finalize_requires_matching_events(self):
        self.ledger.append(self.events[:-1])
        with self.assertRaises(LedgerError):
            self.ledger.finalize(record(self.events, 1, 1))

    def test_rows_are_immutable(self):
        self.ledger.append(self.events)
        for sql in ("UPDATE ledger_events SET event_json='{}'", "DELETE FROM ledger_events",
                    "UPDATE audit_log SET actor='x'", "DELETE FROM audit_log"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(sql)

    def test_tampering_is_detected(self):
        self.ledger.append(self.events)
        self.db.execute("DROP TRIGGER trg_ledger_events_no_update")  # simulate an attacker with file access
        self.db.execute("UPDATE ledger_events SET event_json=replace(event_json,'h10','h3') WHERE seq=1")
        report = self.ledger.verify(MATCH)
        self.assertFalse(report.ok)
        self.assertTrue(any("content hash" in p for p in report.problems))

    def test_corrections_are_separate_and_audited(self):
        self.ledger.append(self.events)
        with self.assertRaises(LedgerError):  # not finalized yet
            self.ledger.add_correction(MATCH, correction_type="void_event", reason="x", author="me",
                                       target_source_event_id="e2")
        self.ledger.finalize(record(self.events, 1, 1))
        fixed = replace(self.events[0], secondary_player_id=None, source_event_id="e1-fix")
        self.ledger.add_correction(MATCH, correction_type="replace_event", reason="assist was wrongly credited",
                                   author="operator", target_source_event_id="e1", replacement=fixed)
        self.ledger.add_correction(MATCH, correction_type="void_event", reason="phantom booking",
                                   author="operator", target_source_event_id="e2")
        effective = self.ledger.effective_events(MATCH)
        self.assertEqual([e.source_event_id for e in effective], ["e1-fix", "e3", "e4", "e5"])
        self.assertEqual(self.ledger.events(MATCH), self.events)  # originals untouched
        rec = self.ledger.finalized_record(MATCH)
        self.assertEqual(len(rec.events), 4)
        self.assertEqual(len(self.ledger.finalized_record(MATCH, with_corrections=False).events), 5)
        actions = [a["action"] for a in self.db.audit_trail("match", MATCH)]
        self.assertEqual(actions.count("ledger.correction"), 2)
        with self.assertRaises(LedgerError):
            self.ledger.add_correction(MATCH, correction_type="void_event", reason=" ", author="x",
                                       target_source_event_id="e3")
        with self.assertRaises(LedgerError):
            self.ledger.add_correction(MATCH, correction_type="void_event", reason="r", author="x",
                                       target_source_event_id="nope")

    def test_export(self):
        self.ledger.append(self.events)
        self.ledger.finalize(record(self.events, 1, 1))
        exported = self.ledger.export(MATCH)
        self.assertTrue(exported["integrity"]["ok"])
        self.assertEqual(len(exported["events"]), 5)


if __name__ == "__main__":
    unittest.main()
