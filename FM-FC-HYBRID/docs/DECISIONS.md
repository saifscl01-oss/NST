# Decisions

Format: context, decision, consequences. Status: Accepted unless stated.

## D-001 Project lives in `FM-FC-HYBRID/` inside the `NST` repo
The repo held an unrelated project; the user asked for a new folder. Existing content untouched.

## D-002 Bridge in Python 3.10+, standard library only
Runs on a bare Windows Python, no supply chain, easy to audit; the bridge is orchestration and
persistence, not performance-critical. In-game components will be C# (FM26 BepInEx) and Lua (FIFA),
talking to the bridge only through JSON contracts.

## D-003 SQLite per career with append-only triggers
Durable, transactional, crash-safe (WAL), inspectable. History cannot be rewritten even by buggy code.

## D-004 Dataclasses as the single contract definition; JSON Schemas generated
One source of truth for Python, C# and Lua. A test fails if committed schemas go stale.

## D-005 Adapters speak game ids; the bridge binds to Hybrid ids
Keeps identity logic out of game-specific code and lets fixtures be re-detected stably.

## D-006 Integration level is explicit and audited
Adapters report what they achieved; only native processing counts as full integration. Enforces the
brief's rule that score editing is never called full integration.

## D-007 FM integration strategy: steered simulation first (Proposed, pending X1)
Options: (A) hook FM's own engine so it produces the FIFA outcome, letting FM run native post-match
processing; (D) let FM finish, then overwrite result and stats.
Recommendation: **A as the target, D as a fallback and as a measuring tool.** A is the only route with a
credible path to native consequences. Trade-off: under A, FM generates its own per-player detail
constrained to the FIFA outcome, so FIFA's per-player statistics become advisory. If steering can't
reproduce exact scorers and cards, A is a compromise and must be reported as such. Decided only after
experiment X1.

## D-008 Recommended pairing FM26 + FIFA 22 (Provisional)
FM26: in-process managed loader and MIT precedents. FIFA 22: richest pre-anti-cheat scripting surface.
FIFA 23+ is BLOCKED (anti-cheat). Revisit after Phase 1–3 experiments.

## D-009 FIFA execution mode: disposable bridge career first, Kick-Off fallback (Proposed)
Only career mode has documented stat sources. Needs the proxy-opponent technique (E12) to work.

## D-010 Research toolkit is file-level; binary analysis delegated to REA
A safety classifier stopped a hand-written PE parser. Rather than recreate it, the toolkit does
discovery, hashing, inventories, comparison and evidence manifests, and generates REA command plans.
REA (MIT, user-installed) covers imports, resources, certificates, exports and IL2CPP metadata.

## D-011 Tactical library stays small until FIFA E2
Per the brief: fidelity framework and seed rules now; the full library once enum and instruction
semantics are confirmed. Capability profiles are per version so rules degrade honestly.

## D-012 No reuse of GPL-3 or CC BY-NC-ND code in the bridge
Aranaktu's FIFA tooling is GPL-3 and Frosty is CC BY-NC-ND. They are studied for mechanisms. Any FIFA DB
reader or writer will be written clean-room. MIT FM26 plugins may be reused with attribution if needed.
