# Evidence Ledger (top level)

The most important claims the project relies on. Detailed ledgers with every source:
[FM_RESEARCH §8](FM_RESEARCH.md), [FIFA_RESEARCH §11](FIFA_RESEARCH.md),
[REVERSE_ENGINEERING_TOOLING](REVERSE_ENGINEERING_TOOLING.md).

Classes: CONFIRMED (directly tested by us), SOURCE VERIFIED (we read the implementation), DOCUMENTED
(primary documentation says so), INFERRED, UNKNOWN, BLOCKED. Nothing is CONFIRMED in-game.

| # | Claim | Class | Source / test |
|---|---|---|---|
| 1 | FM26 match engine and database are native C++ in `game_plugin.dll`; Unity IL2CPP is the UI/flow shell | SOURCE VERIFIED (re-checked by the lead) | FMSuperScout `plugin_MemScan.cs` (comment on `GpBase`: "native C++ database — person objects live here"); FMMatchLens `v061/GameMatchTickHook.cs`, `mem_GamePluginBuildCatalog.cs` |
| 2 | FMMatchLens targets FM26 26.3 via BepInEx 6 IL2CPP, MIT | DOCUMENTED + SOURCE VERIFIED | github.com/osnsyc/FMMatchLens README, LICENSE |
| 3 | FMSuperScout reads FM26 memory and never writes | DOCUMENTED + SOURCE VERIFIED | github.com/mavarobli/FMSuperScout README; source |
| 4 | Harmony patching of FM26 C# UI/match types works | SOURCE VERIFIED | FM26Access source (FM_RESEARCH §3.1) |
| 5 | Biasing an in-progress FM match is possible (referee-decision hook) | SOURCE VERIFIED | FMODD (FM_RESEARCH §3.2) |
| 6 | No public tool replaces FM's simulation or triggers native post-processing for an external result | INFERRED from an extensive search (absence of evidence) | FM_RESEARCH §5 |
| 7 | FM26 save resources are per-file encrypted; offline result editing is not viable | SOURCE VERIFIED | fm-toolkit `fmf-format.md` |
| 8 | FM stores per-fixture player stats, ratings, tables in the save | SOURCE VERIFIED | fmsave / fm-toolkit tables |
| 9 | Whether FM natively processes an edited or steered result | UNKNOWN | Experiment X1 |
| 10 | EA AntiCheat starts with FIFA 23; FIFA 23+ editors fake its launcher | DOCUMENTED / SOURCE VERIFIED | FIFA_RESEARCH §1, §2 → **BLOCKED** for this project |
| 11 | FIFA 20–22 squads, lineups, formations, tactics are in-memory DB tables | SOURCE VERIFIED | FIFA 21 `db_meta.xml`, FIFA 22 CT `consts.lua` |
| 12 | FIFA 22 adds `buildupplay`, `chancecreation`; widths/depth 1..100 (FIFA 20/21: 0..9) | SOURCE VERIFIED | FIFA_RESEARCH §5.4 |
| 13 | CPU vs CPU via cheat-table Side Changer (FIFA 20, 22) | SOURCE VERIFIED (script), untested | FIFA_RESEARCH §4.4 |
| 14 | No live goal/card/sub event API before FIFA 23 | INFERRED (none found in source/docs) | FIFA_RESEARCH §1 |
| 15 | Per-match stats derivable from career-mode tables before/after a match | INFERRED | FIFA_RESEARCH §5.6, experiment E7 |
| 16 | REA 6.8.0 provides static PE/IL2CPP analysers usable on Windows; IL2CPP metadata v31 supported | SOURCE VERIFIED (not executed) | REVERSE_ENGINEERING_TOOLING §3 |
| 17 | Bridge never imports a fixture twice, including after a crash between FM applying and the bridge recording | CONFIRMED (mock adapters) | `tests/integration/test_orchestrator.py::test_crash_after_fm_applied_result_never_double_imports` |
| 18 | Ledger detects tampering and rejects writes after finalization at the database level | CONFIRMED | `tests/unit/test_ledger.py` |
| 19 | Lifecycle survives restart and resumes every unfinished match | CONFIRMED (mock adapters) | `test_crash_mid_match_resumes_collection`, `test_state_survives_reopen` |
| 20 | 60-seed fuzz of the full mock pipeline verifies every match | CONFIRMED (mock adapters) | `tests/regression/test_mock_fuzz.py` |
