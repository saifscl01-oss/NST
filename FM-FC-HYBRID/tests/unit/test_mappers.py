import copy
import unittest
from dataclasses import replace

import tests  # noqa: F401
from fmfc_hybrid.adapters.mock_fm import MockFootballManager
from fmfc_hybrid.contracts.models import Appearance, Duty, RoleAssignment, TacticalPlan
from fmfc_hybrid.errors import MappingError
from fmfc_hybrid.player_mapper import AttributeMapper
from fmfc_hybrid.tactics import Fidelity, TacticalTranslator

PROFILE = "fifa22-provisional"


class AttributeMapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapper = AttributeMapper.from_file()

    def test_curve_monotone_and_bounded(self):
        values = [self.mapper.curve(v / 2) for v in range(0, 45)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(self.mapper.curve(-5), self.mapper.curve(1))
        self.assertEqual(self.mapper.curve(99), self.mapper.curve(20))
        self.assertTrue(1 <= min(values) and max(values) <= 99)

    def test_conversion_reports_defaults(self):
        out, defaulted = self.mapper.convert_attributes({"pace": 20, "acceleration": 1})
        self.assertEqual(out["sprintspeed"], self.mapper.curve(20))
        self.assertEqual(out["acceleration"], self.mapper.curve(1))
        self.assertIn("finishing", defaulted)
        with self.assertRaises(MappingError):
            self.mapper.convert_attributes({"pace": 21})

    def test_invalid_configs_rejected(self):
        base = self.mapper.config
        bad_weights = copy.deepcopy(base)
        bad_weights["attributes"]["finishing"] = {"finishing": 0.5}
        bad_curve = copy.deepcopy(base)
        bad_curve["curve"] = [[1, 50], [10, 40]]
        missing = {k: v for k, v in base.items() if k != "positions"}
        for cfg in (bad_weights, bad_curve, missing):
            with self.assertRaises(MappingError):
                AttributeMapper(cfg)

    def test_player_spec(self):
        fm = MockFootballManager(seed=5)
        outfield = next(p for p in fm.players.values() if "ST" in p.positions)
        spec, report = self.mapper.to_fifa_spec("HP-1", 900001, outfield, must_create=True)
        self.assertEqual(spec.positions[0], "ST")
        self.assertTrue(1 <= spec.weak_foot <= 5 and 1 <= spec.skill_moves <= 5)
        self.assertEqual(set(spec.attributes), set(self.mapper.config["attributes"]))
        self.assertIn("reflexes", report.defaulted_inputs)  # outfielders have no GK attributes in FM
        gk = next(p for p in fm.players.values() if "GK" in p.positions)
        gspec, _ = self.mapper.to_fifa_spec("HP-2", 900002, gk, must_create=False)
        self.assertEqual((gspec.positions[0], gspec.skill_moves), ("GK", 1))
        either = replace(outfield, appearance=Appearance(preferred_foot="either"))
        self.assertEqual(self.mapper.to_fifa_spec("HP-3", 1, either, must_create=True)[0].weak_foot, 5)
        with self.assertRaises(MappingError):
            self.mapper.to_fifa_spec("HP-4", 1, replace(outfield, positions={"ST": 10}), must_create=True)


class TacticalTranslatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.positions = AttributeMapper.from_file().config["positions"]
        cls.tr = TacticalTranslator.load(PROFILE, position_map=cls.positions)
        cls.plan = MockFootballManager().capture_match_context("mockfm-fixture-1").tactics["home"]

    def test_translates_mock_plan(self):
        t = self.tr.translate(self.plan)
        self.assertEqual(t.formation, "4-2-3-1(2)")  # DM pair + AMR/AMC/AML + ST; wingers sit in RM/LM
        self.assertEqual(t.formation_fidelity, Fidelity.STRONG)
        self.assertEqual(t.team_settings["defensive_style"], "constant_pressure")
        self.assertEqual(t.team_settings_bridge_scale["depth"], 8)  # positive (6) + higher line (+2)
        self.assertEqual(t.team_settings["depth"], 78)  # bridge 8/10 -> FIFA 22 range 1..100
        self.assertEqual(t.team_settings["chance_creation"], "possession")
        self.assertEqual(t.player_instructions[6]["attacking_runs"], "get_forward")  # segundo volante
        by_source = {e.source: e for e in t.elements}
        self.assertEqual(by_source["slot5:half_back:defend"].fidelity, Fidelity.PARTIAL)
        self.assertEqual(by_source["slot3:ball_playing_defender:defend"].fidelity, Fidelity.UNSUPPORTED)
        self.assertEqual(by_source["slot0:goalkeeper:defend"].rationale, "no translation rule defined")
        self.assertEqual(sum(t.summary().values()), len(t.elements))
        self.assertEqual(t.overall_fidelity(), Fidelity.UNSUPPORTED)

    def test_missing_knob_downgrades_fidelity(self):
        profile = copy.deepcopy(self.tr.profile)
        del profile["player_instructions"]["support_runs"]
        del profile["team"]["defensive_style"]
        tr = TacticalTranslator(self.tr.rules, "reduced", profile, self.positions)
        t = tr.translate(self.plan)
        by_source = {e.source: e for e in t.elements}
        sv = by_source["slot6:segundo_volante:attack"]
        self.assertEqual(sv.fidelity, Fidelity.PARTIAL)  # was strong
        self.assertEqual(sv.dropped, ("pi.support_runs",))
        self.assertEqual(by_source["counter_press"].fidelity, Fidelity.UNSUPPORTED)

    def test_numeric_knobs_are_clamped(self):
        plan = replace(self.plan, mentality="very_attacking",
                       out_of_possession=("much_higher_defensive_line", "much_higher_defensive_line"))
        self.assertEqual(self.tr.translate(plan).team_settings_bridge_scale["depth"], 10)
        self.assertEqual(self.tr.translate(plan).team_settings["depth"], 100)

    def test_unknown_elements_are_unsupported_not_errors(self):
        plan = replace(self.plan, mentality="chaotic", in_possession=("teleport",), in_transition=(),
                       out_of_possession=(),
                       roles=(RoleAssignment(0, "GK", "sweeper_keeper", Duty.SUPPORT, ("distribute_quickly",)),))
        t = self.tr.translate(plan)
        self.assertTrue(all(e.fidelity is Fidelity.UNSUPPORTED for e in t.elements if e.kind != "formation"))
        self.assertEqual(t.formation_fidelity, Fidelity.PARTIAL)  # a one-player plan is not a formation

    def test_fifa20_profile_loses_build_up_and_chance_creation(self):
        tr20 = TacticalTranslator.load("fifa20-21-provisional", position_map=self.positions)
        t = tr20.translate(self.plan)
        self.assertNotIn("chance_creation", t.team_settings)
        self.assertEqual(t.team_settings["depth"], 7)  # bridge 8/10 -> FIFA 20/21 range 0..9
        by_source = {e.source: e for e in t.elements}
        self.assertEqual(by_source["shorter_passing"].fidelity, Fidelity.UNSUPPORTED)
        self.assertEqual(by_source["shorter_passing"].dropped, ("team.chance_creation",))

    def test_unknown_profile(self):
        with self.assertRaises(MappingError):
            TacticalTranslator.load("fifa99", position_map=self.positions)


if __name__ == "__main__":
    unittest.main()
