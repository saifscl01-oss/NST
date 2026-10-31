# Open Problems

| ID | Problem | Why it matters | Next step | Owner |
|---|---|---|---|---|
| P-01 | Can FM natively process an external match (all consequences)? | Central project risk | X1b baseline, X1c (Route D bound), X1d (Route A steering) | Windows |
| P-02 | Can FM's simulation be held/intercepted for the managed fixture? | Needed for the button-in-FM experience | X2 Harmony reconnaissance on FM26 | Windows |
| P-03 | Can steering reproduce exact scorers, minutes and cards? | Decides whether Route A is a genuine solution or a compromise | After X1d | Windows + analysis |
| P-04 | FIFA per-match event stream (minute-level goals, cards, subs) | Ledger fidelity | E7–E9; clock-correlated polling of score/stats | Windows |
| P-05 | Authorization scope for in-process loaders (BepInEx, Live Editor) in Denuvo-protected games, and whether to install BepInEx into a research copy or the main FM26 install | Must stay within the stated authorization | **User decision** | User |
| P-06 | Legal availability of the FIFA 22 Live Editor DLL (Patreon distribution) | Determines the FIFA-side mechanism | User checks; fallback is the GPL-3 cheat table | User |
| P-07 | IPC transport between bridge and in-game components | Needed for real adapters | Decide once plugin constraints are known (named pipe vs localhost socket vs file drop) | Engineering |
| P-08 | FIFA tactic enum labels and player-instruction bit layout | Tactical mapper output | E2 | Windows |
| P-09 | Matching real FM players to existing FIFA database players | Avoid duplicating real players | Needs E1 schema; name + DOB + nationality + club matching with manual review | Engineering |
| P-10 | Safe FIFA id range for created players | Avoid id collisions | E1/E3 | Windows |
| P-11 | FIFA career calendar picks the opponent | Bridge career needs the FM opponent | E12 proxy-opponent technique | Windows |
| P-12 | Cup rules (extra time, penalties) in the chosen FIFA mode | Correct results for cup ties | E11; Kick-Off fallback | Windows |
| P-13 | Attribute weights are uncalibrated | Player fidelity (Gate 6) | Collect FM/FIFA rating pairs for real players after E1 | Engineering |
| P-14 | Per-patch offset churn (FM26 `game_plugin.dll`, FIFA updates) | Stability | Pin builds; fingerprint by SHA-256; adapters gate on known hashes | Engineering |
| P-15 | Offline operation of FIFA 22 after activation | Offline requirement | E0 | Windows |
