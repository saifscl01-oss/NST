# Capability Matrix

Distinguishes the capabilities the brief separates. "Shown by" names the strongest public precedent;
nothing here has been run by us. Classes as in [EVIDENCE_LEDGER](EVIDENCE_LEDGER.md).

## Football Manager

| Capability | FM26 | FM24 | Shown by | Class |
|---|---|---|---|---|
| Read save data | Yes (container decoded; per-fixture stats, tables) | Yes (`fmf.` + zstd) | fmsave, fm-toolkit, fm26-scout (MIT) | SOURCE VERIFIED |
| Write save data | No (per-file encrypted resources) | No public tool | fm-toolkit research | SOURCE VERIFIED (negative) |
| Read running game state | Yes (BepInEx plugin, `game_plugin.dll`) | Yes (external memory) | FMSuperScout, FMODD | SOURCE VERIFIED |
| Edit player/club data live | Yes | Yes | FMODD, FMRTE, IGE | SOURCE VERIFIED / DOCUMENTED |
| Detect managed fixture | Yes (team schedule, next-match date) | Yes | FMSuperScout, FMODD | SOURCE VERIFIED (reads) |
| Read live match events | Yes (tick-level) | Partial | FMMatchLens | SOURCE VERIFIED |
| Hold / intercept the sim | Unknown (Harmony on `FM.Match.*` is a lead) | Unknown | FM26Access proves Harmony on FM26 UI | UNKNOWN |
| Edit a fixture result | Partly shown (result structures mapped) | Partly | FMODD layouts | SOURCE VERIFIED (layouts) |
| Steer FM's own simulation | Precedent: referee-decision hook | Same | FMODD "black whistle" | SOURCE VERIFIED |
| Inject external events | Not demonstrated | Not demonstrated | — | UNKNOWN |
| Native post-match processing of an external match | Not demonstrated | Not demonstrated | — | UNKNOWN (experiment X1) |
| In-process managed loader | Yes (BepInEx 6 IL2CPP) | No | BepInExPack FM26 | SOURCE VERIFIED |

## FIFA

See [FEASIBILITY_REPORT §3](FEASIBILITY_REPORT.md) for the FIFA 20 vs FIFA 22 table and
[FIFA_RESEARCH §6](FIFA_RESEARCH.md) for the full matrix with sources.

## Bridge (this repository)

| Capability | State | Evidence |
|---|---|---|
| Versioned contracts + JSON Schemas | Implemented | `tests/unit/test_contracts.py` |
| Fixture and match-event validation (match replay) | Implemented | `tests/unit/test_validation.py` |
| Immutable, hash-chained event ledger + corrections | Implemented | `tests/unit/test_ledger.py` |
| Lifecycle with recovery, concurrency, duplicate guards | Implemented | `tests/unit/test_lifecycle.py`, `tests/integration/test_orchestrator.py` |
| Player identity registry | Implemented | `tests/unit/test_identity.py` |
| Attribute conversion | Foundations, provisional weights | `tests/unit/test_mappers.py` |
| Tactical translation with fidelity | Framework + seed rules, per-version profiles | `tests/unit/test_mappers.py` |
| Real FM adapter | Not started | — |
| Real FIFA adapter | Not started | — |
