# FM-FC Hybrid: FIFA match-engine control research (FIFA 15–22, focus FIFA 20 and FIFA 22)

Status: desk research only. **Nothing in this document has been tested in-game.** No downloaded code was executed.
Research date: 2026-10-31. Workstream: FIFA match-engine control.

---

## 0. Method, legend and source snapshot

### Classification legend

| Tag | Meaning |
|---|---|
| **CONFIRMED** | I observed the artefact directly in this session: a repo or file exists, a licence file says X, a file is plain XML. This tag never covers in-game behaviour. |
| **SOURCE VERIFIED** | Traced to actual implementation source: Lua, Cheat Engine Auto-Assembler, C#, or a DB meta/schema file shipped with a tool. The code shows the mechanism exists. It does not prove the mechanism works in-game today. |
| **DOCUMENTED** | Stated in the tool author's own documentation (wiki, README, changelog) or in reputable press. No implementation was inspected. |
| **INFERRED** | My reasoning from SOURCE VERIFIED or DOCUMENTED facts, e.g. carrying a FIFA 21 schema over to FIFA 22. |
| **UNKNOWN** | No evidence found. Needs a local experiment (Section 9). |
| **BLOCKED** | Would require bypassing DRM, authentication or anti-cheat, or using online EA functionality. Out of scope by project rule. |

### Downloaded material (read-only, never executed)

Location: `/tmp/claude-0/-home-user-NST/953f70f4-169d-559b-9007-0495bfe4f535/scratchpad/fifa_research/`. Each entry is a shallow `git clone`; wikis were cloned via `<repo>.wiki.git`.

| Local dir | Upstream | Commit (date) | Licence file |
|---|---|---|---|
| `FIFA-20-Live-Editor` | github.com/xAranaktu/FIFA-20-Live-Editor | a2451fc (2020-04-24), archived 2020-09-29 | GPL-3.0 |
| `FIFA-21-Live-Editor` | github.com/xAranaktu/FIFA-21-Live-Editor | d5307ba (2021-09-13) | GPL-2.0 (but ships closed `FIFALiveEditor.DLL`, `Launcher.exe`, `Injector.exe` binaries) |
| `FIFA-21-CM-Cheat-Table` | github.com/xAranaktu/FIFA-21-CM-Cheat-Table | 1ed689a (2021-04-27) | GPL-3.0 |
| `FIFA-22-Live-Editor` | github.com/xAranaktu/FIFA-22-Live-Editor | 3e88c2f (2022-06-23), archived 2022-10-10 | GPL-3.0 (repo holds only Lua scripts, mods and changelog; the DLL was distributed via Patreon) |
| `FIFA-22-CM-Cheat-Table` | github.com/xAranaktu/FIFA-22-CM-Cheat-Table | 3418251 (2022-04-26) | GPL-3.0 |
| `FIFA-19---Career-Mode-Cheat-Table` | github.com/xAranaktu/FIFA-19---Career-Mode-Cheat-Table | 8ed0a63 (2019-09-08) | MIT (inside `FIFA 19 - CM Cheat Table/LICENSE`) |
| `FIFA-23-Live-Editor` | github.com/xAranaktu/FIFA-23-Live-Editor | 757fe70 (2023-08-17) | GPL-3.0 |
| `FC-24-Live-Editor` | github.com/xAranaktu/FC-24-Live-Editor | e7fb905 (2024-08-01) | GPL-3.0 |
| `FC-26-Live-Editor` | github.com/xAranaktu/FC-26-Live-Editor | c3bf990 (2026-08-10) | no LICENSE file at top level |
| `FIFASquadFileDownloader` | github.com/xAranaktu/FIFASquadFileDownloader | cfe9aeb (2026-09-18) | MIT |
| `FrostyToolsuite` | github.com/CadeEvs/FrostyToolsuite (branch 1.0.6.3) | e400dcb (2023-09-29) | CC BY-NC-ND 4.0 (stated in README.md) |
| `wiki_FIFA-20-Live-Editor` | FIFA-20-Live-Editor wiki | 373d8da | n/a |
| `wiki_FIFA-21-Live-Editor` | FIFA-21-Live-Editor wiki | 414b1ac | n/a |
| `wiki_FIFA-22-Live-Editor` | FIFA-22-Live-Editor wiki | 2db636d | n/a |
| `wiki_FIFA-22-CM-Cheat-Table` | FIFA-22-CM-Cheat-Table wiki | e37a31a | n/a |
| `wiki_FIFA-23-Live-Editor` | FIFA-23-Live-Editor wiki | a8c9a89 | n/a |
| `wiki_FC-24-Live-Editor` | FC-24-Live-Editor wiki | 9eae8ac | n/a |

My parsing helpers live in `/tmp/claude-0/-home-user-NST/953f70f4-169d-559b-9007-0495bfe4f535/scratchpad/scripts/`: `dbmeta*.py`, `ctentries.py`, `ctscript.py`, `ctmeta.py`. They only parse XML and Lua text, run with `python3 -I`.

---

## 1. Summary

1. **FIFA 22 is the latest PC FIFA that can be scripted without touching anti-cheat.** EA AntiCheat (kernel-level) debuted with FIFA 23. The FIFA 23 and FC 24 Live Editors run the game through a *fake* `EAAntiCheat.GameServiceLauncher.exe` so the real anti-cheat never starts. That is an anti-cheat bypass, so FIFA 23 and later are **BLOCKED** for this project. FIFA 20, 21 and 22 have Denuvo (activation) but no EAAC. Aranaktu's documented FIFA 22 workflow is "run Launcher.exe, run FIFA 22", which injects a DLL; it contains no DRM bypass step (DOCUMENTED).
2. **A FIFA 20 "Live Editor" exists, but it is a Cheat Engine table.** The README says the FIFA 20 Live Editor was "previously known as Career Mode Cheat Table" and is built in Cheat Engine. The first DLL-based Live Editor with an in-process Lua 5.3 API is FIFA 21. FIFA 22 extends that API with `CreatePlayer`, `GetPlayersStats` and related functions. (SOURCE VERIFIED / DOCUMENTED)
3. **Open versus closed.** The Live Editor core (DLL plus launcher) is closed for FIFA 21–26. Open parts are the Lua docs, the example scripts and the `lua/libs` wrapper, which shows the closed DLL exposes `c*` natives such as `cTransferPlayer`. Cheat tables for FIFA 19–22 are plain-XML `.CT`/`.CETRAINER` files whose Lua and Auto-Assembler source is fully readable (GPL-3.0, or MIT for FIFA 19). They use AOB signature scans plus code-cave hooks.
4. **Configuring squads, lineups, formations and tactics is programmatically feasible in FIFA 20, 21 and 22.** It is all exposed as t3db database tables, edited in memory: `players`, `editedplayernames`, `teamplayerlinks`, `teams`, `default_teamsheets`, `default_mentalities`, `teamsheets`, `mentalities`, `formations`. FIFA 22 adds `buildupplay` and `chancecreation` fields and changes width/depth sliders from 0..9 to 1..100. (SOURCE VERIFIED from the FIFA 21 `db_meta.xml` and the FIFA 22 CT `consts.lua` meta)
5. **No tool exposes live match events (goal, sub, card) through a documented API in FIFA 20–22.** Live Editor match/event hooks (`AddEventHandler`, `CareerModeEvent` with `USER_MATCH_COMPLETED`, `INJURY` and similar) only exist in LE v2 (FIFA 23 and FC 24+), and those are BLOCKED. What we have for FIFA 22:
   - **Career mode:** `GetPlayersStats()` gives per-player season totals for goals, assists, yellow, red, apps, avg rating and clean sheets. The career table `career_playermatchratinghistory` holds playerid, rating, minsplayed, date and position per match (schema SOURCE VERIFIED for FIFA 21). A before/after delta gives per-match goals, assists, cards, minutes and ratings (INFERRED technique).
   - **During a match:** cheat-table hooks give live score (`MatchScore` hook, team struct `+0x226B0`), the match clock (`MatchTimer`), side/controller switching (CPU vs CPU) and substitution limits (SOURCE VERIFIED).
   - **Gaps:** shots, passes, possession and injury events are **UNKNOWN**, pending memory research or post-match screen capture.
6. **CPU vs CPU** is SOURCE VERIFIED for FIFA 20 and FIFA 22 via the cheat table's "Side Changer > CPU vs CPU" script. It hooks controller assignment and writes CPU controller IDs for both sides; the docs describe it for career mode. A vanilla Kick-Off "controllers in the middle" spectator mode is **UNKNOWN** for FIFA 20 and 22, with only an anecdotal forum report for an unnamed version.
7. **Recommendation:** use **FIFA 22** with a **disposable "bridge" Manager Career** as the primary execution mode, because only career mode has documented programmatic stat sources. Keep **Kick-Off** as the fallback for cup-rule matches (extra time and penalties). Use FIFA 20 and 21 for comparison only. See Section 8.

