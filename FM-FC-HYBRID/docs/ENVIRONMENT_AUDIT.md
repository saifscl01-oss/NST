# Environment Audit (cloud session, 2026-10-31)

## Repository
- Repo `saifscl01-oss/NST`, branch `claude/dazzling-wozniak-r7nqs7`, clean at start.
- Pre-existing content: `halos-projection/` (music royalty and streaming projections). Unrelated to this
  project and left untouched.
- This project lives entirely in `FM-FC-HYBRID/`, created as the user requested.

## Cloud container capabilities

| Item | Finding | Class |
|---|---|---|
| OS | Linux container, ephemeral | CONFIRMED |
| Python | 3.13 (code targets 3.10+) | CONFIRMED |
| Node | 22 | CONFIRMED |
| Also present | Go, Rust, gcc, clang, lld-link, Java, objdump/readelf/strings | CONFIRMED |
| SQLite | 3.53 (via Python `sqlite3`) | CONFIRMED |
| Network | Through an egress proxy. `raw.githubusercontent.com`, PyPI, npm and general web reachable. `github.com` HTML and `api.github.com` return 403 to curl (WebFetch reaches github.com pages) | CONFIRMED |
| GitHub write access | Only `saifscl01-oss/NST` | CONFIRMED |
| Game files | None. No FM or FIFA binaries, saves or installers are present or reachable | CONFIRMED |
| Windows | None. No Wine, no Windows APIs | CONFIRMED |

## Reverse Engineer Anything (REA)
- **Not installed in the cloud container.** No `~/.claude/skills/reverse-engineer-anything`, no `rea` on
  PATH. The user's install is on their local machine.
- Identified as npm package `rea-agents` 6.8.0 (MIT, © 2026 morluto, `github.com/morluto/rea`, release tag
  `rea-agents-6.8.0` at commit `160d821…`). Full audit: [REVERSE_ENGINEERING_TOOLING](REVERSE_ENGINEERING_TOOLING.md).
- Running REA in the cloud was **refused by the session's permission policy** (executing third-party
  code). The audit was therefore source-only and nothing about REA is CONFIRMED by execution here.
- Its built-in static analysers (PE imports, certificates, resources, exports, entropy, desktop-install
  runtime detection, IL2CPP metadata v24/27/29/31/39) cover our identification needs. Decompilation on
  Windows needs Ghidra (experimental) or IDA. Runtime tracing on Windows is effectively unavailable.

## Other limits encountered
- A safety classifier stopped generation of a hand-written PE parser for the research toolkit. That
  module was removed and not recreated; binary metadata comes from REA and the Windows version-info
  facilities (`Get-Item … .VersionInfo`) instead. The toolkit does file-level work only.
- Third-party repositories were downloaded into the session scratchpad as read-only data and never
  executed. The FIFA 21 Live Editor repository contains closed executables; they were not run.

## What the cloud session can and cannot do

| Can | Cannot |
|---|---|
| Read public source of community tools; research documentation | Run, inspect or debug FM/FIFA binaries |
| Build and test the bridge core, contracts, ledger, lifecycle, registry, mappers | Demonstrate anything in-game |
| Build and test the read-only research toolkit on synthetic trees | Execute REA, Ghidra, Cheat Engine, BepInEx |
| Write runbooks and experiments for Windows | Access the user's machine or files |

## Windows experiments required
See [LOCAL_RESEARCH_ENVIRONMENT](LOCAL_RESEARCH_ENVIRONMENT.md): Phase 1 inventory, FM experiments
X0–X2 (X1b and X1d are decisive), FIFA experiments E0–E15.
