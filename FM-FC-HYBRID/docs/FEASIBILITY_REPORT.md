# Feasibility Report (sprint 1)

Date: 2026-10-31. Basis: desk research (source inspection of community tools; nothing run in-game),
plus a working, tested bridge core on mock adapters. Detailed evidence: [FM_RESEARCH](FM_RESEARCH.md),
[FIFA_RESEARCH](FIFA_RESEARCH.md), [REVERSE_ENGINEERING_TOOLING](REVERSE_ENGINEERING_TOOLING.md),
[EVIDENCE_LEDGER](EVIDENCE_LEDGER.md).

## 1. Bottom line

| Question | Answer today | Class |
|---|---|---|
| Can we detect the managed club's upcoming FM fixture? | Yes, by reading live FM memory (several open-source FM26 plugins do it) | SOURCE VERIFIED (reads) |
| Can we stop FM simulating that fixture? | Unknown. Holding FM before kick-off is trivial (the user simply doesn't advance); programmatically intercepting the "play/instant result" path is unproven | UNKNOWN |
| Can FM process an external match with all native consequences? | Unknown, and nobody has demonstrated it. This is the project's central risk | UNKNOWN |
| Can we configure both squads, lineups, formations and tactics in FIFA? | Yes, for FIFA 20–22, via in-memory database tables (community Lua tooling) | SOURCE VERIFIED (mechanism) |
| Can FIFA play user-vs-CPU and CPU-vs-CPU? | User-vs-CPU yes (normal game). CPU-vs-CPU via a community script for FIFA 20/22 | SOURCE VERIFIED (script) |
| Can we collect match events and statistics from FIFA? | Partly. Live score and clock: yes. Per-player goals/assists/cards/rating/minutes: inferable from career-mode tables before/after the match. Shots, passes, possession, injuries: unknown | SOURCE VERIFIED / INFERRED / UNKNOWN |
| Is anything working in-game? | No | — |

## 2. FM match interception and external result processing

FM26 is the most workable target. It is a Unity 6 IL2CPP shell, but **the match engine and database are
still native C++ in `game_plugin.dll`**. BepInEx 6 gives an in-process managed loader, so one plugin can
both patch the C# flow layer and read or hook the native engine. I verified this claim myself in the
downloaded source of FMSuperScout (`plugin_MemScan.cs`: "game_plugin.dll (native C++ database — person
objects live here)") and FMMatchLens (`GameMatchTickHook.cs`, `GamePluginBuildCatalog.cs`).

What the community has demonstrated: reading saves, reading the live database, reading the live match
tick by tick (goals, cards, passes, shots, ratings), editing player and club data, and biasing an
in-progress FM match through a referee-decision hook. Nobody has demonstrated replacing a simulation,
injecting external events, or triggering native post-match processing from an external result.
Offline save editing is not a write path: FM26 save resources are per-file encrypted.

### Candidate routes

| Route | What it is | Native consequences? | Verdict |
|---|---|---|---|
| **A. Steered simulation** | FM's own engine plays the match, hooked so its scoreline and key events converge on the FIFA ledger | **Yes, by construction**, because FM finishes its own match | Primary. A genuine solution *if* steering can reproduce the scoreline, scorers and cards exactly; a compromise if it only approximates them |
| **B. Managed detect/hold** | Harmony patches on FM26's C# match-start / quick-match path | n/a (front-end) | Needed with A or D |
| **D. Post-hoc edit** | Let FM finish, then overwrite result and stat structures before processing | **Probably partial**: value-driven consequences (tables) likely update; event-driven ones (morale, condition, injuries) probably do not | Fallback and measuring tool. Must be reported as `RESULT_AND_STATS`, not full integration |
| E. FM24 native | Same as A/D inside a 500 MB native monolith with no managed loader | Same as A/D | Alternative only |

**Steering vs replacement.** Under Route A FM generates its own per-player match data constrained by the
FIFA result. Ratings, minutes and condition come from FM's engine; FIFA supplies the outcome and key
events. That honours "FM is the authority" and guarantees native processing, but FIFA's own per-player
stats would be advisory. I recommend it because it is the only route with a credible path to full
consequences; see [DECISIONS](DECISIONS.md) D-007.

**The decisive experiment (X1 in [LOCAL_RESEARCH_ENVIRONMENT](LOCAL_RESEARCH_ENVIRONMENT.md)).** On a
throwaway FM26 save, force one goal in a managed match at the engine level (Route A) and separately edit
a finished result (Route D). Save, reload, and diff the save with a read-only parser to see which
consequences FM regenerated natively. This converts the central UNKNOWN into a measured answer.

## 3. FIFA preparation, control and event collection

**FIFA 22** is the newest PC FIFA that can be scripted without touching anti-cheat. EA AntiCheat arrived
in FIFA 23, and the FIFA 23+ editors work by faking the anti-cheat launcher, so those versions are
**BLOCKED** for this project. FIFA 20–22 carry Denuvo activation but no anti-cheat.

| Capability | FIFA 22 | FIFA 20 | Class |
|---|---|---|---|
| Create/modify players | Live Editor `CreatePlayer`, DB table edits | DB table edits via cheat table, no create API | SOURCE VERIFIED / DOCUMENTED |
| Squads, lineups, formations | `teamplayerlinks`, `default_teamsheets`, `default_mentalities`, `formations` | same tables | SOURCE VERIFIED |
| Team tactics | `defensivestyle`, widths/depth 1..100, `buildupplay`, `chancecreation` | widths/depth 0..9, no build-up/chance-creation | SOURCE VERIFIED (fields); label order UNKNOWN |
| Player instructions | Bitfields `playerinstructionN_1/_2` | same | SOURCE VERIFIED (fields); bit layout UNKNOWN |
| User control | Native | Native | DOCUMENTED |
| CPU vs CPU | Cheat-table "Side Changer" | same | SOURCE VERIFIED (script) |
| Live score / clock | Cheat-table hooks | same | SOURCE VERIFIED |
| Goals/assists/cards per player | Career-mode season-stat delta (`GetPlayersStats`) | weaker | INFERRED |
| Rating, minutes per player | `career_playermatchratinghistory` | — | SOURCE VERIFIED schema (FIFA 21), INFERRED for 22 |
| Shots, passes, possession, injuries | Unknown | Unknown | UNKNOWN |
| Full-time detection | Clock/score hooks, career match-complete | same | INFERRED |

**Execution mode.** A disposable "bridge" Manager Career is the primary mode because only career mode
has documented stat sources. The catch: FIFA's own calendar picks the opponent, so the bridge must
overwrite the next scheduled opponent's squad with the FM opponent (needs testing). Kick-Off is the
fallback for cup rules (extra time, penalties).

**Event granularity gap.** No pre-FIFA-23 tool exposes a live goal/card/sub event stream. Minute-level
events may need clock-correlated polling of the score and stats, or post-match screen data. Under Route A
this matters less: FM needs the outcome and key events, and the ledger records what FIFA could provide.

## 4. Recommended pairing

**FM26 (one pinned, offline Steam build, e.g. 26.3.x) + FIFA 22.**

- FM26: in-process managed loader; MIT-licensed precedents for reading the database and the live match;
  published structure layouts; parseable saves for verification. Costs: Denuvo and per-patch offset churn
  (mitigated by pinning a build). FM22 (no Denuvo listed) is a cheap sandbox for developing hook technique.
- FIFA 22: the richest scripting surface before anti-cheat, tactics closest to FM's vocabulary, open
  cheat-table source for match hooks. FIFA 20 stays as a fully readable reference.

This recommendation is evidence-based but **provisional** until experiments X1 (FM) and Y1–Y4 (FIFA)
run on Windows.

## 5. Risks

1. **Central:** no demonstrated way to make FM natively process an external match (X1 decides).
2. **Steering determinism:** forcing exact multi-goal scorelines and scorers inside FM's engine may be hard.
3. **FIFA event granularity** below "final score + season deltas" is unproven.
4. **Tool availability:** the FIFA 22 Live Editor DLL was distributed via Patreon; legal availability is
   unconfirmed. The open cheat-table route may have to carry more weight.
5. **Authorization scope:** in-process loaders (BepInEx, Live Editor) run inside Denuvo-protected
   processes without altering the protection. Confirm this falls within the publisher authorization
   you described ([PROJECT_BRIEF](PROJECT_BRIEF.md)).
6. **Licensing:** Aranaktu's tooling is GPL-3 (reuse would make derived work GPL); Frosty is
   CC BY-NC-ND (reference only); FM26 plugins studied are MIT. A clean-room FIFA DB writer is likely needed.