---

## 2. Per-version technology, tooling and protection (FIFA 15–22; FIFA 23+ for context)

| Version | Engine / PC build | Main editing tools | Aranaktu tooling | In-process scripting | Protection | Implication for us |
|---|---|---|---|---|---|---|
| FIFA 15 | Ignite (pre-Frostbite) – INFERRED | Creation Master 15, DB Master (Rinaldo; closed) – DOCUMENTED | none found in repo list | none | Origin + Denuvo; FIFA 15 was the **first Denuvo game** – DOCUMENTED (en.wikipedia.org/wiki/Denuvo) | Squad/DB file editing only; no runtime control found |
| FIFA 16 | Ignite – INFERRED | Creation Master 16 (Rinaldo, closed; DB in `data\db\fifa_ng_db.db`) – DOCUMENTED (soccergaming CM16 thread) | none | none | Origin + Denuvo – INFERRED | Same as FIFA 15 |
| FIFA 17 | Frostbite – INFERRED (common knowledge; Frosty profile `Fifa17`) | Frosty Editor / Mod Manager (`ProfileVersion.Fifa17`) – SOURCE VERIFIED | `Fifa-17---IniToCT` (AutoIt) | none | Origin + Denuvo – INFERRED | Legacy-file mods |
| FIFA 18 | Frostbite | Frosty (`Fifa18`) – SOURCE VERIFIED | `FIFA-18---Career-Mode-Cheat-Table` (archived) – CONFIRMED | Cheat Engine Lua | Denuvo (cracked on release day) – DOCUMENTED (Wikipedia Denuvo) | CE-table runtime hooks |
| FIFA 19 | Frostbite | Frosty (`Fifa19`) – SOURCE VERIFIED | FIFA 19 CM Cheat Table (MIT): GUI forms `matchfixingform`, `matchscheduleeditorform` – SOURCE VERIFIED | CE Lua + AA | Denuvo – INFERRED | Comparison only |
| **FIFA 20** | Frostbite | Frosty Editor/Mod Manager officially supports up to FIFA 20 (`ProfileVersion.Fifa20 = 20190911`), legacy DB viewer is **read-only** (`Plugins/Fifa/LegacyDatabasePlugin/IO/LegacyDbReader.cs`) – SOURCE VERIFIED; FIFA Editor Tool – DOCUMENTED | **FIFA 20 Live Editor = Cheat Engine table** `source/Live Editor.CETRAINER` (plain XML) + `source/lua/*` (GPL-3.0) – SOURCE VERIFIED | CE Lua (createTimer/readInteger etc. are CE-native) | Denuvo – DOCUMENTED (rutab.net "Взлом FIFA 20 / Версия Denuvo") | Full runtime control via readable CE scripts; no DLL Lua DB API, no `CreatePlayer` |
| FIFA 21 | Frostbite; PC = last-gen build | FIFA Editor Tool (paulv2k4; closed), RDBM 21 profile – DOCUMENTED | FIFA 21 CM Cheat Table (GPL-3) + **first DLL Live Editor** (`FIFALiveEditor.DLL`, closed) with Lua API `lua/DOC.MD` and `data/db_meta.xml` – SOURCE VERIFIED | LE Lua 5.3 (32-bit API docs) + CE | Denuvo – DOCUMENTED (rutab.net, metaratings) | Good comparison: full DB schema shipped in `data/db_meta.xml` |
| **FIFA 22** | Frostbite; **PC = PS4/XB1 (last-gen) feature set, no HyperMotion** – DOCUMENTED (PC Gamer, KitGuru) | FIFA Editor Tool / FIFA Mod Manager (closed), RDBM 22 Beta 5 (Rinaldo; free, non-commercial, closed) – DOCUMENTED; LE FAQ: "Frosty doesn't support FIFA 22" – DOCUMENTED | FIFA 22 Live Editor (closed DLL v22.1.1.9 last per changelog; Lua docs in wiki) + FIFA 22 CM Cheat Table (GPL-3, `FIFA22.CETRAINER` plain XML) – SOURCE VERIFIED | LE Lua 5.3 + CE Lua | Denuvo (bypass claims in press – DOCUMENTED gamegpu.com); activation possibly limited per device – DOCUMENTED (stevivor); **no EA AntiCheat** – DOCUMENTED (EAAC debuted with FIFA 23) | **Best candidate**: richest pre-EAAC API |
| FIFA 23 / FC 24–26 | Frostbite | LE v2 with `AddEventHandler`, `CareerModeEvent`, `GetPlugin`, `MEMORY` | – | LE Lua v2 | **EA AntiCheat (kernel)**; LE uses fake `EAAntiCheat.GameServiceLauncher.exe` (`wiki_FIFA-23-Live-Editor/Getting-Started.md`, `wiki_FC-24-Live-Editor/Getting-Started.md`) | **BLOCKED** (anti-cheat bypass) |

Offline note: the FIFA 23 LE wiki (`Game-Backup.md`) describes running the game online once "so denuvo will allow me to play offline", then switching the EA App to offline mode. The same activate-once-then-offline pattern for FIFA 20/22 is INFERRED and needs experiment E0. Origin was replaced by the EA App, and current FIFA 22 activation behaviour is UNKNOWN.

---

## 3. Tool inventory

| Tool | Versions | Mechanism | Open parts | Closed parts | Licence / reuse |
|---|---|---|---|---|---|
| **FIFA Live Editor (DLL)** – xAranaktu | 21, 22 (23–26 BLOCKED) | DLL injected by `Launcher.exe` (or any injector, per `wiki_FIFA-22-Live-Editor/Using-other-DLL-Injectors.md`); ImGui overlay (F11 menu); hooks the game's t3db database in RAM; embedded Lua 5.3 engine; can also "switch between lua states to access also in-game lua functions" (`FIFA-21-Live-Editor/lua/DOC.MD`; `le_config.json` keys `collect_lua_states`, `execute_in_all_states`) | Lua docs (`lua/DOC.MD` for 21/23/24; FIFA 22 docs in `wiki_FIFA-22-Live-Editor/LUA-API.md`), example scripts (`lua/scripts/*.lua`), Lua wrapper `lua/libs/live_editor.lua` (FIFA 21/23), LE v2 libs (FC 24 `lua/libs/v2/**`) | Core DLL, launcher, injector; binaries for 22 were Patreon-distributed (GitHub Releases empty) | Repo text is GPL-3 (FIFA 21: GPL-2). Scripts are reusable under GPL. The DLL licence is unclear because no source is published, so treat it as a closed runtime dependency. **Do not redistribute.** |
| **Career Mode Cheat Table / FIFA 20 "Live Editor"** – xAranaktu | 18, 19, 20, 21, 22 | Cheat Engine table: AOB scans (`AOB_PATTERNS` in `lua/consts.lua`), Auto-Assembler code caves at hooked game functions, pointer records, Lua GUI forms; in-memory t3db access (`lua/imports/GameDBManager.lua`) | Everything (XML + Lua + AA source readable) | Depends on Cheat Engine (repo shows no licence on GitHub page – UNKNOWN) | GPL-3 (20, 21, 22), MIT (19). Reusable with GPL obligations. |
| **Frosty Toolsuite** (Editor, Mod Manager, SDK) – CadeEvs | 17–20 only (`FrostySdk/ProfileVersion.cs`) | Frostbite asset/legacy-file editing and mod packaging; legacy DB viewer (`Plugins/Fifa/LegacyDatabasePlugin`) needs `*-meta.xml` | Full C# source | – | **CC BY-NC-ND 4.0**: no derivatives, so we can read it as reference but must not reuse or adapt its code |
| **FIFA Editor Tool / FIFA Mod Manager / FMT** – paulv2k4 | 20, 21, 22 (+ later) | Frostbite modding (legacy files, `.fifamod`) | releases repo only (`FMTDev/FMT.Releases`) | source not public (paulv2k4 has 0 public repos) | Closed; Patreon. Use as an external tool only. |
| **Revolution DB Master 22** (RDBM) – Rinaldo / Doctor+ | 21, 22 | Opens squad files (and per the LE wiki, career files) and edits t3db tables | – | closed (.NET 4.8) | "free and non-commercial use only" – DOCUMENTED (fifa-infinity) |
| **Creation Master 15/16, DB Master** – Rinaldo | 15, 16 (CM), DBM many | Edit `fifa_ng_db.db` / squads | – | closed | Free; reference only |
| **FIFASquadFileDownloader** – xAranaktu | FC 27 (format lineage) | Downloads squad files from EA servers (**online, do not use**). Contains squad-file container writer (`main.py: save_squads`: `FBCHUNKS` prefix header 1126 B, `SaveType_Squads\0` main header 48 B + CRC32, t3db `DB\0\x08` payload, `BNRY` chunk) and a decompressor (`unpack`, `other/legacy_unpack.py`) | Full Python | – | MIT. **The download path is online EA functionality and BLOCKED.** The container-format code is a useful *reference* (INFERRED applicability to FIFA 22). |
| **fifatables / dbmaster-cli** – Celtian | 11–23 | TypeScript table configs for DB Master text exports | Full | – | MIT (fifatables) – DOCUMENTED |
| **FIFALibrary (tokke001)** | various | VB.NET, model/texture formats; DB reading only | source (derlineUn/FIFALibrary220) | – | Licence not checked: UNKNOWN |

