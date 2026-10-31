"""Structured reports and evidence bundles.

An evidence bundle is a directory containing JSON/Markdown reports plus a
``manifest.json`` that records the tool version, host, command line, timing and
the SHA-256 of every file in the bundle, so results can be attached to the
research log and verified later.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .safety import ensure_output_outside


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EvidenceBundle:
    def __init__(self, output_dir: Path, scanned_roots: Iterable[Path], *, label: str) -> None:
        self.roots = [Path(r) for r in scanned_roots]
        self.dir = ensure_output_outside(self.roots, Path(output_dir))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.label = label
        self.started = utc_now()
        self.files: list[str] = []

    def write_json(self, name: str, data: Any) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        self.files.append(name)
        return path

    def write_text(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        self.files.append(name)
        return path

    def finalize(self) -> Path:
        manifest = {
            "tool": "fmfc_research",
            "tool_version": __version__,
            "label": self.label,
            "read_only": True,
            "scanned_roots": [str(r) for r in self.roots],
            "command_line": sys.argv,
            "host": {"platform": platform.platform(), "python": sys.version.split()[0],
                     "machine": platform.machine()},
            "started_utc": self.started,
            "finished_utc": utc_now(),
            "files": {name: _sha256(self.dir / name) for name in sorted(set(self.files))},
        }
        path = self.dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


def verify_bundle(bundle_dir: Path) -> list[str]:
    """Return a list of problems (empty if every file matches the manifest)."""
    manifest = json.loads((Path(bundle_dir) / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for name, digest in manifest["files"].items():
        p = Path(bundle_dir) / name
        if not p.is_file():
            problems.append(f"missing: {name}")
        elif _sha256(p) != digest:
            problems.append(f"modified: {name}")
    return problems


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_markdown(title: str, root: str, summary: dict, installs: list[dict]) -> str:
    lines = [f"# {title}", "", f"- Root: `{root}`", f"- Files: {summary['files']}",
             f"- Total bytes: {summary['bytes']:,}", f"- Unhashed (size limit): {summary['unhashed']}", ""]
    if installs:
        lines += ["## Detected installations (INFERRED from file layout)", "",
                  "| Root | Games | Layouts | Key files |", "|---|---|---|---|"]
        for i in installs:
            lines.append(f"| `{i['root']}` | {', '.join(i['games'])} | {', '.join(i['layouts']) or '-'} | "
                         f"{', '.join(i['key_files'])} |")
        lines.append("")
    lines += ["## Bytes by extension (top 15)", "", "| Extension | Files | Bytes |", "|---|---|---|"]
    for ext, b in list(summary["by_extension"].items())[:15]:
        lines.append(f"| `{ext}` | {b['files']} | {b['bytes']:,} |")
    return "\n".join(lines) + "\n"
