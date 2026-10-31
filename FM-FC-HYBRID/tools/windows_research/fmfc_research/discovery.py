"""Find game installations and classify them by file layout (presence checks only).

Nothing here reads file contents except Steam's plain-text library index. All
classifications are INFERRED from layout; REA's ``inspect-desktop-application``
and version info are the confirming evidence.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

SIGNATURES_PATH = Path(__file__).with_name("signatures.json")


def load_signatures(path: Path = SIGNATURES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Installation:
    root: str
    games: list[str] = field(default_factory=list)
    layouts: list[str] = field(default_factory=list)
    key_files: list[str] = field(default_factory=list)
    evidence: str = "INFERRED (file presence)"

    def to_dict(self) -> dict:
        return asdict(self)


def _exists_ci(root: Path, rel: str) -> Optional[Path]:
    """Case-insensitive existence check (Windows paths are case-insensitive; tests run on Linux)."""
    cur = root
    for part in Path(rel).parts:
        try:
            match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
        except (NotADirectoryError, PermissionError, FileNotFoundError):
            return None
        if match is None:
            return None
        cur = match
    return cur


def _glob_any(root: Path, patterns: Iterable[str]) -> list[str]:
    hits = []
    for pat in patterns:
        hits.extend(p.relative_to(root).as_posix() for p in root.glob(pat))
    return sorted(set(hits))


def classify(root: Path, signatures: Optional[dict] = None) -> Installation:
    sig = signatures or load_signatures()
    inst = Installation(root=str(root))
    for g in sig["games"]:
        if not any(_exists_ci(root, f) for f in g.get("require_any", [])):
            continue
        if not all(_exists_ci(root, f) for f in g.get("require_all_extra", [])):
            continue
        if any(_exists_ci(root, f) for f in g.get("exclude", [])):
            continue
        inst.games.append(g["id"])
    for lay in sig["layouts"]:
        if not all(_exists_ci(root, f) for f in lay.get("require_all", [])):
            continue
        if lay.get("glob_any") and not _glob_any(root, lay["glob_any"]):
            continue
        inst.layouts.append(lay["id"])
    for name in sig.get("key_binaries", []):
        hit = _exists_ci(root, name)
        if hit is not None:
            inst.key_files.append(hit.relative_to(root).as_posix())
    inst.key_files.extend(_glob_any(root, sig.get("key_data_globs", [])))
    return inst


def discover(roots: Iterable[Path], *, max_depth: int = 4, signatures: Optional[dict] = None) -> list[Installation]:
    """Walk ``roots`` (depth-limited) and return directories that match a game signature."""
    sig = signatures or load_signatures()
    markers = {n.lower() for g in sig["games"] for n in g.get("require_any", [])}
    found: dict[str, Installation] = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        base_depth = len(root.resolve().parts)
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).resolve().parts) - base_depth
            if depth >= max_depth:
                dirnames[:] = []
            if any(f.lower() in markers for f in filenames):
                inst = classify(Path(dirpath), sig)
                if inst.games:
                    found[str(Path(dirpath).resolve())] = inst
    return [found[k] for k in sorted(found)]


_VDF_PATH = re.compile(r'"path"\s+"([^"]+)"')


def steam_library_roots(steam_dir: Path) -> list[Path]:
    """Parse Steam's libraryfolders.vdf (plain text, read-only) into steamapps/common dirs."""
    vdf = Path(steam_dir) / "steamapps" / "libraryfolders.vdf"
    if not vdf.is_file():
        return []
    roots = []
    for raw in _VDF_PATH.findall(vdf.read_text(encoding="utf-8", errors="replace")):
        common = Path(raw.replace("\\\\", "\\")) / "steamapps" / "common"
        roots.append(common)
    return roots
