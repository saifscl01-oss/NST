"""FM -> FIFA player conversion foundations.

All numbers live in ``data/mappings/fm_to_fifa_attributes.json``; this module
only implements the mechanics (weighted composites + a monotone piecewise-linear
curve from FM's 1-20 scale to FIFA's 1-99 scale) and produces a report of every
defaulted or unmapped input so conversions are auditable.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..adapters.base import FifaPlayerSpec
from ..contracts.models import PlayerProfile
from ..errors import MappingError

DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[3] / "data" / "mappings" / "fm_to_fifa_attributes.json"


@dataclass(frozen=True)
class ConversionReport:
    hybrid_player_id: str
    defaulted_inputs: tuple[str, ...]
    unmapped_traits: tuple[str, ...]
    unmapped_positions: tuple[str, ...]


@dataclass
class AttributeMapper:
    config: dict[str, Any]
    _curve_x: list[float] = field(init=False, repr=False)
    _curve_y: list[float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._validate()
        self._curve_x = [float(p[0]) for p in self.config["curve"]]
        self._curve_y = [float(p[1]) for p in self.config["curve"]]

    @classmethod
    def from_file(cls, path: Path | str = DEFAULT_MAPPING_PATH) -> "AttributeMapper":
        try:
            return cls(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise MappingError(f"cannot load attribute mapping {path}: {exc}") from exc

    @property
    def version(self) -> str:
        return str(self.config.get("mapping_version", "unknown"))

    def _validate(self) -> None:
        cfg = self.config
        for key in ("curve", "attributes", "positions"):
            if key not in cfg:
                raise MappingError(f"mapping config missing '{key}'")
        curve = cfg["curve"]
        xs = [p[0] for p in curve]
        ys = [p[1] for p in curve]
        if len(curve) < 2 or xs != sorted(xs) or len(set(xs)) != len(xs):
            raise MappingError("curve x values must be strictly increasing")
        if ys != sorted(ys):
            raise MappingError("curve must be monotone non-decreasing")
        lo, hi = cfg.get("fifa_scale", [1, 99])
        if ys[0] < lo or ys[-1] > hi:
            raise MappingError("curve outputs exceed the FIFA scale")
        for target, weights in cfg["attributes"].items():
            total = sum(weights.values())
            if abs(total - 1.0) > 1e-6:
                raise MappingError(f"weights for '{target}' sum to {total}, expected 1.0")
            if any(w < 0 for w in weights.values()):
                raise MappingError(f"negative weight for '{target}'")

    # -- primitives ----------------------------------------------------
    def curve(self, fm_value: float) -> int:
        lo_fm, hi_fm = self.config.get("fm_scale", [1, 20])
        v = min(max(float(fm_value), lo_fm), hi_fm)
        xs, ys = self._curve_x, self._curve_y
        if v <= xs[0]:
            return round(ys[0])
        if v >= xs[-1]:
            return round(ys[-1])
        i = bisect_right(xs, v) - 1
        t = (v - xs[i]) / (xs[i + 1] - xs[i])
        return round(ys[i] + t * (ys[i + 1] - ys[i]))

    def convert_attributes(self, fm_attrs: dict[str, int]) -> tuple[dict[str, int], list[str]]:
        default = self.config.get("missing_default_fm_value", 1)
        defaulted: set[str] = set()
        out: dict[str, int] = {}
        for target, weights in self.config["attributes"].items():
            composite = 0.0
            for source, w in weights.items():
                if source in fm_attrs:
                    value = fm_attrs[source]
                    if not 1 <= value <= 20:
                        raise MappingError(f"FM attribute {source}={value} outside 1..20")
                else:
                    value = default
                    defaulted.add(source)
                composite += w * value
            out[target] = self.curve(composite)
        return out, sorted(defaulted)

    @staticmethod
    def _bucket(value: float, thresholds: list[int]) -> int:
        return 1 + sum(1 for t in thresholds if value >= t)

    # -- full player ---------------------------------------------------
    def to_fifa_spec(self, hybrid_id: str, fifa_player_id: int, profile: PlayerProfile, *,
                     must_create: bool) -> tuple[FifaPlayerSpec, ConversionReport]:
        attrs = profile.attributes.all_visible()
        fifa_attrs, defaulted = self.convert_attributes(attrs)

        pos_map = self.config["positions"]
        ordered = sorted(profile.positions.items(), key=lambda kv: (-kv[1], kv[0]))
        positions: list[str] = []
        unmapped_pos: list[str] = []
        for fm_pos, rating in ordered:
            if rating < 15:  # only "accomplished" or better FM positions become FIFA positions (INFERRED)
                continue
            fifa_pos = pos_map.get(fm_pos)
            if fifa_pos is None:
                unmapped_pos.append(fm_pos)
            elif fifa_pos not in positions:
                positions.append(fifa_pos)
        if not positions:
            raise MappingError(f"player {hybrid_id} has no mappable position")

        app = profile.appearance
        weak_rating = _weak_foot_rating(app.preferred_foot, app.left_foot, app.right_foot)
        weak_foot = self._bucket(weak_rating, self.config.get("weak_foot_thresholds", [5, 9, 13, 17]))
        sm_cfg = self.config.get("skill_moves", {"inputs": ["dribbling"], "thresholds": [8, 12, 15, 17]})
        sm_inputs = [attrs.get(k, self.config.get("missing_default_fm_value", 1)) for k in sm_cfg["inputs"]]
        skill_moves = self._bucket(sum(sm_inputs) / len(sm_inputs), sm_cfg["thresholds"])
        if positions[0] == "GK":
            skill_moves = 1

        trait_map = {k: v for k, v in self.config.get("traits", {}).items() if not k.startswith("_")}
        traits, unmapped_traits = [], []
        for t in profile.traits:
            (traits if t in trait_map else unmapped_traits).append(trait_map.get(t, t))
        spec = FifaPlayerSpec(
            hybrid_player_id=hybrid_id, fifa_player_id=fifa_player_id, display_name=profile.display_name,
            must_create=must_create, attributes=fifa_attrs, positions=tuple(positions),
            preferred_foot=app.preferred_foot if app.preferred_foot in ("left", "right") else "right",
            weak_foot=weak_foot, skill_moves=skill_moves, height_cm=app.height_cm, weight_kg=app.weight_kg,
            traits=tuple(traits),
        )
        report = ConversionReport(hybrid_id, tuple(defaulted), tuple(unmapped_traits), tuple(unmapped_pos))
        return spec, report

    def fifa_position(self, fm_position: str) -> str:
        try:
            return self.config["positions"][fm_position]
        except KeyError:
            raise MappingError(f"no FIFA position for FM position {fm_position}") from None


def _weak_foot_rating(preferred: str, left: Optional[int], right: Optional[int]) -> float:
    """FM rates both feet 1-20; FIFA's weak foot is the weaker one on a 1-5 scale."""
    if preferred == "either":
        return 20.0
    weaker = right if preferred == "left" else left
    return float(weaker) if weaker is not None else 8.0  # FM's typical weak foot when unknown (INFERRED)
