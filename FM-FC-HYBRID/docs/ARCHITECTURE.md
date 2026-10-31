# Architecture

## Shape

```
 ┌───────────── Windows PC (offline) ─────────────────────────────────────────────────┐
 │                                                                                     │
 │  Football Manager 26                         FIFA 22                                │
 │  ┌──────────────────────────┐                ┌──────────────────────────┐           │
 │  │ FM plugin (planned)      │                │ FIFA-side scripts        │           │
 │  │ BepInEx 6 IL2CPP, C#     │                │ (planned: Live Editor    │           │
 │  │ - detect fixture         │                │  Lua and/or cheat-table  │           │
 │  │ - hold / steer sim       │                │  hooks)                  │           │
 │  │ - read squads, tactics   │                │ - write squads, tactics  │           │
 │  │ - apply / verify result  │                │ - control mode, collect  │           │
 │  └────────────┬─────────────┘                └─────────────┬────────────┘           │
 │       local IPC (JSON contracts)                   local IPC / files                │
 │  ┌────────────┴─────────────────────────────────────────────┴────────────┐          │
 │  │ Bridge service: src/fmfc_hybrid (Python, stdlib only)                  │          │
 │  │  FmAdapter ── orchestrator ── FifaAdapter                              │          │
 │  │      │  identity registry · player mapper · tactical translator        │          │
 │  │      │  lifecycle state machine · event ledger · result processor     │          │
 │  │      └─ SQLite (one file per career, WAL, append-only audit)          │          │
 │  └────────────────────────────────────────────────────────────────────────┘          │
 └─────────────────────────────────────────────────────────────────────────────────────┘
```

The bridge is the only component with business logic. The in-game components are thin: they expose
capabilities and execute instructions. That keeps game-version churn (offsets, field layouts) out of
the core.

## Components (brief section 8 → code)

| Brief component | Module | State |
|---|---|---|
| A. FM plugin | `adapters/base.py: FmAdapter` protocol; C# plugin not started | Protocol + mock |
| B. Central bridge | `bridge/orchestrator.py`, `bridge/config.py`, `cli.py` | Implemented, tested on mocks |
| C. Player mapping engine | `identity/registry.py`, `player_mapper/attributes.py`, `data/mappings/fm_to_fifa_attributes.json` | Foundations; weights provisional |
| D. Tactical translation | `tactics/translator.py`, `data/mappings/fm_tactics_rules.json`, `data/configurations/fifa_capability_profiles.json` | Framework + seed rules; waits on FIFA E2 |
| E. FIFA adapter | `adapters/base.py: FifaAdapter` protocol | Protocol + mock |
| F. Match event ledger | `ledger/ledger.py` | Implemented, tested |
| G. Result processor | `result_processor/processor.py` | Implemented, tested |
| H. Shared contracts | `contracts/` + `data/schemas/*.schema.json` | Implemented, versioned, tested |

## Data contracts

Dataclasses in `contracts/models.py` are the single definition. `contracts/serialization.py` derives
JSON (de)serialization from type hints; `contracts/jsonschema.py` derives JSON Schemas for the C# and
Lua sides; `contracts/envelope.py` wraps payloads as
`{"contract", "schema_version", "payload"}`.

Compatibility: different major → rejected. Older minor → upgraded by registered migrations.
Newer minor → accepted, unknown additive fields ignored. Same version → strict.

Contracts: `player_profile`, `fixture`, `tactical_plan`, `match_event`, `external_match_record`,
`fm_import_package`.

**Identifiers.** Adapters speak game identifiers only. In fixtures produced by an FM adapter, players are
`fm:<id>`; the bridge registers every captured player and rebinds the fixture to Hybrid Player IDs
(`adapters/ids.py: bind_fixture`) before anything else sees it. Fixture ids are derived from
`(career_id, fm_fixture_ref)` so re-detection is stable.

## Adapter capability model

Adapters declare `FmCapabilities` / `FifaCapabilities` honestly. Each FM import returns an
`IntegrationLevel`:

| Level | Meaning |
|---|---|
| `SCORE_ONLY` | Scoreline edited |
| `RESULT_AND_STATS` | Score plus per-player appearances, goals, cards written |
| `EVENTS_INJECTED` | FM's match representation populated with external events |
| `NATIVE_PROCESSING` | FM ran native post-match processing on the external match (target) |

Only `NATIVE_PROCESSING` is reported as full integration (`MatchOutcome.full_integration`). A Route A
(steered simulation) adapter reports `NATIVE_PROCESSING` and must add verification checks comparing FM's
produced events with the ledger, because steering can diverge.

## Persistence and safety properties

- One SQLite file per career. Schema versioned with `PRAGMA user_version`.
- Append-only tables (`audit_log`, `match_transitions`, `state_snapshots`, `ledger_events`,
  `ledger_finalizations`, `ledger_corrections`, `player_snapshots`, `import_attempts_log`) have
  triggers that abort UPDATE/DELETE; a trigger also rejects ledger inserts after finalization.
- A partial unique index allows one live (non-abandoned) match per career fixture.
- The `imports` table makes each fixture importable once; see [MATCH_LIFECYCLE](MATCH_LIFECYCLE.md).
- Every step saves a preservation snapshot (FM pre-match state, FIFA request, tactical translation with
  fidelity, external record, import package) with its SHA-256.

## Technology choices

Python 3.10+, standard library only (`sqlite3`, `dataclasses`, `unittest`): runs on a bare Windows
Python, easy to audit, and the bridge is I/O-bound orchestration. The in-game sides will use whatever
the host requires: C# for the FM26 BepInEx plugin, Lua for FIFA-side scripts. They meet the bridge only
through the JSON contracts. IPC transport (named pipe, localhost socket or file drop) is deliberately
undecided until the in-game constraints are known ([OPEN_PROBLEMS](OPEN_PROBLEMS.md) P-07).