No open-source, permissively licensed, write-capable t3db (`.db` + `-meta.xml`) library was found. Readable references: Frosty `LegacyDbReader.cs` (NC-ND, reference only), the FIFA 22 CT `GameDBManager.lua` (GPL-3, in-memory), and the FC 24 LE `lua/libs/v2/imports/t3db/*.lua` (GPL-3, in-memory). A clean-room offline parser would have to be written by us. (INFERRED)

---

## 4. Live Editor and Cheat Table API surface relevant to match control

### 4.1 FIFA 22 Live Editor Lua API (closed DLL, documented surface)

Source: `wiki_FIFA-22-Live-Editor/LUA-API.md` (commit 2db636d), cross-checked against `FIFA-22-Live-Editor/changelog.txt`. Lua 5.3.4. Scripts run from F11 → Lua Engine → execute. Standard `io`/`os` libraries are usable: `lua/scripts/export_season_stats.lua` writes a CSV with `io.open` to `%USERPROFILE%\Desktop` (SOURCE VERIFIED).

| Function (verbatim) | Relevance | Constraint per wiki |
|---|---|---|
| `Log`, `MessageBox` | diagnostics | – |
| `IsInCM`, `GetSaveUID`, `GetCurrentDate`, `GetUserTeamID` | mode/state detection | GetSaveUID and GetUserTeamID are CM only |
| `GetCompetitionNameByID`, `GetCompetitionNameByObjID` | label stats | – |
| `GetTeamIdFromPlayerId`, `GetTeamName`, `GetPlayerName` | mapping | – |
| `SetPlayerSharpness`, `SetPlayerMorale`, `SetPlayerForm` | carry FM condition into FIFA | CM only, **user team only** |
| `SetPlayerFitness` | carry FM fitness | CM only |
| `ReloadDB`, `ReloadPlayersManager` | sync LE copy with game DB | – |
| `PlayerHasDevelopementPlan`, `PlayerSetValueInDevelopementPlan` | n/a | CM only |
| **`GetPlayersStats`**, **`GetPlayerStats(playerid)`** | season stats; keys `teamid, playerid, compobjid, avg, goals, yellow, red, app, assists, clean_sheets, motm*, two_yellow*, goals_conceded*, saves*` (*author: "not sure if data is correct"); `avg` must be divided by apps | the doc gives no constraint, but the data is CM season stats ("Game generate the stats only for players that play in the same competitions as you + european & international cups") |
| **`CreatePlayer(playerid, players_row_data)`**, `DeletePlayer(playerid, teamid=0)`, `PlayerExists` | create FM regens; player is created in Free Agents | no CM constraint listed |
| `TransferPlayer`, `LoanPlayer`, `ReleasePlayerFromTeam`, `TerminateLoan`, `DeletePresignedContract`, `IsPlayer*`, `AddPlayerTo*List`, `RemovePlayerFrom*`, `CreateOfferForPlayer` | move players between clubs | The wiki says CM only, **but** changelog v22.1.1.0 says "Transfer Player, Loan Player & Terminate Loan functions are now available also outside of Career Mode". This conflict is UNKNOWN (experiment E3). |
| **`GetDBTablesNames`, `GetDBTableFields(table)`, `GetDBTableRows(table)`, `InsertDBTableRow(table,row_data)`, `DeleteDBTableRow(table,row)`, `EditDBTableField(field)`** | generic CRUD on in-memory t3db; DBRow = `{field = {value, addr, ...}}`; `row.addr == "0"` means insert failed | Wiki home: "Edit Database (only tables that are part of the squadfile)". `Editing-Game-Database.md`: edits are temporary unless the table's `savegroup` is squads or career and the user then saves. |
| `PlayerCapture*`, `AddMinifaceToGenerate`/`GenerateMinifaces` (21) | cosmetic | CM only |
| `GetTransferBudget`/`Set…`, `GetWageBudget`/`Set…`, `AddTransferBan`, `RemoveTransferBan`, `IsTeamTransferBanned` | n/a | CM only |

**Absent in FIFA 22 LE** (SOURCE VERIFIED by absence in the docs and changelog): event callbacks of any kind, raw memory read/write, `GetPlugin`, any match/fixture/lineup-specific function, Kick-Off launch functions. The LE UI (not Lua) has Fixtures (favourite/disliked teams for **quick-simmed games only**, plus single-fixture match-fixing and date rescheduling) and Standings editors (`wiki_FIFA-22-Live-Editor/Fixtures.md`, `Standings.md`).

### 4.2 FIFA 21 Live Editor Lua API (comparison)

Source: `FIFA-21-Live-Editor/lua/DOC.MD`. The FIFA 22 list above **minus** `GetSaveUID`, `GetCompetitionNameBy*`, `GetPlayersStats`, `GetPlayerStats`, `CreatePlayer`, `DeletePlayer`, `PlayerExists`, `PlayerCapture*`, and the transfer-ban functions. It keeps `AddMinifaceToGenerate` and `GenerateMinifaces`. The wrapper `lua/libs/live_editor.lua` shows natives `cTransferPlayer`, `cLoanPlayer`, `DeleteDBTableRowByAddr`, `cIsPlayerTransferListed` and similar (SOURCE VERIFIED). It also ships `data/db_meta.xml`, the full FIFA 21 `fifa_ng_db` schema with 187 tables, used in Section 5.

### 4.3 Live Editor v2 events (FIFA 23 / FC 24+), context only: BLOCKED platforms

- `AddEventHandler(event_name, fn)`, `GetEventHandlers`, `RemoveEventHandler`, `ClearEventHandlersForEvent`. Events: `LEInitDoneEvent` and `pre__/post__CareerModeEvent`, where the latter wraps `EventsManager::HandleMessage(_this, event_id, event)` (`wiki_FC-24-Live-Editor/LUA-API-v2-Events.md`). Example: `FC-26-Live-Editor/lua/track_cm_events.lua`.
- Event IDs (`FC-24-Live-Editor/lua/libs/v2/imports/career_mode/enums.lua`): `ENUM_CM_EVENT_MSG_USER_MATCH_COMPLETED = 6`, `..._ABOUT_TO_ENTER_PREMATCH = 35`, `..._POST_MATCH_REPORTS_DISPLAYED = 37`, `..._TEAMS_READY_FOR_USER_MATCH = 39`, `..._ABOUT_TO_ENTER_A_MATCH = 40`, `..._ABOUT_TO_SIM_OVER_A_MATCH = 42`, `..._MATCH_RESTARTED = 165`, `..._INJURY = 178`, `..._NON_USER_MATCH_RESULT = 218`.
- `GetPlugin(ENUM_djb2<Name>_CLSS)` plus the `MEMORY` object (`ReadInt`, `ReadPointer`, `ReadMultilevelPointer`, `AOBScanGameModule`, …). Service names in `imports/services/enums.lua` include `MatchEventsDB`, `MatchStatesDB`, `MatchEventTrackerService`, `MatchJournalInterface`, `ManOfTheMatchService`, `GameRatingsService`, `KickOffService`, `KickoffMatchTypeService`, `TeamSheetService`, `MatchCreator`, `MatchManager`, `InitMatchDataEditorFactory`.
- **Why it matters:** these names show that the Frostbite FIFA runtime has match event and stats services, which makes it plausible that equivalents exist in FIFA 22 memory (INFERRED). Reaching them in FIFA 22 needs our own read-only memory research (experiment E9). Using the FC 24 tooling itself is **BLOCKED** (EAAC).

### 4.4 Cheat-table match scripts (FIFA 20 and FIFA 22): mechanisms traced in source

FIFA 22 file: `FIFA-22-CM-Cheat-Table/FIFA22.CETRAINER`. FIFA 20 file: `FIFA-20-Live-Editor/source/Live Editor.CETRAINER`. Entry tree extracted with `scripts/ctentries.py`; script bodies with `scripts/ctscript.py`.

