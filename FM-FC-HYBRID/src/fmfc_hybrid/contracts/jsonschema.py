"""JSON Schema (draft 2020-12) export for the contracts.

The non-Python components (FM plugin, FIFA-side Lua scripts) validate against
these generated schemas; ``data/schemas`` holds the committed output and a test
asserts it is up to date with the dataclasses.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import types
import typing
from pathlib import Path
from typing import Any, Union, get_args, get_origin

from .envelope import CONTRACTS


def _type_schema(tp: Any, defs: dict[str, Any]) -> dict[str, Any]:
    origin = get_origin(tp)
    if origin is Union or origin is types.UnionType:
        args = get_args(tp)
        return {"anyOf": [_type_schema(a, defs) for a in args]}
    if tp is type(None):
        return {"type": "null"}
    if origin in (tuple, list):
        (item,) = get_args(tp)[:1] or (Any,)
        return {"type": "array", "items": _type_schema(item, defs)}
    if origin is dict:
        _, val = get_args(tp)
        return {"type": "object", "additionalProperties": _type_schema(val, defs)}
    if tp is str:
        return {"type": "string"}
    if tp is bool:
        return {"type": "boolean"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        defs.setdefault(tp.__name__, {"enum": [m.value for m in tp]})
        return {"$ref": f"#/$defs/{tp.__name__}"}
    if dataclasses.is_dataclass(tp):
        if tp.__name__ not in defs:
            defs[tp.__name__] = {}  # placeholder guards recursion
            hints = typing.get_type_hints(tp)
            props, required = {}, []
            for f in dataclasses.fields(tp):
                props[f.name] = _type_schema(hints[f.name], defs)
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                    required.append(f.name)
            defs[tp.__name__] = {"type": "object", "properties": props, "required": required,
                                 "additionalProperties": False}
        return {"$ref": f"#/$defs/{tp.__name__}"}
    return {}


def contract_schema(name: str) -> dict[str, Any]:
    spec = CONTRACTS[name]
    defs: dict[str, Any] = {}
    payload_ref = _type_schema(spec.model, defs)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"fmfc-hybrid/{name}/{spec.version}",
        "title": f"FM-FC Hybrid contract: {name} v{spec.version}",
        "type": "object",
        "properties": {
            "contract": {"const": name},
            "schema_version": {"type": "string", "pattern": f"^{spec.major}\\.[0-9]+$"},
            "payload": payload_ref,
        },
        "required": ["contract", "schema_version", "payload"],
        "$defs": dict(sorted(defs.items())),
    }


def render_all() -> dict[str, str]:
    return {f"{name}.schema.json": json.dumps(contract_schema(name), indent=2, sort_keys=True) + "\n"
            for name in sorted(CONTRACTS)}


def write_all(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, text in render_all().items():
        path = directory / filename
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
