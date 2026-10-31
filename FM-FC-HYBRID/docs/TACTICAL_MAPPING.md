# Tactical Mapping

Code: `src/fmfc_hybrid/tactics/translator.py`. Rules: `data/mappings/fm_tactics_rules.json`.
Target capabilities: `data/configurations/fifa_capability_profiles.json`. Tests: `tests/unit/test_mappers.py`.

## Principle
Preserve the *intent* of an FM instruction, not its name. Every FM element (formation, mentality,
each team instruction, each role/duty, each individual instruction) is classified:

| Fidelity | Meaning |
|---|---|
| direct | An equivalent mechanism exists |
| strong | Intent preserved with a close mechanism |
| partial | Only part of the intent survives |
| unsupported | Nothing in the target expresses it |

The translation result keeps every element with its fidelity, applied values, dropped knobs and
rationale. It is saved per match (`tactical_translation` snapshot) so the user can see what was lost.

## How it works
1. **Rules** say what an FM element means as bridge "knobs" (`team.depth`, `pi.attacking_runs`…), using
   `set` or `add`. Integer knobs use a 1..10 bridge scale.
2. **Capability profiles** say which knobs a FIFA version really has and their game ranges. A rule
   targeting a missing knob is downgraded automatically (to partial if something still applies,
   unsupported otherwise). So the same rules stay honest across versions: under `fifa20-21-provisional`
   "shorter passing" becomes unsupported because FIFA 20/21 have no `chancecreation` field.
3. Order: formation → mentality (base values) → team instructions (adjustments, clamped) → roles
   (per-player instructions).
4. Integers convert linearly from the bridge scale to the game range (e.g. depth 8/10 → 78 on FIFA 22's
   1..100, → 7 on FIFA 20/21's 0..9).
5. **Formation**: nearest FIFA formation by slot matching, with neighbour costs for near-equivalent slots
   (RW↔RM 0.4, CAM↔CM 0.5 …). Cost 0 is direct, ≤1 strong, otherwise partial.

## What is known about the FIFA side (from [FIFA_RESEARCH §5.4, §7](FIFA_RESEARCH.md))
- Per team up to five game plans (mentalities, Ultra Defensive → Ultra Attacking), each with formation,
  per-slot positions and pitch offsets, player-instruction bitfields and team tactic fields.
- FIFA 22: `defensivestyle` (0..4), `defensivewidth`/`defensivedepth`/`offensivewidth` (1..100),
  `buildupplay` (0..3), `chancecreation` (0..3), players in box, corners, free kicks.
- FIFA 20/21: widths/depth 0..9, `offensivestyle` (0..3), no build-up or chance-creation fields.
- **Unknown:** which integer means which UI label, and the player-instruction bit layout. FIFA
  experiment **E2** resolves both; until then the profiles use descriptive labels that the FIFA adapter
  will map to integers.

## FM's mentality ladder vs FIFA's game plans
FM has 7 mentality steps, FIFA 5 game plans. The seed rules map the shared steps as strong and the two
FM-only steps (cautious, positive) as partial with depth adjustments. A richer approach is to use
FIFA's five game-plan slots to carry FM's in-match tactical changes; that waits until the FIFA adapter
can switch game plans.

## Seed rule coverage
Mentalities (7), ~30 team instructions, ~18 roles including all those the brief names (inverted wing-back,
mezzala, regista, segundo volante, half-back, box-to-box, advanced playmaker, trequartista, deep-lying
forward, pressing forward). Individual instructions have no rules yet and report unsupported.
Per the brief, the library will not grow until the FIFA version and its real tactical surface are
confirmed by E1/E2.

## Notable losses (provisional)
- Inverted wing-back, half-back: in-possession shape changes (stepping into midfield, dropping between
  centre-backs) have no FIFA instruction; only partial intent survives.
- Line of engagement is folded into depth; FIFA does not separate it from the defensive line.
- Offside trap, get stuck in, shoot on sight: no tactical equivalent identified.
- Gameplay sliders (e.g. CPU line height, marking) could approximate some of these later, but sliders
  are global rather than per team, so they cannot express one side's tactics.