| CT entry (verbatim path) | FIFA 20 | FIFA 22 | Mechanism (SOURCE VERIFIED in AA script) |
|---|---|---|---|
| `Scripts > Side Changer` (+ `Controller ID`) | yes | yes | Hooks the controller-assignment loop (FIFA 22: injection at `FIFA22.exe+3F496DD`, `mov rax,[rdi+rcx*8+118]`, sig `SideManipulator`). For the user's controller index it writes `intUserController` into `[rax+30]`; for slots `0x16`/`0x17` it writes `intCPUOneController`/`intCPUTwoController`. |
| `Side Changer > CPU vs CPU` | yes | yes | Sets `intUserController=-1, intCPUOneController=0, intCPUTwoController=1`, so neither side is human. Wiki `CPUvsCPU.md`: "spectate a match … __in career mode__". |
| `Side Changer > Control Home Team / Control Away Team` | – / yes | yes | Same hook, different values. |
| `Scripts > Gameplay` | yes | yes | (a) `MatchScore` hook stores per-team pointers `ptrHomeTeamScore`/`ptrAwayTeamScore` (rdx 1 = home, 0 = away). (b) `DisableSubstitutions` hook overrides the remaining-subs counter `[rsi+rbx+A75C]` per team (0 = none, 6 = unlimited). (c) `IngameStamina` hook. |
| `Gameplay > Home Team > Home - Goals scored` / `Away …` | yes | yes | Pointer record `[ptrHomeTeamScore]+0x226B0` (FIFA 22), i.e. a **live readable and writable score** |
| `Gameplay > Match Timer` (+ `Freeze timer`, `Reset timer`, `End current half`) | yes | yes | `MatchTimer` hook stores `ptrMatchTime` (rcx), clock at `[rcx+0x50]`. "End current half" writes `TIME=25000`. |
| `Gameplay > Unlimited Substitutions (USER)`; `Home/Away - Disable Substitutions (CPU)`; `… Unlimited Substitutions (CPU)` (FIFA 20) | yes | yes | see Gameplay (b) |
| `Gameplay > Home/Away - Injured players`, `NeverTired`, `Tired`, `5 stars skill moves` | yes | partial | in-match player-state cheats |
| `Match Settings > Half Length` | yes | yes | `MatchHalfLength` hook overrides `[r12+18E8]` (minutes) before kick-off |
| `Match Settings > Weather / Time Of Day / Change Stadium` | yes | yes (`MatchWeather`, `MatchTODDisplay`, `MatchTODReal`, `ChangeStadium`) | pre-match overrides |
| `Sim Match Settings > Max Cards / Max Injures` (FIFA 20: `Max_cards = 0`, `Max_injuries = 0`) | yes | yes | values from `simsettings.ini` (sim engine) |
| `Match Fixing` (FIFA 20) / hidden `MatchFixing` (FIFA 22) | yes | yes | Hooks `FootballCompEng_Win64_retail.dll` sim result (reads home/away team IDs at `+0x134`/`+0x138`). **Affects simulated matches only.** |
| `Fixture Edit` (FIFA 20) / Match Schedule Editor | yes | yes | reschedules dates |
| `Other > Freeze Lineup` (FIFA 22) | – | yes | Patches function `FreezeLineup` to `ret`, so the CPU cannot re-pick the lineup. Wiki `Editing-Teamsheets.md`: "new teamsheet cache service": edit the formation, activate, **save and reload the career**, then play. |
| AOB names useful for detection | – | `ScreenID`, `GameSettings`, `pModeManagers`, `DatabaseBasePtr`, `Calendar`, `SimMatchSettings` (`FIFA-22-CM-Cheat-Table/lua/consts.lua` `AOB_PATTERNS`) | `ScreenID` is a plausible full-time / post-match detector (INFERRED) |

Cheat Engine's own Lua (timers, memory reads) makes polling these pointers scriptable. This is INFERRED from CE's general capabilities and the CT's use of `readBytes`/`getAddressList`.

---

## 5. Database tables and fields (t3db `fifa_ng_db`)

Primary schema evidence:
- FIFA 21: `FIFA-21-Live-Editor/data/db_meta.xml`, whose header reads `database name="fifa_ng_db" … version="6"`. Every table has a `savegroups` attribute. (SOURCE VERIFIED)
- FIFA 22: partial schema with bit depths and ranges in `FIFA-22-CM-Cheat-Table/lua/consts.lua` (`DB_TABLES_META` / `DB_TABLES_META_MAP`, tables `teams, default_teamsheets, default_mentalities, players, teamplayerlinks, editedplayernames, career_calendar, career_users, career_playercontract, manager, leagueteamlinks, teamkits, competitionkits`). (SOURCE VERIFIED)
- FIFA 20: field names and bit lengths from CT records in `Live Editor.CETRAINER` and `source/lua/GUI/forms/teamseditorform/consts.lua`. (SOURCE VERIFIED)

### 5.1 Savegroups (FIFA 21, SOURCE VERIFIED; FIFA 22 INFERRED similar)

- `squads`: `default_mentalities, default_teamsheets, formations, editedplayernames, playerloans, playersuspensions, leagueteamlinks, leagues, manager, teamnationlinks, rivals, competition, …`
- `squads,players`: `players`. `squads,onlsquads`: `teams, teamplayerlinks, teamformationteamstylelinks`. `squads,fixtures`: `fixtures`.
- `careermode` (persisted in career save): `career_calendar, career_users, career_managerpref, career_managerinfo, career_playercontract, career_playermatchratinghistory, career_playerlastmatchhistory, career_teamofweek, career_competitionprogress, career_trophies, career_playerawards, career_youthplayers, persistent_events, …`
- `teamsheets`: `teamsheets, mentalities` (user-saved custom tactics). `customformations`: `customformations`. `settings`: `fifaGameSettings, fifaGameDefaults`.
- No savegroup (runtime/default only): `formationoffsets, matchscenarios, scenariosettings, MatchIntensity, cmeventhistory, career_regenplayerattributes, …`

### 5.2 Players and squads

- **`players`** (FIFA 22: 127 fields): `playerid` (19 bits, 0..500000, key), `firstnameid, lastnameid, commonnameid, playerjerseynameid, birthdate (DATE), nationality, height, weight, preferredfoot, preferredposition1..4 (0..31), overallrating, potential (1..99), modifier, internationalrep, skillmoves, weakfootabilitytypecode, attackingworkrate, defensiveworkrate, trait1, trait2`. Attributes: `acceleration, sprintspeed, agility, balance, jumping, stamina, strength, reactions, aggression, composure, interceptions, positioning, vision, ballcontrol, crossing, dribbling, finishing, freekickaccuracy, headingaccuracy, longpassing, shortpassing, marking, shotpower, longshots, standingtackle, slidingtackle, volleys, curve, penalties, gkdiving, gkhandling, gkkicking, gkreflexes, gkpositioning`. FIFA 22 card stats: `pacdiv, shohan, paskic, driref, defspe, phypos` (new against FIFA 21). Appearance fields: `headassetid, headclasscode, headtypecode, haircolorcode, skintonecode, bodytypecode, …`. (SOURCE VERIFIED)
- **`editedplayernames`**: `playerid, firstname, surname, commonname, playerjerseyname` (strings). This is how a created regen gets a name (wiki `CreatePlayer` example). (SOURCE VERIFIED / DOCUMENTED)
- **`teamplayerlinks`**: `artificialkey (key), teamid, playerid, position (0..33), jerseynumber (1..99), form (0..5), injury (0..35), yellows, reds, leaguegoals, leagueappearances, leaguegoalsprevmatch, leaguegoalsprevthreematches, istopscorer, isamongtopscorers, isamongtopscorersinteam`. (SOURCE VERIFIED 21/22)
- **`teams`**: identity plus set-piece takers `captainid, penaltytakerid, freekicktakerid, leftfreekicktakerid, rightfreekicktakerid, leftcornerkicktakerid, rightcornerkicktakerid, longkicktakerid`, `favoriteteamsheetid`, ratings `overallrating/attackrating/midfieldrating/defenserating` and `matchday*rating`, and **team tactics** fields (5.4).

### 5.3 Lineups and formations

- **`default_teamsheets`** (squads): `teamid`, `playerid0..playerid51` (slots 0–10 = XI in formation-position order, then subs and reserves), `captainid`, set-piece taker IDs, `customsub0in/out … customsub2in/out` (planned subs). Values -1..500000. (SOURCE VERIFIED 21/22)
- **`teamsheets`** (savegroup teamsheets): the same plus `teamsheetid`, `teamsheetname`, `profileid`, `sourceformationid`, `isfavourite`. (SOURCE VERIFIED 21)
- **`default_mentalities`** (squads; up to 5 per team, from 1 = Ultra Defensive to 5 = Ultra Attacking, 3 = Balanced per `wiki_FIFA-22-Live-Editor/Editing-Team-Formation.md`): `mentalityid, teamid, sourceformationid, formationaudioid, formationfullnameid`, `position0..10` (position IDs per slot), `offset0x..offset10y` (REAL pitch coordinates), `playerid0..10`, `playerinstruction0_1..10_1` (30-bit) and `playerinstruction0_2..10_2` (20-bit) bitfields, plus team tactic fields (5.4). (SOURCE VERIFIED 21/22)
- **`mentalities`** (teamsheets savegroup): as above plus `teamsheetid`, `profileid`. **`formations` / `customformations`**: `formationid, formationname, position0..10, offset*, playerinstruction*, defenders, midfielders, attackers, offensiverating, relativeformationid`. **`formationoffsets`**. (SOURCE VERIFIED 21)
- Position IDs (0=GK, 1=SW, 2=RWB, 3=RB, 4=RCB, 5=CB, 6=LCB, 7=LB, 8=LWB, 9=RDM, 10=CDM, 11=LDM, 12=RM, 13=RCM, 14=CM, 15=LCM, 16=LM, 17=RAM, 18=CAM, 19=LAM, 20=RF, 21=CF, 22=LF, 23=RW, 24=RS, 25=ST, 26=LS, 27=LW) come from `get_pos_name` in `FIFA-22-Live-Editor/lua/scripts/export_season_stats.lua`. (SOURCE VERIFIED)

