"""Tactical Translation Engine (foundation).

Translates an FM :class:`TacticalPlan` into version-neutral FIFA "knobs"
(team settings + per-player instructions) and classifies every FM element by
fidelity:

* ``direct``      - an equivalent mechanism exists.
* ``strong``      - the intent is preserved with a close mechanism.
* ``partial``     - only part of the intent survives.
* ``unsupported`` - nothing in the target expresses it.

Rules (data/mappings/fm_tactics_rules.json) say what an FM element *means* in
knob terms; a capability profile (data/configurations/fifa_capability_profiles.json)
says which knobs the chosen FIFA version really has. A rule whose knobs are
missing from the profile is downgraded automatically, so the same rules stay
honest across FIFA versions. Application order is mentality (base values) ->
team instructions (adjustments) -> roles (per-player).
"""

from __future__ import annotations

import enum
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..contracts.models import TacticalPlan
from ..errors import MappingError

_DATA = Path(__file__).resolve().parents[3] / "data"
DEFAULT_RULES_PATH = _DATA / "mappings" / "fm_tactics_rules.json"
DEFAULT_PROFILES_PATH = _DATA / "configurations" / "fifa_capability_profiles.json"


class Fidelity(str, enum.Enum):
    DIRECT = "direct"
    STRONG = "strong"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"

    @property
    def rank(self) -> int:
        return [Fidelity.DIRECT, Fidelity.STRONG, Fidelity.PARTIAL, Fidelity.UNSUPPORTED].index(self)


@dataclass(frozen=True)
class TranslatedElement:
    kind: str                 # mentality | team_instruction | role | formation
    source: str               # FM element id (and slot for roles)
    fidelity: Fidelity
    applied: dict[str, Any]   # knob -> value actually applied
    dropped: tuple[str, ...]  # knobs the rule wanted but the profile lacks
    rationale: str


@dataclass(frozen=True)
class TacticalTranslation:
    profile: str
    formation: str
    formation_fidelity: Fidelity
    team_settings: dict[str, Any]
    player_instructions: dict[int, dict[str, Any]]  # lineup slot -> instruction -> value
    elements: tuple[TranslatedElement, ...]
    warnings: tuple[str, ...] = ()

    def summary(self) -> dict[str, int]:
        counts = Counter(e.fidelity.value for e in self.elements)
        return {f.value: counts.get(f.value, 0) for f in Fidelity}

    def overall_fidelity(self) -> Fidelity:
        """The worst fidelity among elements that carry tactical intent."""
        if not self.elements:
            return Fidelity.UNSUPPORTED
        return max((e.fidelity for e in self.elements), key=lambda f: f.rank)


