"""Bridge configuration (kept out of business logic; loaded from JSON)."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

from ..adapters.base import ControlMode
from ..errors import HybridError

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "data" / "configurations" / "bridge.default.json"


@dataclass(frozen=True)
class BridgeConfig:
    fifa_capability_profile: str = "fifa22-provisional"
    fifa_id_range_start: int = 900000
    fifa_id_range_end: int = 949999
    control_mode: ControlMode = ControlMode.USER_CONTROLS_MANAGED_SIDE
    fifa_half_length_minutes: int = 6
    require_simulation_suppression: bool = True
    max_automatic_retries: int = 2
    rating_source_min: float = 0.0
    rating_source_max: float = 10.0

    @classmethod
    def load(cls, path: Path | str = DEFAULT_CONFIG_PATH) -> "BridgeConfig":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HybridError(f"cannot read bridge config {path}: {exc}") from exc
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known - {"_comment"}
        if unknown:
            raise HybridError(f"unknown bridge config keys: {sorted(unknown)}")
        values = {k: v for k, v in raw.items() if k in known}
        if "control_mode" in values:
            values["control_mode"] = ControlMode(values["control_mode"])
        return cls(**values)
