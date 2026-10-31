# Local Windows Research Environment: runbook

This is the ordered work for your Windows machine. Everything up to Phase 2 is **read-only**. Writes
happen only in later phases, on disposable saves, inside a research copy of the game where possible.

## Phase 0: set up (once)

1. **Folders** (outside every game directory):
   `C:\re\` for tools and evidence, `C:\re\out\` for outputs, `C:\re\saves\` for dated save backups.
2. **Python 3.10+** from python.org (standard library only; nothing to pip install).
3. **Clone this repository** to `C:\re\FM-FC-HYBRID` (the bridge folder of the `NST` repo).
4. **Verify the toolkit and core run:**
   ```powershell
   cd C:\re\FM-FC-HYBRID
   python -m unittest discover -s tests -t .
   $env:PYTHONPATH="tools\windows_research"; python -m fmfc_research --help
   ```
5. **Verify your REA install** (exact commands in [REVERSE_ENGINEERING_TOOLING §1.3](REVERSE_ENGINEERING_TOOLING.md)):
   `rea --version` (expect `6.8.0` or later), check the `metadata.version` line of
   `%USERPROFILE%\.claude\skills\reverse-engineer-anything\SKILL.md` (npm 6.8.0 ships skill version 49),
   and run the read-only readiness check. For decompilation later, REA needs Ghidra 12.1.x + JDK 21
   (experimental on Windows) or IDA.
6. **Back up saves**: copy `Documents\Sports Interactive\Football Manager 26\games\` and
   `Documents\FIFA 22\settings\` into `C:\re\saves\<date>\`. Never point any tool at the originals.
7. **Pin builds**: set FM26 and FIFA 22 to not auto-update (Steam: launch offline / update only when
   launched; EA client: offline mode after activation). Record versions in Phase 1.

## Phase 1: inventory and identification (read-only)

For each install (FM24, FM26, FIFA 20, FIFA 22 first, others later):

```powershell
$env:PYTHONPATH="C:\re\FM-FC-HYBRID\tools\windows_research"
python -m fmfc_research discover "D:\Games" --steam "C:\Program Files (x86)\Steam"
python -m fmfc_research inventory "<FM26 install>"  --out C:\re\out\fm26-inventory  --label FM26
python -m fmfc_research inventory "<FIFA22 install>" --out C:\re\out\fifa22-inventory --label FIFA22 --max-hash-mb 2048
python -m fmfc_research verify C:\re\out\fm26-inventory
powershell -File C:\re\FM-FC-HYBRID\tools\windows_research\Collect-VersionInfo.ps1 -Root "<FM26 install>" -OutFile C:\re\out\fm26-versioninfo.json
python -m fmfc_research rea-plan "<FM26 install>" --evidence-dir C:\re\out\fm26-rea > C:\re\out\fm26-rea-plan.ps1
```

Review the generated REA plan, then run it. Most important outputs:
- `inspect-desktop-application` on FM26: confirms Unity IL2CPP and the presence of `game_plugin.dll`.
- `inspect-il2cpp-metadata` on FM26 `global-metadata.dat` (+ `GameAssembly.dll`): confirms metadata
  version (research says v31, which REA supports) and lets us search type names such as
  `FM.Match.MatchSetup` and `EventFmxRequestQuickMatch`.
- `inspect-pe-imports` / `inspect-pe-resources` on `game_plugin.dll`, `fm.exe` (FM24) and `FIFA22.exe`.

Repeat `inventory` for FM24 vs FM26 and FIFA 20 vs FIFA 22, then compare:
`python -m fmfc_research compare C:\re\out\fifa20-inventory\inventory.json C:\re\out\fifa22-inventory\inventory.json --out C:\re\out\fifa20-vs-22.json`

**Send back:** the evidence bundle folders except `inventory.json` if you prefer not to share file
lists (the manifests, summaries, `classification.json`, `key_binaries.json`, version-info JSON and REA
outputs are what matter). They contain names, sizes and hashes, never game content.

## Phase 2: FM26 experiments

Install BepInEx 6 IL2CPP into a **research copy** of the FM26 folder if the copy launches; otherwise
decide whether to install it into the main install (it only adds files and can be removed). This is
your call, see [OPEN_PROBLEMS](OPEN_PROBLEMS.md) P-05.

| ID | Goal | Steps | Writes? |
|---|---|---|---|
| **X0** | Pin and fingerprint | Record `game_plugin.dll` SHA-256 (Phase 1). Check it against the builds FMMatchLens/FMSuperScout support (their build catalogs) | No |
| **X1a** | Observe a managed match live | Install FMMatchLens (MIT) on a throwaway career; play one managed match; confirm live score, scorers, cards and period bytes are visible | No (read-only plugin) |
| **X1b** | **Baseline consequence map** | On a throwaway career: save immediately before a managed match (copy A), play it normally, save after (copy B). Parse both copies with a read-only save parser (fmsave / fm-toolkit, MIT) and diff: fixtures, league table, player match/season stats, ratings, morale, condition, injuries, suspensions, finances, news | No |
| **X1c** | Route D bound | Using a live editor on a throwaway career, change a just-finished managed result before continuing; save; diff against X1b's categories. Classify each consequence as value-driven (updated) or event-driven (not updated) | Yes, throwaway only |
| **X1d** | **Route A steering** (the decisive one) | Ghidra on the pinned `game_plugin.dll` at the match-update RVA FMMatchLens resolves; find where goal events and the score are written. Prototype forcing one extra goal for the managed club; let FM finish; save; diff as in X1b | Yes, throwaway only |
| **X2** | Route B detect/hold | Read-only Harmony postfix logging on `FMDialogHandler.HandleTriggerDialogEvent`, `MatchSetup`, and whatever raises `EventFmxRequestQuickMatch` when the managed fixture starts | No (logging only) |

X1b is the highest-value experiment you can run without any hooking: it tells us exactly which
consequences an integration must reproduce.

## Phase 3: FIFA 22 experiments

Use the experiment table in [FIFA_RESEARCH §9](FIFA_RESEARCH.md) (E0–E15). Priority order:

1. **E0** offline launch with no bypass (stop and report if an online check is mandatory).
2. **E1** schema dump, **E2** tactic enum and player-instruction semantics (unblocks the tactical mapper).
3. **E3** regen creation, **E4/E5** lineup control for both teams, **E6** CPU vs CPU.
4. **E7** per-match stats by career-mode deltas, **E8** full-time detection.
5. E9–E15 as time allows. E14 repeats the key ones on FIFA 20 for comparison.

Confirm first whether you can legally obtain the FIFA 22 Live Editor build (it was distributed via
Patreon). If not, the GPL-3 cheat table becomes the primary FIFA-side mechanism.

## Reporting results

For each experiment record: build hashes, date, exact steps, what you saw, screenshots where useful,
and output files. Drop them in `C:\re\out\<experiment-id>\` and share them in the next session.
I will update the evidence ledger, promote claims to CONFIRMED where warranted, and write the real
adapters against what was observed.