### 5.4 Team tactics fields (in `teams`, `default_mentalities`, `mentalities`)

| Field | FIFA 20 | FIFA 21 | FIFA 22 |
|---|---|---|---|
| `defensivestyle` | 3 bits | 3 bits, 0..4 | 3 bits, 0..4 |
| `defensivewidth`, `defensivedepth`, `offensivewidth` | 4 bits | 4 bits, **0..9** | 7 bits, **1..100** |
| `offensivestyle` | 2 bits | 2 bits, 0..3 | 2 bits, 0..3 (role in 22 UNKNOWN) |
| `buildupplay` | absent | absent | **2 bits, 0..3 (new)** |
| `chancecreation` | absent | absent | **2 bits, 0..3 (new)** |
| `playersinboxcross` | 4 bits | 0..9 | 0..9 |
| `playersinboxcorner`, `playersinboxfk` | 3 bits | 0..4 | 0..4 |
| `playerinstructionN_1` / `_2` | present (teamseditorform consts) | bitfields | bitfields |

Sources: FIFA 21 `db_meta.xml`, FIFA 22 CT `consts.lua`, FIFA 20 CT `BitLength`. All SOURCE VERIFIED. The mapping of enum values to UI labels (e.g. defensivestyle 0 = Balanced?) and the player-instruction bit layout are **UNKNOWN**: no labels were found in any repo. See experiment E2.

Legacy table `customteamstyles` (FIFA 21): `busbuildupspeed, buspassing, buspositioning, busdribbling, ccpassing, cccrossing, ccshooting, ccpositioning, defmentality, defaggression, defteamwidth, defdefenderline`. These are the FIFA 15–18-era "team style slider" fields, still present in the FIFA 21 schema (SOURCE VERIFIED). Whether FIFA 21/22 use them is UNKNOWN.

### 5.5 Match settings, gameplay sliders, difficulty

**`fifaGameSettings`** (savegroup `settings`; FIFA 21, SOURCE VERIFIED) has:
- Match settings: `halflength`, `difficultylevel`, `difficultylevelcareer`, `gamespeed`, `injuries`, `offsides`, `bookings`, `handball`, `extratime`, `penalties`, `numofsubs`, `subsonbench`.
- Controller switching: `homeautoswitch`, `awayautoswitch`.
- Gameplay sliders: `gcsprintspeeduser/cpu`, `gcaccelerationuser/cpu`, `gcshoterror*`, `gcpasserror*`, `gcshotspeed*`, `gcpassspeed*`, `gcinjuryfrequency*`, `gcinjuryseverity*`, `gcgkability*`, `gcposmarking*`, `gcposrunfrequency*`, `gcposdefensivelineheight*`, `gcposlinelength*`, `gcposlinewidth*`, `gcposfullbackpositioning*`, `gcpowerbaruser`, `gctraperror*`.

These match the slider list on EA's FIFA 22 PC settings page (Half Length 4–20 min, Beginner–Legendary, Slow/Normal/Fast, user and CPU sliders 0–100; ea.com/able/resources/fifa/fifa-22/pc/game-settings – DOCUMENTED). **"Legacy defending"** is not a named field: UNKNOWN, possibly a `genericsettingN` or a profile setting.

Career: `career_managerpref` has `matchdifficulty`, `halflength`, `boardaidifficulty`, `clubformation1..5` (FIFA 20 CT records, SOURCE VERIFIED). Kick-Off scenarios: `matchscenarios` (`homeid, awayid, halflength, stadiumid, timeofday, userside, gametype, …`) and `scenariosettings` (`homescore, awayscore, startminute, starthalf, …`) are "Match Scenarios" data, and whether they can launch a custom Kick-Off is UNKNOWN.

### 5.6 Match and fixture persistence (career)

| Table | Fields | Use for us |
|---|---|---|
| **`career_playermatchratinghistory`** (careermode) | `artificialkey, playerid, rating (-1..100), minsplayed (-1..140), date (YYYYMMDD 20080101..20601231), position (0..31)` | per-match player ratings and minutes, so subs can be derived (INFERRED) |
| **`career_playerlastmatchhistory`** (careermode) | `artificialkey, teamid, playerid, minsplayed (0..150), playeroverall, playerfact (-1..15), position` | last-match snapshot (playerfact meaning UNKNOWN) |
| `career_teamofweek` | `playerid, matchrating, month, weekswon` | – |
| `career_calendar` | `currdate, startdate, enddate, …` | date anchor |
| `fixtures` (squads,fixtures) | `fixtureid, hometeamid, awayteamid, competitionid, fixturedate, fixturetime, stadiumid, homeleagueid, awayleagueid, *form, *leaguepos, *matchesplayed` | whether CM uses this table or FootballCompEng internal objects for its calendar is UNKNOWN |
| `persistent_events`, `cmeventhistory`, `cmteameventhistory` | `eventid, eventdate, player1id, team1id, team2id, compobjid, miscvalue` / `teamid, eventid, playerid, daysfromstart` | event log semantics UNKNOWN; could hold match-related CM events |
| `playersuspensions` (squads) | `playerid, teamid, games, enddate` | card consequences |
| `teamplayerlinks.yellows/reds/injury/leaguegoals*` | squad-level counters | coarse deltas |
| In-memory season stats via `GetPlayersStats()` (FIFA 22 LE) | goals, assists, yellow, red, two_yellow, app, avg, motm, clean_sheets, saves, goals_conceded per (player, compobjid) | **main per-match delta source** |

No table holding per-match goal minutes, assist pairings, shots, passes or possession was found in the FIFA 21 schema. That gap is SOURCE VERIFIED by absence in the 187 table names, which means such data, if it exists at all, lives only in runtime memory or in the post-match UI (INFERRED).

---

## 6. Capability matrix (FIFA 20 vs FIFA 22)

