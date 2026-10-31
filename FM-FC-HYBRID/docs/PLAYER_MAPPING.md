# Player Mapping

Code: `src/fmfc_hybrid/identity/registry.py`, `src/fmfc_hybrid/player_mapper/attributes.py`.
Config: `data/mappings/fm_to_fifa_attributes.json`. Tests: `tests/unit/test_identity.py`,
`tests/unit/test_mappers.py`.

## Identity registry
- Each FM player seen in a career gets a **Hybrid Player ID** (`HP-…`) the first time he is captured. It
  never changes: transfers, development, retirement and re-captures update the record.
- Stored per player: FM id, Hybrid id, FIFA id (if linked), link status (`unlinked`, `matched`,
  `created`, `stale`), name, date of birth, origin (`fm_database`, `regen`, `youth_intake`, `fm_editor`),
  club, primary position, the full captured profile (attributes, appearance, traits) with SHA-256, the
  last capture time and the last FIFA sync time.
- Every capture that changes the profile writes an append-only snapshot and an audit entry listing the
  changed fields. A changed profile marks an existing FIFA link `stale`, meaning FIFA must be re-synced.
- Same FM id with a different date of birth is refused (prevents merging two people).
- Careers are isolated: the same FM player gets different Hybrid ids in different careers.

## FIFA ids
- Players that exist in FIFA's database can be linked (`matched`). Matching real players to FIFA records
  is not implemented yet; it needs the FIFA schema from experiment E1 and a matching strategy
  ([OPEN_PROBLEMS](OPEN_PROBLEMS.md) P-09).
- Players FIFA doesn't know (regens, youth graduates, FM-only players) get an id allocated from a
  configured range. Allocated ids are recorded permanently and **never reused**, even after retirement.
  The FIFA adapter can veto ids already present in the game's database.
- The safe range (`fifa_id_range_*` in `bridge.default.json`) is a placeholder. It must be checked
  against the FIFA 22 database before real use.
- Only the two matchday squads are synchronized per fixture, as the brief asks.

## Attribute conversion (provisional)
- Each FIFA attribute is a weighted composite of FM attributes (weights sum to 1), passed through a
  monotone piecewise-linear curve from FM 1–20 to FIFA 1–99.
- Weak foot: FM rates both feet 1–20; the weaker foot is bucketed to 1–5. "Either" → 5.
- Skill moves: bucketed average of dribbling, flair, technique and agility; goalkeepers are 1.
- Positions: FM positions rated 15+ ("accomplished") become FIFA positions, best first.
- Missing inputs (e.g. goalkeeping attributes for outfielders) use a configured default and are listed in
  a per-player conversion report, saved with each match.
- **Status:** the weights are engineering judgement, not calibrated. Target field names follow common
  FIFA database naming and are INFERRED until E1 confirms the FIFA 22 `players` schema (FIFA 22 uses
  `defensiveawareness` where older versions used `marking`, for example). Calibration needs real pairs of
  FM and FIFA ratings for the same players.

## Not yet covered
Appearance (faces, hair, skin tone), kits and numbers, contracts, form, fitness, morale carry-over into
FIFA (FIFA career mode may allow fitness/form injection; see FIFA_RESEARCH §8), and hidden attributes.
