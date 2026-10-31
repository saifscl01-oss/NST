# Research Log

## 2026-10-31: sprint 1 (cloud session)

**Reconnaissance**
- Repo `NST` contained only an unrelated project; created `FM-FC-HYBRID/` as asked.
- Cloud container: Linux, Python 3.13, Node 22, clang/lld; web via proxy; no game files; no Windows.
- REA is not installed in the cloud. Identified it as npm `rea-agents` 6.8.0 (MIT, morluto/rea).
  Executing it here was refused by the permission policy; ran a read-only source audit instead.

**Parallel research** (three agents; outputs in `docs/`)
- FM workstream → `FM_RESEARCH.md`. Key finding: FM26 keeps the engine native in `game_plugin.dll`
  under a Unity IL2CPP shell; BepInEx 6 plugins read it. Reading is solved; replacing the sim is not.
  Lead re-verified the central claim in downloaded FMSuperScout/FMMatchLens source and READMEs.
- FIFA workstream → `FIFA_RESEARCH.md`. Key finding: FIFA 22 is the last version without EA AntiCheat;
  squad and tactics tables are editable; no live event API before FIFA 23; career-mode deltas are the
  best stat source.
- REA workstream → `REVERSE_ENGINEERING_TOOLING.md`.

**Engineering**
- Built the bridge core (contracts, storage, ledger, lifecycle, identity, mappers, result processor,
  orchestrator, mocks, CLI) and a read-only research toolkit.
- A safety classifier stopped a hand-written PE parser; it was removed and the toolkit refocused on
  file-level evidence with REA for binary metadata (DECISIONS D-010).
- Tests: 95, all passing. The validator caught a real ordering bug in the mock FIFA generator (events in
  the same minute emitted out of order); fixed and covered by a 60-seed fuzz regression test.
- Reconciled the tactical capability profile with source-verified FIFA field ranges: split into
  FIFA 22 and FIFA 20/21 profiles with bridge-scale → game-scale conversion.

**Outcome**
Gate 0 complete. Gate 1 has a proposed route (steered simulation on FM26) awaiting experiment X1.