| # | Capability | FIFA 20 (CE "Live Editor" table) | FIFA 22 (LE DLL + CM Cheat Table) |
|---|---|---|---|
| 1 | Create or modify players | **Modify:** SOURCE VERIFIED. The CT `FIFA Database Tables` script hooks the DB read function and edits `players`/`teamplayerlinks` records in RAM (wiki `desc-FIFA-Database-Tables.md`: "Make game to access database for the table you want to edit"). **Create new IDs:** the CT offers "Generate players with custom ID" (youth academy, DOCUMENTED); arbitrary regen creation is UNKNOWN. Offline squad-file editing via Frosty is read-only and via FET is DOCUMENTED. | **Modify:** SOURCE VERIFIED (`EditDBTableField`, CT `GameDBManager:set_table_record_field_value`). **Create:** `CreatePlayer(playerid, row)` + `InsertDBTableRow("editedplayernames", …)` is DOCUMENTED (wiki example, changelog v22.1.1.0). IDs must fit 0..500000 (SOURCE VERIFIED). Behaviour in Kick-Off vs CM is UNKNOWN (E3). |
| 2 | Configure both teams programmatically | INFERRED feasible via CT DB pointers plus the GUI Teams Editor (`source/lua/GUI/forms/teamseditorform`); no batch API, only manual GUI or CE-Lua scripting against record pointers | `teamplayerlinks` insert/delete via DB CRUD (SOURCE VERIFIED API); `TransferPlayer` (CM per wiki, also outside CM per changelog: conflict, UNKNOWN); `teams` fields editable. DOCUMENTED. |
| 3 | Set starting lineups | `default_teamsheets` / `teamsheets` records exposed in the CT (SOURCE VERIFIED). Effect at kick-off is UNKNOWN. | `default_teamsheets.playerid0..51` editable (SOURCE VERIFIED). For CPU teams in CM: "Roster changes will be temporary" unless the CT `Freeze Lineup` is used plus save and reload (DOCUMENTED). User-team lineup through `teamsheets`/`favoriteteamsheetid` is UNKNOWN (E5). |
| 4 | Formations and tactical instructions | Team Editor formation, mentality and player instructions (`teamseditorform/consts.lua` lists `playerinstruction*`, `position*`, `offensivestyle`, `defensivewidth`…) – SOURCE VERIFIED. Enum semantics UNKNOWN. | LE Formation Editor (wiki: change formation, tactic, mentalities 1–5, positions, offsets, player instructions, XI and bench) – DOCUMENTED. Fields incl. `buildupplay`, `chancecreation`, 1..100 width/depth – SOURCE VERIFIED. Enum and PI bit semantics UNKNOWN (E2). |
| 5 | Launch an actual match | Manual: user presses Play Match (CM) or Kick-Off. Programmatic launch: UNKNOWN. | Same. Programmatic launch: UNKNOWN. Possible lead: LE "switch lua states to access in-game lua functions" (DOCUMENTED) plus legacy `data/fifarna/lua` (`FIFA-21-Live-Editor/data/legacy_structure.txt`) → E13. |
| 6 | Manual control of own team | Native game behaviour. INFERRED trivially yes. | Native. INFERRED yes. |
| 7 | CPU vs CPU | CT `Side Changer > CPU vs CPU`: SOURCE VERIFIED script; wiki says "in career mode". Kick-Off vanilla spectate: UNKNOWN. | Same CT script (`SideManipulator` hook): SOURCE VERIFIED. Kick-Off vanilla: UNKNOWN (only an anecdotal forum report for an unnamed FIFA). CPU subs can be disabled per side (SOURCE VERIFIED). |
| 8 | Capture goals, assists, subs, cards | Live score pointer (`Home/Away - Goals scored`) – SOURCE VERIFIED. Per-player events: UNKNOWN. Career DB (`teamplayerlinks.leaguegoals/yellows/reds`, `career_playermatchratinghistory` INFERRED present) → coarse deltas, INFERRED. | Live score `[ptrHomeTeamScore]+0x226B0` – SOURCE VERIFIED. **CM:** `GetPlayersStats()` before/after delta → goals, assists, yellow, red per player (INFERRED technique on a DOCUMENTED API). Subs from `minsplayed` deltas – INFERRED. Goal minutes and assist-goal pairing: UNKNOWN. Injuries: UNKNOWN. **Kick-Off:** UNKNOWN. |
| 9 | Individual player stats (ratings, shots, passes) | Ratings via career rating table – INFERRED (FIFA 20 schema not inspected). Shots and passes: UNKNOWN. | Ratings: `career_playermatchratinghistory.rating` (schema SOURCE VERIFIED for 21, INFERRED for 22) and `GetPlayersStats().avg` delta. Shots, passes, tackles: UNKNOWN (memory or UI only). |
| 10 | Team statistics | Score only (SOURCE VERIFIED). Possession, shots etc.: UNKNOWN. | Score and the sum of player goals. Possession, shots, corners, fouls: UNKNOWN (E9). |
| 11 | Detect full-time and export | Timer pointer `ptrMatchTime` (SOURCE VERIFIED) plus CE Lua polling and file write (INFERRED). | Candidates: timer pointer (SOURCE VERIFIED); `ScreenID` AOB (SOURCE VERIFIED exists, semantics INFERRED); new `career_playermatchratinghistory` rows with `date == currdate` (INFERRED); export via LE Lua `io` (SOURCE VERIFIED that the export script writes files). No push event: LE v2 events are BLOCKED. |

---

## 7. Tactical system per version

- **FIFA 15–18:** team-style sliders such as build-up speed/passing/positioning, chance-creation passing/crossing/shooting/positioning and defence pressure/aggression/width/line. These are represented by the `customteamstyles` table fields still present in the FIFA 21 schema (SOURCE VERIFIED fields; era attribution INFERRED).
- **FIFA 19–21 ("Dynamic Tactics" era; FIFA 20 and 21 verified in schema):**
  - Per team, up to 5 game plans (mentalities: Ultra Defensive → Ultra Attacking).
  - Each game plan carries a formation (`sourceformationid`, positions, offsets), defensive style (5 values, `defensivestyle` 0..4), width and depth (0..9, shown as 1–10 in the UI: INFERRED), offensive style (`offensivestyle` 0..3), offensive width (0..9), players in box (0..9), corners and free kicks (0..4).
  - Player instructions per slot are packed into two integers (`playerinstructionN_1/_2`).
  - Source: `db_meta.xml` (21) and CT bit lengths (20).
- **FIFA 22:** same mentality structure.
  - Offence is split into **`buildupplay` (0..3)** and **`chancecreation` (0..3)**. Width and depth go to **1..100**, consistent with FIFA 22's UI sliders. `offensivestyle` is still present (function UNKNOWN).
  - The CM "teamsheet cache service" means lineup and formation edits need the CT `Freeze Lineup` plus save and reload (DOCUMENTED, `wiki_FIFA-22-CM-Cheat-Table/Editing-Teamsheets.md`).
  - CPU teams carry one mentality by default; "4 more mentalities are generated when the user team face the CPU team" (DOCUMENTED, LE wiki).
- **Mapping FM tactics into FIFA:** FM tactics are far richer, so the bridge needs a lossy mapping: FM mentality → mentality slot; pressing → defensivestyle; line of engagement/defensive line → depth; width → width; passing directness/tempo → buildupplay/chancecreation; player roles → position plus PIs. The design is INFERRED. The value semantics must be pinned down by E2 first.

---

## 8. Recommended match-execution mode

**Recommendation: FIFA 22, a disposable "bridge" Manager Career as the primary mode, with Kick-Off as the fallback.**

Reasoning:
1. **Stats capture decides it.** In FIFA 20–22 the only documented programmatic stat sources are career-mode ones: `GetPlayersStats` / `GetPlayerStats` and the `career_*` tables. Kick-Off has no documented stat persistence or API, so every Kick-Off result would need memory research or screen capture. (DOCUMENTED / SOURCE VERIFIED / INFERRED)
2. **Condition sync.** Career mode exposes `SetPlayerFitness/Form/Morale/Sharpness` (user team only for three of them), so FM condition can be mirrored into FIFA. (DOCUMENTED)
3. **The opponent problem.** The FIFA career calendar decides the opponent, and the LE can only reschedule dates and fix sim results (DOCUMENTED). Proposed workaround: a **proxy-opponent technique**. Before each FM fixture, overwrite the squad, names, tactics and teamsheet of FIFA's next scheduled opponent with the FM opponent's data. Kits and badge would stay cosmetic mismatches. This is INFERRED and needs experiment E12, including side effects on FIFA's league state, which does not matter in a disposable sandbox.
4. **Kick-Off fallback** for (a) cup ties needing extra time or penalties, since `fifaGameSettings.extratime/penalties` exist (SOURCE VERIFIED fields; behaviour UNKNOWN), and (b) the case where E12 fails. Here, capture would be score via the CT pointer plus the post-match screen (manual or OCR), until E9 finds memory stats structures.
5. **Why not FIFA 23+:** EAAC, and the LE's fake-launcher approach is BLOCKED. **Why not FIFA 20 as primary:** it has no in-process Lua DB API, no `CreatePlayer` and no `GetPlayersStats`; everything would be CE pointer scripting. It remains a fully open (GPL) reference implementation, though.
6. **Caveats:** the FIFA 22 LE DLL is closed and was distributed via Patreon (GitHub releases are empty), so legal access to v22.1.1.9 must be confirmed (UNKNOWN). The FIFA 22 PC build is last-gen (DOCUMENTED). Denuvo activation needs a one-time online activation before offline play (INFERRED from the FIFA 23 LE wiki). Running the LE DLL and CE together has not been verified (UNKNOWN).

---

## 9. Local Windows experiments (step-by-step; read-only first, disposable copies)

