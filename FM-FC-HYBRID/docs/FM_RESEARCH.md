# FM-FC Hybrid — Football Manager Investigation (FM24 / FM26 priority)

**Author:** research engineer, FM workstream · **Date:** 2026-10-31
**Scope:** Whether FM's managed-club match lifecycle can be (1) detected, (2) intercepted, (3) executed externally in FIFA, (4) represented in FM's internal structures, (5) supplied back, and (6) processed natively by FM for all downstream consequences.
**Platform target:** Windows, offline, single-player, launcher-independent game files. No DRM/auth/anti-cheat bypass. No modification of original game files or valuable saves.

> **Evidence classification used throughout:** CONFIRMED (verified in a running game — we have NONE of these ourselves; only third parties claim them), SOURCE VERIFIED (we read the actual source code / binary signature), DOCUMENTED (a credible primary/community source states it), INFERRED (reasoned from verified facts), UNKNOWN, BLOCKED (could not access). We did not run FM; nothing here is claimed to work in-game by us.

---

## 1. Summary

- **FM26 and FM24 are fundamentally different engines.** FM24 (`fm.exe`) is a single, ~500 MB native x64 C++ monolith. FM26 split into a Unity 6 / IL2CPP shell (`fm.exe` bootstrapper + `GameAssembly.dll`, C# compiled to native) **plus a separate native C++ database/simulation DLL, `game_plugin.dll`**. In FM26 the *match engine and database still live in native C++ (`game_plugin.dll`)*; Unity only does presentation and the UI layer (`FM.UI`, `SI.*` IL2CPP assemblies). This is the single most important finding: the move to Unity did **not** move the match simulation into C#. (SOURCE VERIFIED via three independent open-source projects; DOCUMENTED by press/Wikipedia.)
- **FM26 is far more penetrable than FM24 in practice**, because BepInEx 6 (IL2CPP) gives you a supported managed-code loader *inside the process*, from which you can both P/Invoke `ReadProcessMemory`/detour native `game_plugin.dll` functions **and** Harmony-patch the Unity/C# UI layer. Multiple working open-source BepInEx plugins exist for FM26 (FMSuperScout, FMMatchLens, FM26Access). FM24 has no managed loader; it requires classic external memory editing or native DLL injection/detours (FMODD, Cheat Engine tables).
- **Reading is solved; native match *replacement* and native *post-match processing injection* are not demonstrated by anyone.** The community can read the live database, read the live match-engine event stream tick-by-tick (FMMatchLens), read/parse saves (fmsave, fm-toolkit, fm26-scout), and edit player/club data live. The only demonstrated *write to match outcomes* is a referee-decision hook (FMODD "black whistle") that biases an in-progress FM simulation — i.e. it steers FM's own engine, it does not substitute an external result.
- **All DRM is Denuvo Anti-tamper + Steam** on FM19–FM26 (FM22 appears to be Steam-only, no Denuvo listed). Denuvo protects `fm.exe`. Crucially, FM26's actual simulation code is in `game_plugin.dll`, and community tools hook that DLL directly by SHA-256 build fingerprint — Denuvo on the Unity bootstrapper has not stopped runtime memory tooling. We must still never defeat Denuvo itself.
- **Recommended integration target: FM26 (specifically a pinned Steam build such as 26.3.x).** Reasoning in §7.
- **Honest verdict on the hard goal:** Full "FIFA replaces the simulation, FM processes all consequences natively" is **not confirmed possible by anyone** and is the research frontier. The realistic first milestone is **steered simulation** (let FM26's `game_plugin.dll` run the match but constrain its outcome/events toward the FIFA ledger via native hooks), because that guarantees native post-match processing. A clean "inject an external match object and trigger native post-processing" path is UNKNOWN and is the key thing to test.

---

## 2. Per-version technology table (FM15–FM26, focus FM24/FM26)

| Version | App / match-engine tech | 64-bit | DRM (Steam store) | Distribution | Notes | Class |
|---|---|---|---|---|---|---|
| FM15–FM18 | Native C++ monolith (`fm.exe`); 32-bit+64-bit era | Mixed (FM17 listed 64-bit **or** 32-bit) | Steam DRM; Denuvo not listed on FM17 | Steam | Oldest mature memory editors/CE tables live here | DOCUMENTED |
| FM19 | Native C++ `fm.exe` | 64-bit | **Denuvo Anti-tamper** (first FM with Denuvo, per store) | Steam | FM19 store page lists Denuvo | SOURCE VERIFIED (Steam store) |
| FM20 | Native C++ `fm.exe` | 64-bit only (32-bit dropped) | Denuvo Anti-Tamper | Steam | First 64-bit-only Windows FM | SOURCE VERIFIED (store) + DOCUMENTED |
| FM21 | Native C++ `fm.exe` | 64-bit | Denuvo Anti-tamper | Steam/Epic | | SOURCE VERIFIED (store) |
| FM22 | Native C++ `fm.exe` | 64-bit | **No 3rd-party DRM listed** (Steam only) | Steam/Epic/GamePass | Notable: easiest DRM of the modern era | SOURCE VERIFIED (store) |
| FM23 | Native C++ `fm.exe` | 64-bit | Denuvo Anti-tamper | Steam/Epic/GamePass | | SOURCE VERIFIED (store) |
| **FM24** | **Native C++ monolith `fm.exe` (~500 MB image).** Match engine, database, simulation all in this one PE. | 64-bit | **Denuvo Anti-tamper** | Steam / Epic / GamePass (XGP) | DirectX 11. Distinct EXE SHA-256 per build & platform (FMODD pins 24.4.2 Steam/Epic/XGP). Save = `fmf.`+zstd. | SOURCE VERIFIED |
| **FM26** | **Unity 6 / IL2CPP shell** (`fm.exe` bootstrapper + `GameAssembly.dll` = C# compiled to native; `fm_Data/il2cpp_data/` with `global-metadata.dat` v31, `il2cpp.usym`). **Match engine + database are native C++ in a separate `game_plugin.dll`.** UI = IL2CPP C# (`FM.UI`, `SI.Core`, `SI.Bindable`, `SI.Services`, `SI.UI`, `Assembly-CSharp`, `FM.Match.*`). | 64-bit | **Denuvo Anti-tamper** | Steam / Epic / GamePass | DirectX 11. Denuvo on `fm.exe`; tools hook `game_plugin.dll` by SHA-256. Unity ~6000-series (exact string UNKNOWN). | SOURCE VERIFIED |
| FM27 | Same split architecture as FM26 (Unity IL2CPP + native `game_plugin.dll`). New 5-argument match-update native ABI; 720-tick sim lead vs FM26's 360. | 64-bit | Expect Denuvo | Steam / GamePass | Released ~10 Nov 2026 (beta 29 Oct). FMMatchLens 0.7 & FMODD already pin an FM27 `game_plugin.dll` build. | DOCUMENTED / SOURCE VERIFIED (offsets) |

Key technology facts (SOURCE VERIFIED unless noted):
- FM26 installation root contains `fm.exe`, `GameAssembly.dll` (~190 MB native from IL2CPP), `fm_Data/il2cpp_data/global-metadata.dat` (magic `0xFAB11BAF`, metadata version 31) and `il2cpp.usym` (magic `sym-`, v2). IL2CPP confirms **C# source compiled to native via IL2CPP, not Mono** — so Mono-style runtime reflection is out; you need Il2CppInterop. (fm-toolkit RE docs.)
- FM26 match engine + persistent DB objects are in **`game_plugin.dll`** (native C++), loaded *after* the BepInEx chainloader. FMSuperScout, FMMatchLens and FMODD all read/hook this DLL, not `GameAssembly.dll`, for simulation data. (SOURCE VERIFIED across all three.)
- FM26 C# UI symbol names recovered from `global-metadata.dat` include `FM.Match.MatchSetup`, `MatchPlaybackController`, `FM.UI.FMDialogHandler`, `EventFmxRequestQuickMatch`, `FMPlayerRating`, `FMMatchMomentumChart`. The existence of `EventFmxRequestQuickMatch` as a C# event is a strong lead for intercepting "instant result" at the UI boundary. (SOURCE VERIFIED: symbol strings; INFERRED: its role.)

---

## 3. Existing tooling inventory (mechanism · licence · source)

### 3.1 BepInEx / Unity-IL2CPP plugins (FM26) — in-process managed code

| Tool | Mechanism | What it touches | Licence / source | Class |
|---|---|---|---|---|
| **BepInEx 6 (IL2CPP, win-x64)** | Doorstop injects into the Unity process; Il2CppInterop generates interop assemblies; Harmony (`0Harmony.dll`) patches IL2CPP/C# methods. Pinned as BepInExPack_FootballManager26 6.0.738 on Thunderstore. | Foundation loader. Harmony can patch `FM.*`/`SI.*` C# methods. | Open (LGPL/MIT family); builds.bepinex.dev | SOURCE VERIFIED |
| **FMSuperScout** (`mavarobli/FMSuperScout`) | BepInEx IL2CPP plugin that **reads its own process memory via `ReadProcessMemory`** (not raw deref — crash-safe) and walks `game_plugin.dll` vtables to classify person objects. Read-only. Offsets pinned to FM26 26.3.x. | Reads full DB (45k+ players/staff): CA/PA, attributes (stored ×5), contracts, `team+0xA0` schedule → `+0x94` next-match date. **Read-only, never writes.** | MIT; full C# source | SOURCE VERIFIED |
| **FMMatchLens** (`osnsyc/FMMatchLens`) | BepInEx IL2CPP plugin. Installs a **native detour** (MonoMod `INativeDetour`) on a `game_plugin.dll` match-update function (resolved by SHA-256 → fixed RVA, e.g. FM26 Steam build RVA pinned; FM27 build is a different RVA). Reads the live `GAME_MATCH` object every tick. | **Reads the live match engine tick-by-tick**: ball XYZ, per-player positions/speed, a native momentum/event vector (passes, shots, goals, cards with event-type enums), xG, ratings, lifecycle/period bytes. Saves `.fmlens` archives; local HTTP+WebSocket dashboard. Read-only. | MIT; full C# source | SOURCE VERIFIED |
| **FM26Access** (`GreenBeanGravy/FM26Access`, archived) | BepInEx IL2CPP + **Harmony patches on C# UI types**: `FM.UI.FMDialogHandler.HandleTriggerDialogEvent`, `DialogManager.CloseCurrentDialogEvent`, `FM.Match.MatchCommentaryComponent.m_commentaryState`. Uses `Resources.FindObjectsOfTypeAll` + Il2CppType. | Reads UI state / match commentary for a screen-reader. Demonstrates **Harmony hooking of FM26's managed match+dialog layer** — the clean way to intercept UI-level actions. | MIT; full C# source | SOURCE VERIFIED |
| **FM Reloaded** (`jo13310/FM_Reloaded`) | Cross-platform FM26 mod manager, one-click BepInEx install. | Mod management only. | GitHub repo | DOCUMENTED |
| **jal-co/FMMLoader-26** | FM26 mod loader (TypeScript). | Loader tooling. | GitHub | DOCUMENTED |

### 3.2 Native external / injected editors (FM24 and FM26)

| Tool | Mechanism | What it edits | Licence / source | Class |
|---|---|---|---|---|
| **FMODD** (`Kasnm1/football-manager-ODD`) | Windows companion. Resolves a **read-only process handle**, identifies module by **EXE SHA-256** (FM24 `fm.exe`; FM26 `game_plugin.dll`), resolves objects by **vtable RVA + RTTI + UID + expected-old-value checks**, then does validated writes with write-back verification. For some effects it installs **native code detours** via a bundled `fmodd_hook_core.dll` at pattern-matched RVAs. | Players, clubs, finances, training, injuries, morale, league standings (+1 point item). **Reads fixtures & results** from native pools (`FIXTURE`, `sicomps::FIXTURE_RESULT` short-lived, `db::SCORELINE::BASIC_SCORELINE` persistent). Installs a **referee-decision hook** that biases card decisions of an in-progress match toward one side ("black whistle"). | "Source available", non-commercial; Python source on GitHub, binary on fmodd.com | SOURCE VERIFIED |
| **FMRTE** | Real-time editor; reads/writes save data in memory (memory scanning). One edition per FM year back to FM12; subscription covers 12→27. No plugin/API/SDK. | Players, clubs, competitions (standings, points, reputation). **Fixtures only indirectly via pre-game files; no live match-result or match-event editing listed.** | Commercial (€7.99/edition or sub); closed source | DOCUMENTED |
| **FM Live Editor 26 (FMLE26)** / FM24€0 | Live editors. FM24€0 explicitly reads+writes another process's memory (GPLv3, open source). | Attributes (incl. hidden), contracts, finances; heal injuries, fix fitness, remove bans, morale. **No fixture/match-result editing.** | FMLE26 closed/£5.49; FM24€0 GPLv3 | DOCUMENTED (FM24€0 source not located) |
| **FMCET / tdg6661 Cheat Engine tables** | Cheat Engine `.CT` tables; AOB-scanned pointers. Author tdg6661 (Patreon). FMSuperScout's offsets are derived from these; FMODD cross-checks against them. | Player/club fields; "reference for field locations". | Freeware tables | DOCUMENTED |
| **FM Genie Scout 26** | External scout tool; build-gated to FM26 version. Does not appear to use live memory writing (reads save/DB). | Scouting; In-Game Scout overlay. | Freeware; closed | DOCUMENTED |
| **Official In-Game Editor (IGE)** DLC ($8.99) | SI's own live editor inside the game. | Live-edit attributes, finances, contracts, morale, heal injuries. **Cannot create/delete clubs/leagues (pre-game editor only). No documented live match-result or fixture editing.** | Paid DLC | DOCUMENTED |
| **Official Pre-Game Editor** (free) | Edits the database before a save starts; produces `.fmf` editor-data files. | Everything structural pre-save; the route "real fixtures/results" packs use. | Free | DOCUMENTED |

### 3.3 Save-file parsers (read-only; all MIT)

| Tool | Scope | Class |
|---|---|---|
| **rhiever/fmsave** (+ kyleboas fork) | FM26 (& early FM27) save → Python/CSV/JSON. 30 readers incl. **fixtures, league-tables, player-match-stats, player-season-stats**. Read-only. Full `_container.py` source verified (header magic, zstd frames, trailer directory). | SOURCE VERIFIED |
| **spadesM/fm-toolkit** | Extends fmsave; documents the **81-section container**, 28 DB tables, `simatch.fmf` match-engine model files, IL2CPP metadata extractor. Read-only. | SOURCE VERIFIED |
| **ChristianStaubo/fm26-scout** | FM26 `.fm` exporter; documents player block, `game_db.dat`, `match_stats_cfg.dat` per-match stat blobs. Read-only. Reverse-engineered by diffing before/after-one-match saves. | SOURCE VERIFIED |
| **kuhyx fm24_searcher** | FM24 DB parser; documents FM24 `fmf.`/`tad.` + zstd format. Read-only. | SOURCE VERIFIED |

### 3.4 Skins
FM skins are XML panel definitions; they **cannot execute arbitrary code**. The "instant result" skins (Wannachup) only *expose a button for a function already built into the game* for Touch/Console — i.e. the engine already has a one-click resolve path. A skin cannot be our integration mechanism, but it confirms a native instant-resolve code path exists (lead for §6). (DOCUMENTED.)

---

## 4. Save format findings

`.fm` save = **`\x02\x01fmf.` magic + 26-byte header + run of Zstandard frames + a trailing zstd directory frame** (this is the generic SI "fmf." resource-archive container; the same magic appears in `.fmf` editor/resource files and is even registered in TestDisk/PhotoRec). (SOURCE VERIFIED: fmsave `_container.py`, kuhyx `binary_parser.py`, testdisk `file_fm.c`.)

- **Header (fmsave, SOURCE VERIFIED):** magic at 0–6; `u64 directory_offset` at byte 9 (`trailer_offset = 9 + directory_offset`); `u32 content_end_rel` at byte 22. Directory entries end with a 40-byte tail of `5× u64` (rel_offset, compressed_size, decompressed_size, +2 metadata). 44 of the decompressed `.dat` sections begin with inner magic `03 01 'tad.'`.
- **~81 named sections** (64 `.dat` + 17–19 `.cmt` language commentary) plus **per-match `.apm` (3D animation/physics replay) and `.scm` (scorecard/event-summary) files** accumulated as matches are played. These `.apm`/`.scm` are the modern equivalent of the old `.pkm` match replays.
- **Match/fixture data in the save** (fm-toolkit/fmsave tables, SOURCE VERIFIED): `fixtures` (home/away teams, `home_goals`/`away_goals`, `played`, `match_record_id`, `match_rules_template`), `league-tables` (full standings rows), `player-match-stats`, `player-season-stats` (58 stat fields), `player-season-history`, `competitions`, `stages`, `competition-rules`. So **FM stores per-fixture player stats, ratings and events in the save** — confirming the data model a FIFA result would have to populate.
- **`.pkm` / `.apm` / `.scm` internal structure:** No public parser decodes the 3D replay payloads. fm-toolkit treats `.apm`/`.scm` as opaque telemetry. (UNKNOWN beyond their existence.)
- **Writing a save is unsolved/hostile:** every public tool is read-only. The payloads inside `.fmf` resource archives (e.g. shortlist `.fmf`) are **per-file encrypted** (random nonce; identical input → different output; key in `GameAssembly.dll`) — fm-toolkit's `.fmf`-write research concluded producing an FM-accepted `.fmf` is **not feasible** without SI's Resource Archiver or extracting the key. (SOURCE VERIFIED, fm-toolkit `fmf-format.md`.) Implication: **offline save-file editing of results is not a viable write path**; our writes must be live (in-memory) while FM is running.
- **Match-engine model files** live in `shared/data/simatch.fmf` (xG logistic models per shot type, QME Poisson/Normal/Binned distributions, player-rating coefficient tables, ball physics `.bta`, tactical presets). These are editable by hex-editing extracted frames and re-archiving with SI's bundled **Resource Archiver** (community "match engine mods" do this). This is tuning, **not** result injection. (SOURCE VERIFIED + DOCUMENTED.)

---

## 5. Match lifecycle model — known vs unknown

Stages from scheduling to native post-match processing. Each stage notes what is reachable and the strongest evidence.

| Stage | What FM does | Reachable? / how | Class |
|---|---|---|---|
| **(0) Fixture scheduling** | Fixtures stored per team in a native schedule object and in competition fixture pools. | **READ: yes.** FM26: `DbTeam+0xA0` → schedule, `+0x94` next-match date (FMSuperScout); FMODD reads `FIXTURE_DEL_ARRAY` two-level pools, `FIXTURE`/`FIXTURE_RESULT` vtables. In save: `fixtures` table. | SOURCE VERIFIED |
| **(1) Detect the managed club's upcoming fixture** | Next fixture for the human-managed club becomes "today" on match day. | **YES.** Resolve human manager object (FM26 `manager_person_offset=0x450`; FM24 similar), its club/team, then team schedule next-match date == game date. Both FMSuperScout and FMODD do this. | SOURCE VERIFIED (reads) / INFERRED (as a trigger) |
| **(2) Detect/intercept match *start*** | User advances → FM either opens the 3D match (`FM.Match.MatchSetup` + `MatchPlaybackController`, runtime-state byte `4/6`) or does "instant result" (`EventFmxRequestQuickMatch`). FM24 uses native `MATCH_SESSION_MANAGER` (`fm.exe+…`, begin/end vector). | **DETECT: yes** (FMMatchLens detours the per-tick match-update fn; FMODD/FM26Access read `MatchSetup`/state bytes; FM26Access Harmony-patches UI). **INTERCEPT (prevent normal sim): UNKNOWN** — nobody has shown blocking the sim from starting while keeping the fixture "playable". | DETECT SOURCE VERIFIED; INTERCEPT UNKNOWN |
| **(3) Execute externally in FIFA** | — (our side) | Out of FM scope; FM must merely be paused/held at match day. Holding FM at the pre-match screen is trivially achievable (don't advance). | INFERRED |
| **(4) Represent the external match in FM structures** | A completed match is a `GAME_MATCH` runtime object + a persisted `BASIC_SCORELINE`/`FIXTURE_RESULT` + per-player match-stat records + events (goals/cards) + ratings. | **Structures are READABLE and their layouts partly mapped** (FMMatchLens maps `GAME_MATCH`, Team, MatchPlayer, PlayerStats, MomentumEvent incl. goal/card/pass event-type enums; FMODD maps `FIXTURE_RESULT`/`BASIC_SCORELINE` goal-event records). **Constructing a valid one from outside is UNKNOWN.** | LAYOUTS SOURCE VERIFIED; synthesis UNKNOWN |
| **(5) Supply the match info** | — | Two candidate surfaces: (a) write into native result/stat structures while FM holds; (b) hook the sim so it *produces* the desired outcome. | INFERRED |
| **(6) Native post-match processing** | FM natively applies: result→tables, ratings, morale, condition/fatigue, injuries, suspensions, finances, news, history. These are driven by native code reacting to the authoritative match object. | **This is the crux.** Steering the sim (stage 2+) guarantees it because FM's own engine finishes the match → native pipeline runs. **Post-hoc editing of the scoreline does NOT guarantee the full pipeline runs** — editing `BASIC_SCORELINE` after the fact is "changing a scoreline", not driving ratings/morale/injuries. Whether a late in-memory edit (between whistle and processing) triggers the full native cascade is UNKNOWN. | UNKNOWN (the key experiment) |

**What is genuinely demonstrated vs. our goal:**
- Reading save data — **SOLVED** (fmsave/fm-toolkit/fm26-scout).
- Reading running game state — **SOLVED** (FMSuperScout, FMMatchLens, FMODD).
- Editing player/club data live — **SOLVED** (FMODD, FMRTE, FMLE26, IGE).
- Editing a fixture *result* value — **partially shown** (FMODD reads results; FMRTE/pre-game can set pre-determined league results; live result-write not clearly public).
- Accessing match *events* live — **SOLVED read-side** (FMMatchLens decodes goals/cards/passes/shots with event-type enums and ticks).
- Replacing match simulation — **NOT demonstrated by anyone.**
- Injecting externally generated events — **NOT demonstrated** (closest: FMODD's referee hook biases FM's *own* generated events).
- Triggering native post-match processing from an external result — **NOT demonstrated; UNKNOWN.**

---

## 6. Integration route options (ranked, with required local Windows experiments)

All experiments are **read-only first**, on **copies of saves**, against a **pinned build** (record `game_plugin.dll`/`fm.exe` SHA-256). Never touch original installs or valuable saves; never defeat Denuvo.

### Route A — FM26 "steered simulation" via native `game_plugin.dll` hook (RECOMMENDED primary)
**Idea:** Let FM26's own native engine run the managed-club match, but hook it so its outcome and key events converge on the FIFA ledger (final score, scorers, cards, broad shot/possession shape). Because FM's own engine finishes the match, **native post-match processing (stage 6) runs for free.** This is the only route with a credible path to full-consequence integration.
**Why plausible:** FMMatchLens already installs a native detour on the per-tick match-update function and reads the full event/rating pipeline; FMODD already hooks a *decision* point (referee) to bias outcomes of a live match. Steering is "FMODD's hook class, aimed at scoreline/goal events instead of cards, driven by an external ledger."
**Feasibility:** Medium. Hard parts: forcing a *specific* multi-goal scoreline and specific scorers deterministically without destabilising the engine; mapping FIFA events → FM event semantics; per-build RVA fragility.
**Risk:** Hook on a Denuvo-protected process family (mitigated: the hook is on `game_plugin.dll`, which community tools already detour; we must still never tamper with Denuvo/`fm.exe` integrity).
**Experiments:**
1. **(Read)** Install BepInEx 6 IL2CPP + FMMatchLens on a pinned FM26 build; play one managed match; confirm you can observe score, scorers, cards, ticks, lifecycle bytes live. Record the `game_plugin.dll` SHA-256 and the match-update RVA FMMatchLens resolves.
2. **(Read)** With FMSuperScout-style reads, locate the live `GAME_MATCH` object and its score/period/lifecycle fields during a managed match; correlate with the save's `fixtures`/`player-match-stats` after saving (diff before/after via fm26-scout's method).
3. **(Read→reason)** In Ghidra, load the pinned `game_plugin.dll`; locate the match-update function at the known RVA; identify where the score and goal-event vector are written and where the RNG (LCG, per community) is read. Do **not** patch yet. Deliverable: candidate write-points for a goal event and for final-whistle.
4. **(Controlled write, throwaway save)** Prototype forcing exactly one extra goal for the managed club at a chosen tick by writing the goal-event record + score byte at the identified point, then let FM finish; save; reload; verify via fmsave whether ratings/morale/condition/table all updated natively. **This single experiment answers the whole project's feasibility.**

### Route B — FM26 managed interception of the match-start / instant-result path (RECOMMENDED companion to A)
**Idea:** Harmony-patch the C# UI/flow layer so that when the managed fixture is about to be simulated, we divert to "hold" (play in FIFA), then hand results back. `EventFmxRequestQuickMatch`, `FM.Match.MatchSetup`, `MatchPlaybackController` are confirmed C# symbols; FM26Access proves Harmony works on `FM.UI`/`FM.Match`.
**Feasibility:** Medium for *detect/hold*; the "hand results back and trigger processing" still bottoms out in Route A or D.
**Experiments:**
1. **(Read)** Harmony-postfix `FMDialogHandler.HandleTriggerDialogEvent` and probe for a method raising `EventFmxRequestQuickMatch`; log when the managed fixture triggers it.
2. **(Read)** Enumerate `MatchSetup`/`MatchPlaybackController` instances (FM26Access pattern) at a managed match; map `ViewableMatchType` and the native `game_plugin` state byte (`4/6`).
3. **(Reason)** Determine whether a prefix returning early can *hold* the match at pre-kickoff without corrupting state. Read-only reconnaissance of the methods first.

### Route C — "Steered simulation" by editing match-engine model files (LOW value for this goal)
**Idea:** Hex-edit `simatch.fmf` frames to bias the engine. **Rejected as integration mechanism:** it tunes probabilities globally, cannot target one fixture or reproduce a specific scoreline/scorers, and requires SI's Resource Archiver to repack. Useful only as background on engine math. (DOCUMENTED.)

### Route D — Post-hoc result/stat editing (live memory or, in theory, save) (PARTIAL; fallback)
**Idea:** Let FM "instant result" the managed fixture, then overwrite the `BASIC_SCORELINE`/`FIXTURE_RESULT` + per-player match-stat + rating structures to the FIFA ledger while FM holds between whistle and processing.
**Feasibility of "changing the scoreline": high. Feasibility of full native downstream processing: UNKNOWN and probably partial** — this is the "changing a scoreline is not full integration" trap. Editing stored results likely updates tables (which read those values) but may not regenerate morale/condition/injury effects that are computed *during* a simulated match.
**Experiments:**
1. **(Read)** FMODD-style: locate `FIXTURE_RESULT`/`BASIC_SCORELINE` for the just-played managed fixture; read its goal-event records and score offsets (FMODD documents `result_*_goals_offset`, `result_event_root_offset`).
2. **(Write, throwaway)** Edit score + goal events; save; reload; via fmsave diff whether (a) league table, (b) player-season-stats, (c) morale, (d) condition, (e) injuries changed. Classify which consequences are "value-driven" (update) vs "event-driven" (do not). This bounds how much D can ever deliver.

### Route E — FM24 native detours via Ghidra (ALTERNATIVE, higher effort)
**Idea:** Same as A/D but on FM24's single `fm.exe`. FMODD already carries FM24 match-session, fixture-result, scoreline and referee-hook RVAs for Steam 24.4.2, and a community C++ bit-for-bit match-engine reimplementation (private) reports the RNG is an LCG and that rating calc/modulator/evaluator were reconstructed and validated against the live game.
**Feasibility:** Medium-low. `fm.exe` is a ~500 MB Denuvo-protected monolith; no managed loader, so everything is external injection/detours; AOB scanning a 500 MB image per build. Mature CE tables/editors exist but none replaces the sim.
**Experiments:** mirror Route A steps 3–4 but entirely in native space (CE table to locate, Ghidra on `fm.exe` to analyse, external injector to test), on a throwaway save.

### Ranking
1. **Route A (FM26 native steered sim)** — only credible path to full native consequences; best tooling precedent.
2. **Route B (FM26 managed detect/hold)** — needed front-end for A/D; low risk reconnaissance.
3. **Route D (post-hoc edit)** — fast partial win; use to *measure* which consequences are value- vs event-driven.
4. **Route E (FM24 native)** — fallback if FM26 per-build churn or Denuvo proves too hostile; FM22 (no Denuvo) is the easiest legacy sandbox for technique development.
5. **Route C (model-file tuning)** — not an integration route; background only.

---

## 7. Recommended FM version: **FM26** (pin a stable Steam build, e.g. 26.3.x)

Reasoning:
- **In-process managed loader exists and works** (BepInEx 6 IL2CPP) — you get Harmony on the C# UI/flow layer *and* P/Invoke/native-detour access to `game_plugin.dll` in one process. FM24 has neither; it forces pure external injection.
- **The simulation is still native C++** in `game_plugin.dll`, so the hard "steer the engine" work is the same class of problem as FM24 — but reachable from inside a managed plugin, with three independent open-source precedents (FMMatchLens detour, FMSuperScout reads, FM26Access Harmony) you can study and licence (MIT).
- **Rich, already-mapped structures:** FMMatchLens has published live offsets for `GAME_MATCH`, teams, match players, per-player stat blocks and the goal/card/pass event vector; FMODD has published fixture/result/scoreline layouts. This is a large head-start specifically on stages 4–6.
- **Save format fully parseable** (fmsave/fm-toolkit/fm26-scout) for before/after verification of native processing — essential for the one experiment that decides the project.
- **Downside accepted:** Denuvo + per-patch build churn (offsets move every patch; FMSuperScout documents a re-pin procedure; FMMatchLens gates by SHA-256). Mitigate by pinning one offline build and never auto-updating.
- **FM22 as a secondary sandbox** (no Denuvo listed) is worth keeping for developing native-hook technique cheaply, but FM26 is where the deliverable should target because of the managed-loader ecosystem and published offsets. FM27 is the same architecture and the tooling is already following it, so FM26 technique ports forward.

**The decisive next action:** Route A experiment 4 (or Route D experiment 2) on a throwaway FM26 save — does a forced/edited result cause FM to natively regenerate ratings, morale, condition, injuries and tables? That single read→diff test converts the project's central UNKNOWN into CONFIRMED or refuted.

---

## 8. Evidence ledger

| # | Claim | Class | Source |
|---|---|---|---|
| 1 | FM26 is first FM on Unity; core simulation/match engine stays on SI proprietary (native) systems, Unity does rendering/presentation. | DOCUMENTED | en.wikipedia.org/wiki/Football_Manager_26; videogameschronicle, purexbox |
| 2 | FM26 ships `fm.exe` + `GameAssembly.dll` (IL2CPP native) + `fm_Data/il2cpp_data/global-metadata.dat` (v31, magic `0xFAB11BAF`) + `il2cpp.usym`. => IL2CPP, not Mono. | SOURCE VERIFIED | fm-toolkit docs `FM26_REVERSE_ENGINEERING_*` (raw.githubusercontent.com/spadesM/fm-toolkit) |
| 3 | FM26 match engine + persistent DB objects live in native `game_plugin.dll`, loaded after BepInEx chainloader. | SOURCE VERIFIED | FMSuperScout `Dumper.cs`/`Fields.cs`; FMMatchLens `GamePluginBuildCatalog.cs`; FMODD `game_layout.py` |
| 4 | FM26 C# symbols incl. `FM.Match.MatchSetup`, `MatchPlaybackController`, `EventFmxRequestQuickMatch`, `FMPlayerRating`, `FM.UI.FMDialogHandler`. | SOURCE VERIFIED | fm-toolkit (global-metadata extraction); FM26Access `DialogHandlerPatch.cs`, `MatchCommentaryAnnouncer.cs` |
| 5 | BepInEx 6 IL2CPP (win-x64) is the working FM26 loader; needs `ignore_disable_switch=true` (FM self-relaunch sets `DOORSTOP_DISABLE`); BepInExPack_FootballManager26 6.0.738 on Thunderstore. | SOURCE VERIFIED / DOCUMENTED | FM26Access README; thunderstore.io/c/football-manager-26/p/BepInEx/BepInExPack_FootballManager26 |
| 6 | FMSuperScout: BepInEx IL2CPP plugin, reads own memory via `ReadProcessMemory` (crash-safe), walks `game_plugin.dll` vtables, read-only; offsets pinned FM26 26.3.x; team schedule `+0xA0`, next-match `+0x94`. | SOURCE VERIFIED | raw.githubusercontent.com/mavarobli/FMSuperScout (`Plugin.cs`,`MemScan.cs`,`Fields.cs`,`repin-guide.md`); MIT |
| 7 | FMMatchLens: BepInEx IL2CPP plugin installs MonoMod `INativeDetour` on a `game_plugin.dll` match-update function resolved by SHA-256→RVA; reads live `GAME_MATCH` (ball XYZ, player positions, momentum/event vector with goal/card/pass enums, xG, ratings, lifecycle bytes); read-only; `.fmlens` archives. | SOURCE VERIFIED | raw.githubusercontent.com/osnsyc/FMMatchLens (`GameMatchTickHook.cs`,`GamePluginBuildCatalog.cs`,`Offsets.cs`); MIT |
| 8 | FM26→FM27 same split architecture; FM27 match-update native ABI gained a 5th argument; 720-tick sim lead (FM26 360). | SOURCE VERIFIED | FMMatchLens `CHANGELOG.md`, `Offsets.cs` (v0.7.0 vs v0.6.1) |
| 9 | FM26Access: Harmony patches `FMDialogHandler.HandleTriggerDialogEvent`/`DialogManager.CloseCurrentDialogEvent`, reads `FM.Match.MatchCommentaryComponent.m_commentaryState`; uses `SI.Bindable`, `FM.UI`. | SOURCE VERIFIED | raw.githubusercontent.com/GreenBeanGravy/FM26Access (`Patches/*`,`MatchStatus.cs`,`MatchCommentaryAnnouncer.cs`); MIT |
| 10 | FMODD identifies FM24 by `fm.exe` SHA-256 and FM26 by `game_plugin.dll`; resolves objects by vtable RVA+RTTI+UID+expected-old-value; validated writes w/ write-back; some effects via native `fmodd_hook_core.dll` detours at pattern RVAs. | SOURCE VERIFIED | raw.githubusercontent.com/Kasnm1/football-manager-ODD (`game_layout.py`,`hook_native_core.py`,`RUNTIME_CONTRACTS.md`); source-available, non-commercial |
| 11 | FMODD reads results from native pools: `FIXTURE`, short-lived `sicomps::FIXTURE_RESULT`, persistent `db::SCORELINE::BASIC_SCORELINE`; documents score/goal-event offsets. | SOURCE VERIFIED | FMODD `game_layout.py` (FM24 & FM26 layouts), `RUNTIME_CONTRACTS.md` |
| 12 | FMODD installs a referee-decision hook ("black whistle") biasing card decisions of an in-progress match toward one participant — i.e. steers FM's own engine, not an external result. | SOURCE VERIFIED | FMODD `referee_hook.py`, `probe_referee_context.py`, `match_integrity.py` |
| 13 | `.fm` save = `\x02\x01fmf.` + 26-byte header (u64 dir offset @9, u32 @22) + zstd frames + zstd trailer directory (40-byte 5×u64 tails); ~81 sections (.dat/.cmt) + per-match `.apm`/`.scm`. | SOURCE VERIFIED | fmsave `_container.py`; fm-toolkit `FM26_SAVE_DATABASE_SCHEMA_AND_81_SECTIONS.md`; testdisk `file_fm.c` |
| 14 | Save stores fixtures (home/away goals, played, match_record_id), league-tables, player-match-stats, player-season-stats, competition-rules — i.e. per-fixture player stats/ratings persist. | SOURCE VERIFIED | fm-toolkit 28-table schema; fmsave readers; fm26-scout `match_stats_cfg.dat` |
| 15 | `.fmf` resource-archive payloads are per-file encrypted (key in `GameAssembly.dll`); producing an FM-accepted `.fmf` from outside judged not feasible without SI Resource Archiver. | SOURCE VERIFIED | fm-toolkit `docs/fmf-format.md` |
| 16 | Match-engine math lives in `shared/data/simatch.fmf` (xG logistic models, QME distributions, rating coefficients, ball physics, tactics); hex-editable + repack via SI Resource Archiver (community ME mods). | SOURCE VERIFIED / DOCUMENTED | fm-toolkit `FM26_REVERSE_ENGINEERING_SAVE_AND_GAME_FILES.md`; fmprojects.substack.com |
| 17 | DRM: FM19/20/21/23/24/26 list Denuvo Anti-tamper on Steam; FM22 lists no 3rd-party DRM; FM17 32-or-64-bit, no Denuvo listed. | SOURCE VERIFIED | store.steampowered.com app pages 872790/1100600/1263850/1569040/1904540/2252570/3551340/482730 |
| 18 | FM26 + FM24 both 64-bit, DirectX 11; In-Game Editor sold as DLC; Steam Workshop listed for FM26. | SOURCE VERIFIED | Steam store (FM24 2252570, FM26 3551340) |
| 19 | FM20 first 64-bit-only Windows FM (32-bit dropped). | DOCUMENTED | fmscout system-requirements article |
| 20 | Official IGE live-edits attributes/finances/contracts/morale, heals injuries; cannot create/delete clubs/leagues (pre-game only); no documented live match-result/fixture edit. | DOCUMENTED | deltiasgaming IGE guide; fmscout |
| 21 | Community "real fixtures/results" packs are pre-game `.fmf` editor-data; only league-phase results, cups simulated; set results before save; not live. | DOCUMENTED | fmscout/sortitoutsi real-fixture-results pages |
| 22 | FM skins are XML and cannot run code; "instant result" skins merely expose a built-in Touch/Console resolve function. | DOCUMENTED | fmscout Wannachup FM24 instant-result skin page |
| 23 | FMRTE memory-based editor, one edition per FM year (12→27); edits players/clubs/competitions; no plugin SDK; fixtures only via pre-game files; no live match-result editing. | DOCUMENTED | fmrte.com |
| 24 | A private community project reports a bit-for-bit C++ reimplementation of the FM23 native match engine: RNG = LCG, rating calc/modulator/evaluator reconstructed and validated vs live game. Self-reported, source not published. | DOCUMENTED (unverified) | sortitoutsi.net/content/77224 |
| 25 | fm26-scout reverse-engineered FM26 saves by diffing before/after-one-match saves — the recommended verification method for native post-processing. | SOURCE VERIFIED | github.com/ChristianStaubo/fm26-scout README; `fm26_export.py` |
| 26 | FM24 save/DB format = `fmf.`/`tad.` + zstd; CA/PA not readable from DB alone (HTML import needed). | SOURCE VERIFIED | kuhyx `fm24_searcher/binary_parser.py` (MIT) |
| 27 | Replacing match simulation, injecting externally generated match events, and triggering native post-match processing from an external result are NOT demonstrated by any located tool. | INFERRED (absence across all sources reviewed) | §3 tool survey |
| 28 | FM26 exact Unity version string / UnityPlayer build; `.apm`/`.scm`/`.pkm` internal payload format; whether a late in-memory result edit triggers the full native consequence cascade. | UNKNOWN | — |
| 29 | sortitoutsi.net full forum pages (tool threads), pcgamingwiki FM pages. | BLOCKED (HTTP 403) | sortitoutsi.net, pcgamingwiki.com |

---

### Appendix — downloaded source (read-only, not executed)
Stored under `/tmp/claude-0/-home-user-NST/953f70f4-169d-559b-9007-0495bfe4f535/scratchpad/fm_research/`: `fmsuperscout/`, `fmmatchlens/` (+`v061/`), `fmtoolkit/` (RE docs), `fmodd/` (layout + probe scripts), `fm26access/`, `fmsave/`, `kuhyx/`. All MIT except FMODD (source-available, non-commercial) and fm-toolkit (MIT; vendored rhiever/fmsave MIT). None executed.
