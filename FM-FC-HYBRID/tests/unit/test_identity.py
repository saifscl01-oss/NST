import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import tests  # noqa: F401
from fmfc_hybrid.adapters.mock_fm import MockFootballManager
from fmfc_hybrid.contracts.models import FifaLinkStatus, PlayerOrigin
from fmfc_hybrid.errors import IdentityError
from fmfc_hybrid.identity import FifaIdPolicy, PlayerRegistry
from fmfc_hybrid.storage import Database


def profiles(n=3):
    fm = MockFootballManager(seed=3)
    return list(fm.players.values())[:n]


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.addCleanup(self.db.close)
        self.reg = PlayerRegistry(self.db, "career-1", FifaIdPolicy(500, 503))
        self.p = profiles()

    def test_hybrid_id_is_stable(self):
        first = self.reg.register(self.p[0])
        again = self.reg.register(self.p[0])
        self.assertEqual(first.hybrid_player_id, again.hybrid_player_id)
        self.assertTrue(first.hybrid_player_id.startswith("HP-"))
        self.assertEqual(len(self.reg.snapshot_history(first.hybrid_player_id)), 1)

    def test_transfer_and_development_keep_identity(self):
        rec = self.reg.register(self.p[0])
        self.reg.link_fifa(rec.hybrid_player_id, 123)
        attrs = replace(self.p[0].attributes, technical={**self.p[0].attributes.technical, "finishing": 20})
        moved = replace(self.p[0], club_fm_id=999, attributes=attrs)
        after = self.reg.register(moved, reason="transfer")
        self.assertEqual(after.hybrid_player_id, rec.hybrid_player_id)
        self.assertEqual(after.profile.club_fm_id, 999)
        self.assertEqual(after.fifa_link_status, FifaLinkStatus.STALE)
        self.assertEqual(len(self.reg.snapshot_history(rec.hybrid_player_id)), 2)
        changes = [a for a in self.db.audit_trail("player", rec.hybrid_player_id) if a["action"] == "player.update"]
        self.assertIn("club_fm_id", changes[0]["payload"]["changes"])
        self.assertIn("attr.finishing", changes[0]["payload"]["changes"])
        synced = self.reg.mark_fifa_synced(rec.hybrid_player_id)
        self.assertEqual(synced.fifa_link_status, FifaLinkStatus.MATCHED)
        self.assertIsNotNone(synced.last_fifa_sync_at)

    def test_identity_conflicts_refused(self):
        rec = self.reg.register(self.p[0])
        with self.assertRaises(IdentityError):
            self.reg.register(replace(self.p[0], date_of_birth="1970-01-01"))
        other = self.reg.register(self.p[1])
        self.reg.link_fifa(rec.hybrid_player_id, 77)
        with self.assertRaises(IdentityError):
            self.reg.link_fifa(other.hybrid_player_id, 77)
        with self.assertRaises(IdentityError):
            self.reg.link_fifa(rec.hybrid_player_id, 78)
        self.assertEqual(self.reg.link_fifa(rec.hybrid_player_id, 78, relink=True).fifa_player_id, 78)

    def test_allocation_never_reuses_ids(self):
        a = self.reg.register(self.p[0])
        b = self.reg.register(self.p[1])
        c = self.reg.register(self.p[2])
        ida = self.reg.allocate_fifa_id(a.hybrid_player_id).fifa_player_id
        self.assertEqual(ida, 500)
        self.assertEqual(self.reg.allocate_fifa_id(a.hybrid_player_id).fifa_player_id, 500)  # idempotent
        self.reg.retire(a.hybrid_player_id)
        idb = self.reg.allocate_fifa_id(b.hybrid_player_id, occupied=lambda i: i == 501).fifa_player_id
        self.assertEqual(idb, 502)
        self.assertEqual(self.reg.get(a.hybrid_player_id).status, "retired")
        self.assertEqual(self.reg.get(a.hybrid_player_id).fifa_player_id, 500)
        self.assertEqual(self.reg.allocate_fifa_id(c.hybrid_player_id).fifa_link_status, FifaLinkStatus.CREATED)
        d = self.reg.register(profiles(4)[3])
        with self.assertRaises(IdentityError):
            self.reg.allocate_fifa_id(d.hybrid_player_id)  # range 500..503 exhausted

    def test_regens_and_queries(self):
        regen = replace(self.p[0], fm_player_id=777777, origin=PlayerOrigin.REGEN)
        rec = self.reg.register(regen)
        self.assertEqual(rec.profile.origin, PlayerOrigin.REGEN)
        self.assertEqual(self.reg.get_by_fm(777777).hybrid_player_id, rec.hybrid_player_id)
        self.assertIn(rec.hybrid_player_id, [r.hybrid_player_id for r in self.reg.needing_fifa_sync()])
        self.assertIsNone(self.reg.get_by_fifa(1))
        with self.assertRaises(IdentityError):
            self.reg.get("HP-missing")

    def test_careers_are_isolated(self):
        rec = self.reg.register(self.p[0])
        other = PlayerRegistry(self.db, "career-2")
        rec2 = other.register(self.p[0])
        self.assertNotEqual(rec.hybrid_player_id, rec2.hybrid_player_id)
        with self.assertRaises(IdentityError):
            other.get(rec.hybrid_player_id)

    def test_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.sqlite"
            with Database(path) as db:
                hid = PlayerRegistry(db, "c").register(self.p[0]).hybrid_player_id
            with Database(path) as db:
                self.assertEqual(PlayerRegistry(db, "c").register(self.p[0]).hybrid_player_id, hid)


if __name__ == "__main__":
    unittest.main()
