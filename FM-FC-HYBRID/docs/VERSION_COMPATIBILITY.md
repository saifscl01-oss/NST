# Version Compatibility

Full per-version tables: [FM_RESEARCH §2](FM_RESEARCH.md) and [FIFA_RESEARCH §2](FIFA_RESEARCH.md).

## Football Manager

| Version | Architecture | Protection (store listing) | Tooling maturity for us | Role |
|---|---|---|---|---|
| FM15–FM18 | Native C++ monolith | Steam DRM | Old memory editors | Historical reference |
| FM19–FM21, FM23 | Native C++ monolith, x64 | Denuvo + Steam | Memory editors, CE tables | Historical reference |
| FM22 | Native C++ monolith, x64 | Steam only, no Denuvo listed | Same class as FM24 | Cheap sandbox for hook technique |
| **FM24** | Native C++ monolith `fm.exe` (~500 MB) | Denuvo + Steam | External memory editing only; no managed loader | Fallback (Route E) |
| **FM26** | Unity 6 IL2CPP shell + native `game_plugin.dll` (engine and DB) | Denuvo on `fm.exe` | BepInEx 6, three MIT plugins, published layouts | **Recommended** |
| FM27 | Same split as FM26 (released ~Nov 2026) | Expected Denuvo | Community tools already follow it | Future port target |

FM26 → FM27 technique should port forward; each patch moves offsets, so builds are pinned and
fingerprinted by SHA-256 (the community tools do the same).

## FIFA

| Version | Engine | Anti-cheat | Scripting | Role |
|---|---|---|---|---|
| FIFA 15–16 | Ignite (INFERRED) | none | DB file editing only | Historical |
| FIFA 17–19 | Frostbite | none | Cheat tables, Frosty mods | Historical |
| **FIFA 20** | Frostbite | none (Denuvo) | GPL-3 cheat table ("Live Editor" in CE form), fully readable | Reference / fallback |
| FIFA 21 | Frostbite | none (Denuvo) | First DLL Live Editor (Lua 5.3 API) | Comparison |
| **FIFA 22** | Frostbite | none (Denuvo) | Live Editor (`CreatePlayer`, DB API), GPL-3 cheat table | **Recommended** |
| FIFA 23 / FC 24+ | Frostbite | EA AntiCheat | Editors require faking the anti-cheat launcher | **BLOCKED** |

## Bridge configuration per version
- `data/configurations/fifa_capability_profiles.json`: `fifa22-provisional` and `fifa20-21-provisional`
  (field ranges SOURCE VERIFIED; enum labels pending FIFA experiment E2).
- `data/configurations/bridge.default.json`: selects the profile.
