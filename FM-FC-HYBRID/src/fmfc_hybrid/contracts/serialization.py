"""Generic, type-hint driven (de)serialization for the contract dataclasses.

Keeping this generic means every contract model is defined exactly once (as a
dataclass) and the JSON wire format, the JSON Schema export and validation all
derive from that single definition.

Supported field types: ``str``, ``int``, ``float``, ``bool``, ``Enum``
subclasses, nested dataclasses, ``Optional[X]`` / ``X | None``,
``tuple[X, ...]``, ``list[X]`` and ``dict[str, X]``.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import types
import typing
from functools import lru_cache
from typing import Any, TypeVar, Union, get_args, get_origin

from ..errors import ContractError

T = TypeVar("T")

_NONE_TYPE = type(None)


def to_primitive(obj: Any) -> Any:
    """Convert a contract object into JSON-compatible primitives."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_primitive(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [to_primitive(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): to_primitive(v) for k, v in obj.items()}
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    raise ContractError(f"Cannot serialize value of type {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON used for hashing and idempotency keys."""
    return json.dumps(to_primitive(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _hints(cls: type) -> dict[str, Any]:
    return typing.get_type_hints(cls)


def _is_union(tp: Any) -> bool:
    origin = get_origin(tp)
    return origin is Union or origin is types.UnionType


def from_primitive(tp: Any, data: Any, *, path: str = "$", strict: bool = True) -> Any:
    """Build an instance of ``tp`` from JSON primitives.

    ``strict`` rejects unknown dataclass fields. Non-strict mode ignores them,
    which is how payloads from a *newer minor* contract version are accepted.
    """
    if _is_union(tp):
        args = get_args(tp)
        if data is None:
            if _NONE_TYPE in args:
                return None
            raise ContractError(f"{path}: null is not allowed")
        non_none = [a for a in args if a is not _NONE_TYPE]
        if len(non_none) == 1:
            return from_primitive(non_none[0], data, path=path, strict=strict)
        # Unions of scalars, e.g. ``str | int | float | bool`` used in event details.
        for candidate in non_none:
            if candidate in (str, int, float, bool) and _scalar_matches(candidate, data):
                return data
        raise ContractError(f"{path}: value {data!r} does not match any of {non_none}")

    if data is None:
        raise ContractError(f"{path}: null is not allowed")

    origin = get_origin(tp)
    if origin in (tuple, list):
        if not isinstance(data, list):
            raise ContractError(f"{path}: expected array, got {type(data).__name__}")
        args = get_args(tp)
        item_tp = args[0] if args else Any
        items = [from_primitive(item_tp, v, path=f"{path}[{i}]", strict=strict) for i, v in enumerate(data)]
        return tuple(items) if origin is tuple else items
    if origin is dict:
        if not isinstance(data, dict):
            raise ContractError(f"{path}: expected object, got {type(data).__name__}")
        _, val_tp = get_args(tp)
        return {str(k): from_primitive(val_tp, v, path=f"{path}.{k}", strict=strict) for k, v in data.items()}
    if tp is Any:
        return data
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        try:
            return tp(data)
        except ValueError:
            allowed = ", ".join(str(m.value) for m in tp)
            raise ContractError(f"{path}: {data!r} is not a valid {tp.__name__} (allowed: {allowed})") from None
    if dataclasses.is_dataclass(tp):
        if not isinstance(data, dict):
            raise ContractError(f"{path}: expected object for {tp.__name__}, got {type(data).__name__}")
        hints = _hints(tp)
        fields = {f.name: f for f in dataclasses.fields(tp)}
        unknown = set(data) - set(fields)
        if unknown and strict:
            raise ContractError(f"{path}: unknown field(s) for {tp.__name__}: {sorted(unknown)}")
        kwargs = {}
        for name, f in fields.items():
            if name in data:
                kwargs[name] = from_primitive(hints[name], data[name], path=f"{path}.{name}", strict=strict)
            elif f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                raise ContractError(f"{path}: missing required field '{name}' for {tp.__name__}")
        try:
            return tp(**kwargs)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"{path}: cannot construct {tp.__name__}: {exc}") from exc
    if tp in (str, int, float, bool):
        if not _scalar_matches(tp, data):
            raise ContractError(f"{path}: expected {tp.__name__}, got {type(data).__name__}")
        return float(data) if tp is float else data
    raise ContractError(f"{path}: unsupported type {tp!r}")


def _scalar_matches(tp: type, value: Any) -> bool:
    if tp is bool:
        return isinstance(value, bool)
    if tp is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if tp is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, tp)
