"""Read-only guarantees for the research toolkit.

* Source files are only ever opened with mode ``"rb"`` through :func:`open_read_only`.
* Output directories must lie outside every scanned root, so a report can
  never be written into a game installation.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Iterable


class SafetyError(Exception):
    pass


def open_read_only(path: Path) -> BinaryIO:
    return open(path, "rb")


def ensure_output_outside(roots: Iterable[Path], output: Path) -> Path:
    out = output.resolve()
    for root in roots:
        r = Path(root).resolve()
        if out == r or r in out.parents:
            raise SafetyError(f"output directory {out} is inside scanned root {r}; choose another location")
    return out