Ground rules for every experiment:
- Use only the user's legitimately activated install.
- Make no change to game binaries, and never use fake launchers or anti-cheat or DRM tools.
- Work offline after activation, with Origin or EA App in offline mode.
- Never enter online modes while tools are loaded.
- Back up `Documents\FIFA 22\settings\` (squads, careers, profile) and `Documents\FIFA 20\settings\` to a dated folder first, and work on **copies** of saves (save career to a new slot before editing).
- Record `FIFA22.exe` file version and title update for every run.

| ID | Goal (unknown resolved) | Steps | Pass criterion |
|---|---|---|---|
| **E0** | Offline launch and protection status (no bypass) | 1) Launch FIFA 22 online once via its normal launcher. 2) Quit, switch the client to offline mode, relaunch. 3) Note any activation prompt. Repeat for FIFA 20. | The game reaches the main menu offline. Record exact behaviour; if an online check is mandatory, document it and stop. |
| **E1** | FIFA 22 schema dump (read-only) | 1) Start the LE (Launcher, then game), main menu. 2) Lua: loop `GetDBTablesNames()` and `GetDBTableFields(t)`, write CSV via `io.open` to a scratch folder. 3) Repeat inside a CM save. Diff against FIFA 21 `db_meta.xml`. | Full FIFA 22 table and field list incl. `career_playermatchratinghistory` present (or not) |
| **E2** | Tactic enum and PI semantics | 1) Kick-Off → Customise → Edit Teams → user custom tactics. 2) Dump `teamsheets`/`mentalities` (and `default_mentalities` for that team). 3) Change ONE UI option (e.g. Defensive Style → "Drop Back"), save, re-dump, diff. 4) Repeat for every option and every player-instruction toggle per position. | Value-to-label table for `defensivestyle`, `buildupplay`, `chancecreation`, `offensivestyle`, widths; bit map for `playerinstructionN_1/_2` |
| **E3** | Regen creation and squad membership in Kick-Off vs CM | 1) Kick-Off context: `ReloadDB()`, `CreatePlayer(0, {...})`, insert `editedplayernames`; attempt `TransferPlayer`; else `InsertDBTableRow("teamplayerlinks", …)` with unique `artificialkey`. 2) Open Kick-Off team select and check the squad. 3) Save the squad file to a new slot; reload the game; verify persistence. 4) Repeat in a CM copy. | The created player appears and plays; documented behaviour of `TransferPlayer` outside CM resolves the wiki/changelog conflict |
| **E4** | CPU-team lineup and formation control | 1) Edit the opponent's `default_teamsheets` XI order and `default_mentalities` formation. 2) Kick-Off: go to the pre-match lineup screen and compare. 3) CM: same, with CT `Freeze Lineup` on, save, reload, Play Match. | Pre-match lineup equals the injected one in both modes (or document divergence) |
| **E5** | User-team lineup programmatically | Edit the user team's `teamsheets` row (favourite) and `teams.favoriteteamsheetid`; open the squad screen before kick-off. | The user XI and tactics match the injected ones without manual UI work |
| **E6** | CPU vs CPU | 1) Kick-Off, vanilla: leave all controllers in the middle and try to start; then in-match pause → change sides → middle. 2) If that fails: CT `Side Changer`, set Controller ID, then `CPU vs CPU` in Kick-Off. 3) Same in CM. | Both teams AI-controlled for 90 minutes, no human indicator |
| **E7** | Per-match stats via deltas (CM) | 1) Before the match: dump `GetPlayersStats()`, `career_playermatchratinghistory`, `career_playerlastmatchhistory`, `teamplayerlinks` (both teams). 2) Play a short match (Half Length 4) with forced events (sliders: injury frequency high; bookings on). 3) After the post-match screen: re-dump. 4) Compare with the in-game Match Facts / Player Ratings screens (photograph them). | Goals, assists, yellow/red, minutes and rating per player match the UI; document the AI-team coverage gap |
| **E8** | Full-time detection | While playing, poll every 1 s: (a) CT `ptrMatchTime` clock, (b) CT `ScreenID` value, (c) row count of `career_playermatchratinghistory`. Log timestamps at kick-off, HT, FT and the post-match screen. | One signal reliably flips exactly once at FT |
| **E9** | Team stats and event structures in memory (read-only research) | 1) With CE attached (no writes), use the CT `Gameplay` hook to get `ptrHomeTeamScore`. 2) Snapshot the memory region around the team struct before and after a shot, a corner, a foul and a sub; diff for incrementing counters; validate against the Match Facts screen. 3) Document offsets only; no hooks of our own yet. | Offsets for shots, on-target, corners, fouls, possession and subs used, or a conclusion that they are not found |
| **E10** | Injury capture | Force injuries (sliders); before and after: `teamplayerlinks.injury`, LE Players Editor injury display, `playersuspensions`, and CM injury reports. | An identified source for injury type and duration |
| **E11** | Match settings control | Dump `fifaGameSettings`; change Half Length, difficulty, speed, subs, extra time and penalties in the UI; diff. Then test writing `halflength` via `EditDBTableField` before Kick-Off. | A writable settings path, or confirmation that UI is required |
| **E12** | Proxy-opponent technique (CM) | In a disposable career: identify the next fixture's opponent via the LE Teams Editor → Fixtures; replace its `teamplayerlinks`, players (or create), `editedplayernames`, `teams.teamname` (string field in the FIFA 21 schema) and tactics; Freeze Lineup; save, reload, play. Then check the league table and next fixtures for corruption. | The match is played with the FM opponent data and the career remains loadable |
| **E13** | Programmatic kick-off (exploratory, read-only) | Enable LE `collect_lua_states`; in each game Lua state, list `_G` keys to a file; search for kick-off, match-setup or screen-navigation functions. Do not call unknown functions until they are reviewed. | A candidate API list, or "none" |
| **E14** | FIFA 20 parity | Repeat E2, E4, E6, E7 (timer and score pointers) with the FIFA 20 CE table. | Comparison table |
| **E15** | Offline file export path | Save the career after a match; open a **copy** of the career file in RDBM 22 (read-only); check whether `career_playermatchratinghistory` and others are visible. Optionally parse the container header per `FIFASquadFileDownloader/main.py` layout (clean-room, our own code). | Stats readable without the game running |

---

## 10. Limitations, risks and licence notes

- **BLOCKED:**
  - FIFA 23 / FC 24–26 Live Editor workflows, because they replace the EA AntiCheat launcher.
  - Any Denuvo bypass.
  - `FIFASquadFileDownloader`'s EA-server download path, because it is online EA functionality.
  - Online modes with tools loaded.
- **Closed dependencies:**
  - The Live Editor DLLs (21/22), FIFA Editor Tool, RDBM and Creation Master. We can depend on them at runtime only, cannot redistribute them, and their behaviour is not inspectable.
  - The FIFA 21 LE repo contains executable binaries (`FIFALiveEditor.DLL`, `Launcher.exe`, `Injector/Injector.exe`). These were downloaded, not executed, and should not be executed from the scratch copy.
- **Reusable source:**
  - Aranaktu cheat tables and LE Lua scripts: GPL-3.0 (FIFA 19: MIT). Any derived bridge script that is distributed inherits GPL obligations.
  - `FIFASquadFileDownloader`: MIT.
  - Frosty: CC BY-NC-ND, so reference only, no derivative code.
  - EA data files (e.g. `db_meta.xml` shipped in the FIFA 21 LE repo) are EA content and should not be redistributed by us.
- **Version fragility:** CT scripts use AOB signatures and hard-coded struct offsets (e.g. `+0x226B0`, `+0xA75C`, `+0x18E8`). Any game title update can break them, so the exact FIFA 22 version must be pinned.
- **Save integrity:** the LE wiki warns that duplicate primary keys and edits on match day can corrupt saves. Always use copies.

---

## 11. Evidence ledger

| # | Claim | Class | Source |
|---|---|---|---|
| 1 | A FIFA 20 Live Editor exists and is a Cheat Engine table ("previously known as Career Mode Cheat Table") | CONFIRMED / SOURCE VERIFIED | `FIFA-20-Live-Editor/README.md`; `source/Live Editor.CETRAINER` (plain XML) |
| 2 | The FIFA 21 LE is a closed DLL plus launcher/injector with a Lua API | CONFIRMED | `FIFA-21-Live-Editor/FIFALiveEditor.DLL`, `Launcher.exe`, `Injector/`, `lua/DOC.MD` |
| 3 | The FIFA 22 LE repo holds scripts and docs only; releases come via Patreon | CONFIRMED / DOCUMENTED | repo tree; `wiki_FIFA-22-Live-Editor/Getting-Started.md` |
| 4 | LE repos are GPL-3 (FIFA 21: GPL-2); CTs GPL-3; FIFA 19 CT MIT | CONFIRMED | LICENSE files |
| 5 | Frosty licence is CC BY-NC-ND 4.0; profiles only up to FIFA 20 | SOURCE VERIFIED | `FrostyToolsuite/README.md`; `FrostySdk/ProfileVersion.cs` |
| 6 | Frosty legacy DB plugin is a reader that needs `-meta.xml` | SOURCE VERIFIED | `Plugins/Fifa/LegacyDatabasePlugin/LegacyDbEditor.cs` L101-116, `IO/LegacyDbReader.cs` |
| 7 | "Frosty doesn't support FIFA 22" | DOCUMENTED | `wiki_FIFA-22-Live-Editor/Frequently-asked-questions.md` |
| 8 | FIFA 22 LE Lua function list (Section 4.1) | DOCUMENTED | `wiki_FIFA-22-Live-Editor/LUA-API.md` |
| 9 | `GetPlayersStats` / `GetPlayerStats` added in v22.1.0.9; `CreatePlayer` / `DeletePlayer` / `PlayerExists` in v22.1.1.0 | DOCUMENTED | `FIFA-22-Live-Editor/changelog.txt` |
| 10 | Transfer functions "available also outside of Career Mode" vs wiki "only in Career Mode" | DOCUMENTED (conflict) → UNKNOWN | changelog v22.1.1.0 vs `LUA-API.md` constraints |
| 11 | LE Lua can write files (io) | SOURCE VERIFIED | `FIFA-22-Live-Editor/lua/scripts/export_season_stats.lua` |
| 12 | The FIFA 22 LE has no event callbacks or memory API | SOURCE VERIFIED (by absence) | `LUA-API.md`, changelog |
| 13 | LE v2 events `AddEventHandler`, `pre__/post__CareerModeEvent`, `LEInitDoneEvent` | SOURCE VERIFIED / DOCUMENTED | `FC-24-Live-Editor/lua/scripts/*.lua`, `lua/libs/v2/tests/event_handlers_test.lua`, `wiki_FC-24-Live-Editor/LUA-API-v2-Events.md` |
| 14 | CM event IDs incl. `USER_MATCH_COMPLETED=6`, `INJURY=178` | SOURCE VERIFIED (FC 24) | `FC-24-Live-Editor/lua/libs/v2/imports/career_mode/enums.lua` |
| 15 | Runtime services `MatchEventsDB`, `MatchStatesDB`, `GameRatingsService`, `KickOffService`, `TeamSheetService` exist (FC 24) | SOURCE VERIFIED (names only) | `FC-24-Live-Editor/lua/libs/v2/imports/services/enums.lua` |
| 16 | Similar services exist in FIFA 22 memory | INFERRED | from 15 |
| 17 | FIFA 23+ LE uses a fake EAAC launcher | DOCUMENTED → BLOCKED | `wiki_FIFA-23-Live-Editor/Getting-Started.md`, `wiki_FC-24-Live-Editor/Getting-Started.md` |
| 18 | EA AntiCheat debuted with FIFA 23 | DOCUMENTED | gigazine.net/gsc_news/en/20220914-fifa-23-kernel-mode-protection; esports.gg; hothardware.com |
| 19 | FIFA 15 was the first Denuvo game | DOCUMENTED | en.wikipedia.org/wiki/Denuvo |
| 20 | FIFA 20/21/22 PC use Denuvo | DOCUMENTED (press crack reports) | rutab.net (FIFA 20, FIFA 21); en.gamegpu.com (FIFA 22) |
| 21 | FIFA 22 PC = PS4/XB1 feature set, no HyperMotion | DOCUMENTED | pcgamer.com/uk/fifa-22s-pc-edition-will-miss-out-on-next-gen-features/; kitguru.net |
| 22 | Activate once online, then offline play works under Denuvo | DOCUMENTED (FIFA 23), INFERRED (FIFA 20/22) | `wiki_FIFA-23-Live-Editor/Game-Backup.md` L39-47 |
| 23 | CT CPU vs CPU via controller-assignment hook | SOURCE VERIFIED | `FIFA22.CETRAINER` entries `Side Changer`, `CPU vs CPU` (injection `FIFA22.exe+3F496DD`); same entries in FIFA 20 CETRAINER |
| 24 | CPU vs CPU described for career mode | DOCUMENTED | `wiki_FIFA-20-Live-Editor/CPUvsCPU.md`, `wiki_FIFA-22-CM-Cheat-Table/CPUvsCPU.md` |
| 25 | Vanilla Kick-Off CPU vs CPU by leaving controllers in the middle | UNKNOWN (anecdotal, version unnamed) | forums.penny-arcade.com/discussion/168911 |
| 26 | Live score pointer `[ptrHomeTeamScore]+0x226B0` | SOURCE VERIFIED | `FIFA22.CETRAINER` `Gameplay` script + `Home - Goals scored` record |
| 27 | Match clock pointer `ptrMatchTime`, `[rcx+0x50]` | SOURCE VERIFIED | `FIFA22.CETRAINER` `Match Timer` |
| 28 | Substitution limits overridable per side (`[rsi+rbx+A75C]`) | SOURCE VERIFIED | `FIFA22.CETRAINER` `Gameplay` (DisableSubstitutions) |
| 29 | Half length overridable pre-match (`[r12+18E8]`) | SOURCE VERIFIED | `FIFA22.CETRAINER` `Half Length` |
| 30 | Match-fixing only affects simulated matches (FootballCompEng hook) | SOURCE VERIFIED / DOCUMENTED | `FIFA22.CETRAINER` `MatchFixing`; `wiki_FIFA-22-Live-Editor/Fixtures.md` ("WORKS ONLY FOR QUICK SIMMED GAMES") |
| 31 | FIFA 22 CM lineup edits need Freeze Lineup plus save and reload | DOCUMENTED / SOURCE VERIFIED | `wiki_FIFA-22-CM-Cheat-Table/Editing-Teamsheets.md`; `FIFA22.CETRAINER` `Freeze Lineup` |
| 32 | CPU roster changes are temporary; formation and tactic changes persist | DOCUMENTED | `wiki_FIFA-22-Live-Editor/Editing-Team-Formation.md` |
| 33 | 1–5 mentalities; Balanced = 3; CPU has 1 by default | DOCUMENTED | same |
| 34 | FIFA 21 schema: 187 tables with savegroups (Section 5.1) | SOURCE VERIFIED | `FIFA-21-Live-Editor/data/db_meta.xml` |
| 35 | `career_playermatchratinghistory(playerid, rating, minsplayed, date, position)` in the careermode savegroup | SOURCE VERIFIED (FIFA 21); INFERRED (FIFA 20/22) | `db_meta.xml` |
| 36 | No per-match event or team-stats table in the schema | SOURCE VERIFIED (by absence, FIFA 21) | `db_meta.xml` table list |
| 37 | FIFA 22 tactic fields `buildupplay`, `chancecreation` (0..3); width/depth 1..100 | SOURCE VERIFIED | `FIFA-22-CM-Cheat-Table/lua/consts.lua` `DB_TABLES_META` (teams, default_mentalities) |
| 38 | FIFA 21 width/depth 0..9; no buildupplay/chancecreation | SOURCE VERIFIED | `db_meta.xml` |
| 39 | FIFA 20 width/depth 4-bit; no buildupplay | SOURCE VERIFIED | FIFA 20 CETRAINER `BitLength`; grep shows no `buildupplay` in the FIFA 20 repo |
| 40 | Tactic enum labels and PI bit layout | UNKNOWN | none found (grep for labels in all repos returned nothing) |
| 41 | playerid range 0..500000 (19 bits) | SOURCE VERIFIED | FIFA 21 `db_meta.xml`; FIFA 22 CT `consts.lua` |
| 42 | Position ID table 0..27 | SOURCE VERIFIED | `FIFA-22-Live-Editor/lua/scripts/export_season_stats.lua` `get_pos_name` |
| 43 | `fifaGameSettings` holds half length, difficulty, speed, injuries, offsides, bookings, extratime, penalties, numofsubs, gc* sliders | SOURCE VERIFIED (FIFA 21) | `db_meta.xml` |
| 44 | FIFA 22 UI settings: Half Length 4–20, Beginner–Legendary, user and CPU sliders 0–100 | DOCUMENTED | ea.com/able/resources/fifa/fifa-22/pc/game-settings |
| 45 | "Legacy defending" storage | UNKNOWN | – |
| 46 | In-memory t3db table struct offsets (FIFA 22) and read/write helpers | SOURCE VERIFIED | `FIFA-22-CM-Cheat-Table/lua/consts.lua` `DB_TABLE_STRUCT_OFFSETS`; `lua/imports/GameDBManager.lua` |
| 47 | Squad file container layout (FBCHUNKS / SaveType_Squads / CRC32 / DB / BNRY) | SOURCE VERIFIED (FC 27); INFERRED (FIFA 22) | `FIFASquadFileDownloader/main.py` `save_squads`, `unpack` |
| 48 | RDBM 22 edits FIFA 22 squad-file tables; free and non-commercial | DOCUMENTED | dl.fifa-infinity.com/fifa-22/revolution-db-master-22/ |
| 49 | RDBM can open career files | DOCUMENTED | `wiki_FIFA-22-Live-Editor/Editing-Game-Database.md` |
| 50 | Programmatic match launch | UNKNOWN | no API found; E13 |
| 51 | In-game Lua states are accessible from the LE | DOCUMENTED | `FIFA-21-Live-Editor/lua/DOC.MD`; `le_config.json` |
| 52 | Per-match goals, assists and cards obtainable via `GetPlayersStats` delta | INFERRED | from 8/9 + export script |
| 53 | Subs derivable from `minsplayed` | INFERRED | from 35 |
| 54 | Team stats (possession, shots) and injuries capture | UNKNOWN | E9, E10 |
| 55 | The Cheat Engine repo shows no licence on its GitHub page | CONFIRMED (absence on page) → licence UNKNOWN | github.com/cheat-engine/cheat-engine |
| 56 | Creation Master 16 edits `data\db\fifa_ng_db.db`; adding records breaks saves | DOCUMENTED | soccergaming.com/forums/threads/creation-master-16.183588 |
| 57 | Nothing above has been verified in-game | – | no experiments run |