@dataclass
class TacticalTranslator:
    rules: dict[str, Any]
    profile_name: str
    profile: dict[str, Any]
    position_map: dict[str, str] = field(default_factory=dict)  # FM position -> FIFA position

    @classmethod
    def load(cls, profile_name: str, *, position_map: dict[str, str],
             rules_path: Path = DEFAULT_RULES_PATH, profiles_path: Path = DEFAULT_PROFILES_PATH
             ) -> "TacticalTranslator":
        try:
            rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
            profiles = json.loads(Path(profiles_path).read_text(encoding="utf-8"))["profiles"]
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise MappingError(f"cannot load tactical configuration: {exc}") from exc
        if profile_name not in profiles:
            raise MappingError(f"unknown FIFA capability profile '{profile_name}'")
        return cls(rules, profile_name, profiles[profile_name], position_map)

    # -- knob handling -------------------------------------------------
    def _knob_spec(self, knob: str) -> Optional[dict[str, Any]]:
        scope, _, name = knob.partition(".")
        table = {"team": self.profile.get("team", {}), "pi": self.profile.get("player_instructions", {})}.get(scope)
        return None if table is None else table.get(name)

    def _apply(self, target: dict[str, Any], knob: str, op: dict[str, Any], spec: dict[str, Any],
               warnings: list[str], source: str) -> Any:
        name = knob.partition(".")[2]
        if "set" in op:
            value = op["set"]
            if name in target and target[name] != value and spec["type"] == "enum":
                warnings.append(f"{source}: overrides {knob}={target[name]!r} with {value!r}")
        elif "add" in op:
            if spec["type"] != "int":
                raise MappingError(f"rule {source}: 'add' on non-numeric knob {knob}")
            value = target.get(name, spec.get("default", spec["min"])) + op["add"]
        else:
            raise MappingError(f"rule {source}: operation must be 'set' or 'add'")
        if spec["type"] == "int":
            value = max(spec["min"], min(spec["max"], int(value)))
        elif spec["type"] == "enum" and value not in spec["values"]:
            raise MappingError(f"rule {source}: {value!r} is not a valid value for {knob}")
        target[name] = value
        return value

    def _apply_rule(self, kind: str, source: str, rule: Optional[dict[str, Any]], target: dict[str, Any],
                    warnings: list[str]) -> TranslatedElement:
        if rule is None:
            return TranslatedElement(kind, source, Fidelity.UNSUPPORTED, {}, (), "no translation rule defined")
        fidelity = Fidelity(rule["fidelity"])
        applied, dropped = {}, []
        for knob, op in rule.get("targets", {}).items():
            spec = self._knob_spec(knob)
            if spec is None:
                dropped.append(knob)
                continue
            applied[knob] = self._apply(target, knob, op, spec, warnings, source)
        if dropped:
            fidelity = Fidelity.UNSUPPORTED if not applied else max(fidelity, Fidelity.PARTIAL,
                                                                    key=lambda f: f.rank)
        return TranslatedElement(kind, source, fidelity, applied, tuple(dropped), rule.get("rationale", ""))

    # -- formation -----------------------------------------------------
    def nearest_formation(self, fm_positions: list[str]) -> tuple[str, Fidelity, int]:
        wanted = Counter(self.position_map.get(p, p) for p in fm_positions)
        best: tuple[int, str] | None = None
        for name, slots in sorted(self.profile.get("formations", {}).items()):
            have = Counter(slots)
            distance = sum((wanted - have).values())
            if best is None or distance < best[0]:
                best = (distance, name)
        if best is None:
            raise MappingError("capability profile defines no formations")
        distance, name = best
        fidelity = Fidelity.DIRECT if distance == 0 else Fidelity.STRONG if distance == 1 else Fidelity.PARTIAL
        return name, fidelity, distance

    # -- main entry ----------------------------------------------------
    def translate(self, plan: TacticalPlan) -> TacticalTranslation:
        warnings: list[str] = []
        elements: list[TranslatedElement] = []
        team: dict[str, Any] = {name: spec["default"] for name, spec in self.profile.get("team", {}).items()
                                if "default" in spec}

        roles_sorted = sorted(plan.roles, key=lambda r: r.slot)
        formation, f_fid, distance = self.nearest_formation([r.position for r in roles_sorted])
        elements.append(TranslatedElement(
            "formation", plan.formation, f_fid, {"formation": formation}, (),
            f"nearest FIFA formation by position slots ({distance} slot(s) differ)"))

        elements.append(self._apply_rule("mentality", plan.mentality,
                                         self.rules.get("mentality", {}).get(plan.mentality), team, warnings))
        ti_rules = self.rules.get("team_instructions", {})
        for group in (plan.in_possession, plan.in_transition, plan.out_of_possession):
            for code in group:
                elements.append(self._apply_rule("team_instruction", code, ti_rules.get(code), team, warnings))

        role_rules = self.rules.get("roles", {})
        per_player: dict[int, dict[str, Any]] = {}
        for ra in roles_sorted:
            target: dict[str, Any] = {}
            el = self._apply_rule("role", f"slot{ra.slot}:{ra.role}:{ra.duty.value}",
                                  role_rules.get(ra.role), target, warnings)
            elements.append(el)
            for ii in ra.individual_instructions:
                elements.append(TranslatedElement("individual_instruction", f"slot{ra.slot}:{ii}",
                                                  Fidelity.UNSUPPORTED, {}, (),
                                                  "individual instruction rules not yet defined"))
            if target:
                per_player[ra.slot] = target
        team["formation"] = formation
        return TacticalTranslation(self.profile_name, formation, f_fid, team, per_player, tuple(elements),
                                   tuple(warnings))
