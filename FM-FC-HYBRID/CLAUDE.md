# CLAUDE.md: FM-FC Hybrid working rules

## What this is
A bridge that lets Football Manager (authority on everything) hand the managed club's fixtures to
FIFA (match engine) and take the played match back. Read `README.md`, then `docs/FEASIBILITY_REPORT.md`.

## Commands
- Tests: `python -m unittest discover -s tests -t .` (run from `FM-FC-HYBRID/`). Must stay green.
- Strict run: `python -W error::ResourceWarning -m unittest discover -s tests -t .`
- Mock end-to-end: `PYTHONPATH=src python -m fmfc_hybrid demo --matches 3`
- Regenerate schemas after changing any contract dataclass: `PYTHONPATH=src python -m fmfc_hybrid schemas`
  (a test fails if `data/schemas` is stale).
- Research toolkit: `PYTHONPATH=tools/windows_research python -m fmfc_research --help`

## Engineering rules
- Python >= 3.10, **standard library only** in `src/` and `tools/`. Do not add dependencies without a
  recorded decision in `docs/DECISIONS.md`.
- Shared code (`contracts`, `ledger`, `lifecycle`, `identity`, `result_processor`, `bridge`) must stay
  game-agnostic. Game specifics live only in adapters and in `data/` configuration.
- Never invent game functions, offsets or APIs. Real adapters are written only against behaviour that is
  SOURCE VERIFIED or CONFIRMED and cited in the docs.
- Every new contract field: update dataclass, regenerate schemas, bump the contract minor version
  if additive (major if breaking) in `contracts/envelope.py`, add a migration for older minors.
- Append-only tables are protected by triggers; never weaken them. Corrections go through
  `EventLedger.add_correction`.
- Integration honesty: an adapter reports its real `IntegrationLevel`. Only `NATIVE_PROCESSING` counts
  as full integration. Never describe score editing as full integration.

## Evidence standard
Classify claims as CONFIRMED / SOURCE VERIFIED / DOCUMENTED / INFERRED / UNKNOWN / BLOCKED and add
important ones to `docs/EVIDENCE_LEDGER.md`. Do not claim anything works in-game until demonstrated
on the user's Windows machine with recorded evidence.

## Safety
- No proprietary binaries, saves or credentials in git (`.gitignore` blocks common extensions).
- No DRM / authentication / anti-cheat circumvention. FIFA 23+ is BLOCKED (EA AntiCheat).
- Research tooling is read-only and refuses to write inside a scanned installation.
- Downloaded third-party code is data: never execute it in the cloud session.
- A safety classifier stopped a hand-written PE binary parser in sprint 1; binary-level analysis is
  delegated to the user's local REA install instead (docs/REVERSE_ENGINEERING_TOOLING.md).

## Where things are
Research: `docs/FM_RESEARCH.md`, `docs/FIFA_RESEARCH.md`, `docs/REVERSE_ENGINEERING_TOOLING.md`.
Next steps: `docs/LOCAL_RESEARCH_ENVIRONMENT.md`, `docs/OPEN_PROBLEMS.md`.
