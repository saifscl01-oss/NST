import json
import unittest
from dataclasses import replace
from pathlib import Path

import tests  # noqa: F401  (sys.path setup)
from fmfc_hybrid.adapters.mock_fm import MockFootballManager
from fmfc_hybrid.contracts import envelope
from fmfc_hybrid.contracts.jsonschema import render_all
from fmfc_hybrid.contracts.models import Fixture, MatchEvent, PlayerProfile, TacticalPlan
from fmfc_hybrid.contracts.serialization import canonical_json, content_hash, from_primitive, to_primitive
from fmfc_hybrid.errors import ContractError, ContractVersionError
from tests.fixtures.builders import fixture, record, simple_match

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "data" / "schemas"


class RoundTripTests(unittest.TestCase):
    def test_all_contracts_round_trip(self):
        fm = MockFootballManager()
        ctx = fm.capture_match_context(fm.detect_upcoming_fixture().fm_fixture_ref)
        objects = [ctx.fixture, ctx.players[0], ctx.tactics["home"], simple_match()[0],
                   record(simple_match(), 1, 1)]
        for obj in objects:
            with self.subTest(type=type(obj).__name__):
                text = envelope.dumps(obj)
                self.assertEqual(envelope.loads(text), obj)
                self.assertEqual(from_primitive(type(obj), json.loads(json.dumps(to_primitive(obj)))), obj)

    def test_canonical_json_is_deterministic(self):
        f1, f2 = fixture(), fixture()
        self.assertEqual(canonical_json(f1), canonical_json(f2))
        self.assertEqual(content_hash(f1), content_hash(f2))
        self.assertNotEqual(content_hash(f1), content_hash(replace(f1, venue="Elsewhere")))

    def test_wrong_types_rejected(self):
        data = to_primitive(simple_match()[0])
        data["sequence"] = "one"
        with self.assertRaises(ContractError):
            from_primitive(MatchEvent, data)
        data = to_primitive(simple_match()[0])
        data["type"] = "teleport"
        with self.assertRaises(ContractError):
            from_primitive(MatchEvent, data)
        data = to_primitive(simple_match()[0])
        data["sequence"] = True  # bool must not pass as int
        with self.assertRaises(ContractError):
            from_primitive(MatchEvent, data)

    def test_missing_required_field(self):
        data = to_primitive(fixture())
        del data["home"]
        with self.assertRaises(ContractError):
            from_primitive(Fixture, data)


class VersionCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.env = envelope.wrap(fixture())

    def test_unknown_field_rejected_at_same_version(self):
        self.env["payload"]["surprise"] = 1
        with self.assertRaises(ContractError):
            envelope.unwrap(self.env)

    def test_newer_minor_accepts_additive_fields(self):
        self.env["schema_version"] = "1.7"
        self.env["payload"]["weather"] = "rain"
        self.assertEqual(envelope.unwrap(self.env), fixture())

    def test_different_major_rejected(self):
        self.env["schema_version"] = "2.0"
        with self.assertRaises(ContractVersionError):
            envelope.unwrap(self.env)

    def test_malformed_version_and_contract(self):
        for bad in ("1", "x.y", 1.0, None):
            env = dict(self.env, schema_version=bad)
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                envelope.unwrap(env)
        with self.assertRaises(ContractError):
            envelope.unwrap(dict(self.env, contract="nope"))
        with self.assertRaises(ContractError):
            envelope.unwrap(self.env, expected="match_event")
        with self.assertRaises(ContractError):
            envelope.loads("{not json")

    def test_older_minor_is_migrated(self):
        spec = envelope.CONTRACTS["tactical_plan"]
        original = spec
        try:
            envelope.CONTRACTS["tactical_plan"] = replace(spec, version="1.2")
            # 1.0 used "shape" instead of "formation"; 1.1 -> 1.2 is a no-op step.
            envelope.register_migration("tactical_plan", "1.0", "1.1",
                                        lambda p: {**{k: v for k, v in p.items() if k != "shape"},
                                                   "formation": p["shape"]})
            envelope.register_migration("tactical_plan", "1.1", "1.2", lambda p: p)
            plan = MockFootballManager().capture_match_context("mockfm-fixture-1").tactics["home"]
            payload = to_primitive(plan)
            payload["shape"] = payload.pop("formation")
            out = envelope.unwrap({"contract": "tactical_plan", "schema_version": "1.0", "payload": payload})
            self.assertIsInstance(out, TacticalPlan)
            self.assertEqual(out.formation, plan.formation)
        finally:
            envelope.CONTRACTS["tactical_plan"] = original
            envelope.unregister_migration("tactical_plan", "1.0")
            envelope.unregister_migration("tactical_plan", "1.1")

    def test_missing_migration_path(self):
        spec = envelope.CONTRACTS["player_profile"]
        try:
            envelope.CONTRACTS["player_profile"] = replace(spec, version="1.3")
            with self.assertRaises(ContractVersionError):
                envelope.unwrap({"contract": "player_profile", "schema_version": "1.1", "payload": {}})
        finally:
            envelope.CONTRACTS["player_profile"] = spec

    def test_migration_cannot_cross_major(self):
        with self.assertRaises(ValueError):
            envelope.register_migration("fixture", "1.0", "2.0", lambda p: p)


class SchemaExportTests(unittest.TestCase):
    def test_committed_schemas_are_current(self):
        for name, text in render_all().items():
            with self.subTest(schema=name):
                path = SCHEMA_DIR / name
                self.assertTrue(path.is_file(), f"{name} missing; run: python -m fmfc_hybrid schemas")
                self.assertEqual(path.read_text(encoding="utf-8"), text,
                                 f"{name} is stale; run: python -m fmfc_hybrid schemas")

    def test_schema_requires_payload_fields(self):
        schema = json.loads(render_all()["player_profile.schema.json"])
        profile = schema["$defs"]["PlayerProfile"]
        self.assertIn("fm_player_id", profile["required"])
        self.assertFalse(profile["additionalProperties"])
        self.assertIn("PlayerOrigin", schema["$defs"])


if __name__ == "__main__":
    unittest.main()
