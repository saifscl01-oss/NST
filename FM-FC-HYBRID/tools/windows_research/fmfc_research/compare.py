"""Compare two inventories (e.g. FM26 patch A vs B, FIFA 20 vs FIFA 22)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class InventoryDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[dict] = field(default_factory=list)
    unchanged: int = 0
    unverifiable: list[str] = field(default_factory=list)  # present in both, but a hash is missing

    def to_dict(self) -> dict:
        return {"added": self.added, "removed": self.removed, "changed": self.changed,
                "unchanged": self.unchanged, "unverifiable": self.unverifiable,
                "summary": {"added": len(self.added), "removed": len(self.removed),
                            "changed": len(self.changed), "unchanged": self.unchanged}}


def compare_inventories(left: Iterable[dict], right: Iterable[dict], *, case_insensitive: bool = True
                        ) -> InventoryDiff:
    def key(p: str) -> str:
        return p.lower() if case_insensitive else p

    a = {key(e["path"]): e for e in left}
    b = {key(e["path"]): e for e in right}
    diff = InventoryDiff()
    for k in sorted(set(b) - set(a)):
        diff.added.append(b[k]["path"])
    for k in sorted(set(a) - set(b)):
        diff.removed.append(a[k]["path"])
    for k in sorted(set(a) & set(b)):
        ea, eb = a[k], b[k]
        if ea.get("sha256") is None or eb.get("sha256") is None:
            if ea["size"] != eb["size"]:
                diff.changed.append({"path": eb["path"], "size": [ea["size"], eb["size"]], "sha256": None})
            else:
                diff.unverifiable.append(eb["path"])
        elif ea["sha256"] != eb["sha256"]:
            diff.changed.append({"path": eb["path"], "size": [ea["size"], eb["size"]],
                                 "sha256": [ea["sha256"], eb["sha256"]]})
        else:
            diff.unchanged += 1
    return diff
