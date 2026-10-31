"""Versioned contract envelopes.

Every payload crossing a process boundary (FM plugin <-> bridge <-> FIFA
adapter) is wrapped as::

    {"contract": "<name>", "schema_version": "<major>.<minor>", "payload": {...}}

Compatibility policy (see docs/ARCHITECTURE.md, "Data contracts"):

* Different major version            -> rejected (ContractVersionError).
* Same major, older minor            -> upgraded through registered migrations.
* Same major, newer minor            -> accepted; unknown (additive) fields ignored.
* Same version                       -> strict: unknown fields rejected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ..errors import ContractError, ContractVersionError
from . import models
from .serialization import from_primitive, to_primitive


@dataclass(frozen=True)
class ContractSpec:
    name: str
    model: type
    version: str  # current "major.minor"

    @property
    def major(self) -> int:
        return int(self.version.split(".")[0])

    @property
    def minor(self) -> int:
        return int(self.version.split(".")[1])


CONTRACTS: dict[str, ContractSpec] = {
    spec.name: spec
    for spec in (
        ContractSpec("player_profile", models.PlayerProfile, "1.0"),
        ContractSpec("fixture", models.Fixture, "1.0"),
        ContractSpec("tactical_plan", models.TacticalPlan, "1.0"),
        ContractSpec("match_event", models.MatchEvent, "1.0"),
        ContractSpec("external_match_record", models.ExternalMatchRecord, "1.0"),
        ContractSpec("fm_import_package", models.FmImportPackage, "1.0"),
    )
}

Migration = Callable[[dict[str, Any]], dict[str, Any]]

# (contract name, from "major.minor") -> (to "major.minor", function)
_MIGRATIONS: dict[tuple[str, str], tuple[str, Migration]] = {}


def register_migration(contract: str, from_version: str, to_version: str, fn: Migration) -> None:
    """Register a payload upgrade step. Steps must stay within one major version."""
    if from_version.split(".")[0] != to_version.split(".")[0]:
        raise ValueError("Migrations may not cross major versions")
    _MIGRATIONS[(contract, from_version)] = (to_version, fn)


def unregister_migration(contract: str, from_version: str) -> None:
    _MIGRATIONS.pop((contract, from_version), None)


def _parse_version(text: Any) -> tuple[int, int]:
    if not isinstance(text, str) or text.count(".") != 1:
        raise ContractError(f"Malformed schema_version: {text!r}")
    major, minor = text.split(".")
    if not (major.isdigit() and minor.isdigit()):
        raise ContractError(f"Malformed schema_version: {text!r}")
    return int(major), int(minor)


def contract_name_for(obj: Any) -> str:
    for spec in CONTRACTS.values():
        if type(obj) is spec.model:
            return spec.name
    raise ContractError(f"No contract registered for {type(obj).__name__}")


def wrap(obj: Any) -> dict[str, Any]:
    spec = CONTRACTS[contract_name_for(obj)]
    return {"contract": spec.name, "schema_version": spec.version, "payload": to_primitive(obj)}


def dumps(obj: Any, *, indent: int | None = None) -> str:
    return json.dumps(wrap(obj), indent=indent, sort_keys=True, ensure_ascii=False)


def unwrap(envelope: dict[str, Any], *, expected: str | None = None) -> Any:
    if not isinstance(envelope, dict):
        raise ContractError("Envelope must be a JSON object")
    for key in ("contract", "schema_version", "payload"):
        if key not in envelope:
            raise ContractError(f"Envelope missing '{key}'")
    name = envelope["contract"]
    if name not in CONTRACTS:
        raise ContractError(f"Unknown contract '{name}'")
    if expected is not None and name != expected:
        raise ContractError(f"Expected contract '{expected}', got '{name}'")
    spec = CONTRACTS[name]
    major, minor = _parse_version(envelope["schema_version"])
    if major != spec.major:
        raise ContractVersionError(
            f"Contract '{name}' major version {major} is incompatible with supported {spec.version}",
            details={"received": envelope["schema_version"], "supported": spec.version},
        )
    payload = envelope["payload"]
    strict = True
    if minor < spec.minor:
        payload = _migrate(name, f"{major}.{minor}", spec.version, payload)
    elif minor > spec.minor:
        strict = False  # newer producer; additive fields are ignored
    return from_primitive(spec.model, payload, path=f"{name}", strict=strict)


def loads(text: str, *, expected: str | None = None) -> Any:
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError(f"Invalid JSON: {exc}") from exc
    return unwrap(envelope, expected=expected)


def _migrate(name: str, from_version: str, to_version: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = from_version
    data = dict(payload)
    seen = set()
    while current != to_version:
        if current in seen:
            raise ContractError(f"Migration cycle for '{name}' at {current}")
        seen.add(current)
        step = _MIGRATIONS.get((name, current))
        if step is None:
            raise ContractVersionError(
                f"No migration path for '{name}' from {current} to {to_version}",
                details={"from": current, "to": to_version},
            )
        current, fn = step
        data = fn(data)
    return data
