# FM-FC Hybrid

> Football Manager is the brain. FIFA is the body. This project is the nervous system.

FM-FC Hybrid replaces Football Manager's simulation of **your managed club's fixtures** with a match
actually played in EA Sports FIFA, then returns the result, events and player performances to FM so FM
processes every downstream consequence itself. Windows, offline, single-player.

## Status (2026-10-31, end of sprint 1)

| Gate | Status | Evidence |
|---|---|---|
| 0. Repository and environment established | **Done** | 95 passing tests (`python -m unittest discover -s tests -t .`), [ENVIRONMENT_AUDIT](docs/ENVIRONMENT_AUDIT.md) |
| 1. FM match lifecycle understood well enough to propose an integration route | **Route proposed, not demonstrated** | [FM_RESEARCH](docs/FM_RESEARCH.md), [FEASIBILITY_REPORT](docs/FEASIBILITY_REPORT.md). Needs the decisive Windows experiment X1 |
| 2. FIFA match preparation and execution | Not started (needs Windows) | Plan in [FIFA_RESEARCH §9](docs/FIFA_RESEARCH.md) |
| 3. Match event collection | Not started | — |
| 4. External match integrated into FM | Not started | — |
| 5. End-to-end on a disposable career | Simulated with mocks only | `tests/integration/test_orchestrator.py`, **not** a game demonstration |
| 6–7. Fidelity, polished UI | Not started | — |

**Nothing works in-game yet.** Everything that runs today runs against mock adapters.

## Recommended pairing (provisional, evidence-based)

**FM26 (pinned Steam build) + FIFA 22**. Reasoning in [FEASIBILITY_REPORT](docs/FEASIBILITY_REPORT.md).

## Repository layout

```
FM-FC-HYBRID/
├── CLAUDE.md                  working rules for engineering sessions
├── docs/                      research, architecture, decisions, evidence
├── src/fmfc_hybrid/           bridge core (Python 3.10+, standard library only)
│   ├── contracts/             versioned data contracts, JSON Schema export, validation/match replay
│   ├── storage/               SQLite (WAL, append-only triggers, migrations)
│   ├── ledger/                hash-chained, immutable match event ledger + audited corrections
│   ├── lifecycle/             formal match state machine with failure/recovery states
│   ├── identity/              persistent player identity registry (Hybrid Player IDs)
│   ├── player_mapper/         FM 1-20 -> FIFA 1-99 conversion foundations (config-driven)
│   ├── tactics/               tactical translation engine with fidelity classification
│   ├── result_processor/      external match -> idempotent FM import package; once-only import guard
│   ├── adapters/              adapter protocols + mock FM / mock FIFA (no real game adapters yet)
│   ├── bridge/                orchestrator (crash-safe) and configuration
│   └── cli.py                 python -m fmfc_hybrid {demo,status,history,ledger,schemas}
├── tools/windows_research/    read-only local research toolkit (python -m fmfc_research)
├── data/schemas/              generated JSON Schemas for every contract
├── data/mappings/             attribute and tactic mapping rules (provisional)
├── data/configurations/       bridge config, FIFA capability profiles
└── tests/                     unit, integration, regression (unittest; no third-party deps)
```

## Quick start

```bash
cd FM-FC-HYBRID
python -m unittest discover -s tests -t .                  # 95 tests
PYTHONPATH=src python -m fmfc_hybrid demo --matches 3       # mock season, end to end
PYTHONPATH=src python -m fmfc_hybrid demo --fifa-fault interrupt_once   # see recovery states
PYTHONPATH=tools/windows_research python -m fmfc_research --help        # research toolkit
```

On Windows use `set PYTHONPATH=src` (cmd) or `$env:PYTHONPATH="src"` (PowerShell).

## Key documents

- [FEASIBILITY_REPORT](docs/FEASIBILITY_REPORT.md): what is possible, what is unknown, the pairing.
- [LOCAL_RESEARCH_ENVIRONMENT](docs/LOCAL_RESEARCH_ENVIRONMENT.md): exactly what to do on Windows next.
- [ARCHITECTURE](docs/ARCHITECTURE.md), [MATCH_LIFECYCLE](docs/MATCH_LIFECYCLE.md), [DECISIONS](docs/DECISIONS.md).
- [EVIDENCE_LEDGER](docs/EVIDENCE_LEDGER.md) and the detailed ledgers inside each research doc.

## Ground rules

No proprietary game files, saves or credentials in this repository. No DRM, authentication or
anti-cheat circumvention. Reconnaissance is read-only, on copies, against disposable saves. See
[PROJECT_BRIEF](docs/PROJECT_BRIEF.md) for the user's stated authorization and its scope.
