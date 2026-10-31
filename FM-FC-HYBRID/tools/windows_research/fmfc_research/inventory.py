"""SHA-256 file inventories of an installation directory (read-only)."""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional

from .safety import open_read_only

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class FileEntry:
    path: str          # POSIX-style path relative to the root
    size: int
    modified_utc: str
    sha256: Optional[str]  # None when hashing was skipped (size limit)
    extension: str

    def to_dict(self) -> dict:
        return asdict(self)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open_read_only(path) as fh:
        while True:
            block = fh.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def iter_files(root: Path, *, follow_symlinks: bool = False) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink() and not follow_symlinks:
                continue
            yield p


def build_inventory(root: Path, *, max_hash_bytes: Optional[int] = None, workers: int = 4,
                    include: Optional[Callable[[Path], bool]] = None,
                    progress: Optional[Callable[[int, Path], None]] = None) -> list[FileEntry]:
    """Inventory every regular file under ``root``. Hashes are computed in parallel threads."""
    root = Path(root)
    files = [p for p in iter_files(root) if include is None or include(p)]

    def entry(p: Path) -> FileEntry:
        st = p.stat()
        digest = None if (max_hash_bytes is not None and st.st_size > max_hash_bytes) else sha256_file(p)
        return FileEntry(
            path=p.relative_to(root).as_posix(), size=st.st_size,
            modified_utc=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            sha256=digest, extension=p.suffix.lower())

    results: list[FileEntry] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i, e in enumerate(pool.map(entry, files), 1):
            results.append(e)
            if progress:
                progress(i, root / e.path)
    return sorted(results, key=lambda e: e.path.lower())


def summarize(entries: list[FileEntry]) -> dict:
    by_ext: dict[str, dict[str, int]] = {}
    for e in entries:
        bucket = by_ext.setdefault(e.extension or "<none>", {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += e.size
    return {
        "files": len(entries),
        "bytes": sum(e.size for e in entries),
        "unhashed": sum(1 for e in entries if e.sha256 is None),
        "by_extension": dict(sorted(by_ext.items(), key=lambda kv: -kv[1]["bytes"])),
    }
