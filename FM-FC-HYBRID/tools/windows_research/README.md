# fmfc_research: local research toolkit (read-only)

Standard-library Python 3.10+. Collects file-level evidence about game installations. It never writes
inside a scanned installation (enforced), opens source files read-only, and records every output file's
SHA-256 in a manifest.

Binary-level analysis (imports, exports, resources, certificates, IL2CPP metadata) is delegated to
your local **REA** install; `rea-plan` prints the audited REA commands for an installation's key
binaries. See `docs/REVERSE_ENGINEERING_TOOLING.md`.

```powershell
$env:PYTHONPATH="C:\re\FM-FC-HYBRID\tools\windows_research"
python -m fmfc_research discover "D:\Games" --steam "C:\Program Files (x86)\Steam"
python -m fmfc_research inventory "<install>" --out C:\re\out\<label> --label <label> [--max-hash-mb 2048]
python -m fmfc_research compare <a>\inventory.json <b>\inventory.json --out C:\re\out\a-vs-b.json
python -m fmfc_research rea-plan "<install>" --evidence-dir C:\re\out\<label>-rea
python -m fmfc_research verify C:\re\out\<label>
powershell -File Collect-VersionInfo.ps1 -Root "<install>" -OutFile C:\re\out\<label>-versioninfo.json
```

| Command | Output |
|---|---|
| `discover` | Installations found under the roots (and Steam libraries), classified by file layout (INFERRED) |
| `inventory` | Evidence bundle: `inventory.json` (path, size, mtime, SHA-256), `classification.json`, `summary.json`, `key_binaries.json`, `report.md`, `manifest.json` |
| `compare` | Added / removed / changed files between two inventories |
| `rea-plan` | PowerShell lines running REA's read-only analysers on the key binaries |
| `verify` | Checks a bundle against its manifest |
| `Collect-VersionInfo.ps1` | Windows version-resource fields + SHA-256 for key binaries (built-in cmdlets only) |

Detection rules live in `fmfc_research/signatures.json` (file presence only). Tests:
`tests/unit/test_research_toolkit.py` (synthetic directory trees, no game files).
