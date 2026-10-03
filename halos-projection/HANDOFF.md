# Halos earnings projection — handoff (written 2026-10-03)

## Task
User (artist NST) wants a projection of what the track **Halos** (solo NST, released 2026-09-25,
ISRC QT9XM2676741) will earn at **3 months, 6 months and 1 year** from release, based on its
current streaming pace.

## Next step (why this file exists)
Previous session's network blocked open.spotify.com, playlistdock.com, www.submithub.com.
User has since set the environment's network access to full, which only applies to NEW sessions.
**In the new session: fetch the 10 playlist links below (follower counts, owner, whether Halos is
listed, date added), then re-run the projection with per-playlist stream expectations.**
If Spotify pages return nothing useful (JS-rendered), ask the user to paste name / followers /
date added / user-vs-Spotify-owned per playlist.

Playlists Halos was added to:
- https://open.spotify.com/playlist/02LI8ykG97EEj91RWlPnOB
- https://open.spotify.com/playlist/41PAMpyVwLZ9fSq2fEs55c
- https://open.spotify.com/playlist/4JkSfgARnJBbWBPaSKFSbw
- https://open.spotify.com/playlist/0mhOvbFfirs9XIzyIIKpLB
- https://www.submithub.com/playlist/3IVDC1uVsVT8JU7nmdNNid
- https://playlistdock.com/spotify-out.php?id=4345&t=bec6e4cfe3c478ea97d2b93c&type=playlist
- https://playlistdock.com/spotify-out.php?id=4100&t=274e2d7ce62555ce372aceae&type=playlist
- https://playlistdock.com/spotify-out.php?id=3919&t=1923f04f06b730dfcaff559d&type=playlist
- https://playlistdock.com/spotify-out.php?id=4101&t=48d0161f3fdfda3844e98adb&type=playlist
- https://playlistdock.com/spotify-out.php?id=3921&t=a0001dc7f2aec9610db408b4&type=playlist
(PlaylistDock links are tracked redirects: only follow them, never submit anything.)

## Data gathered
**Source files**: user uploaded `NST - Main copy.zip` (not committed; large, contains media). Key
inputs inside it: `resources/nst/nst-2026-09-28-per-track-detail.csv`, `resources/nst/nst-weekly-progress-log.md`,
`sauvachi-royalties/README.md`, `nst-album-projection/{README,discovery-mode-rules,artist-tools-extract-2026-08-28}.md`.

**Halos, S4A 2026-09-28**: 101 all-time streams, 26 listeners, 7 saves; only playlist was a user
playlist "Melodic Hip Hop & RnB" (14 streams). 70% active / 30% programmed.

**Halos, S4A Sep 4 – Oct 1 (screenshots, 2026-10-03)**: 262 streams, 131 listeners, 2 streams/listener,
17 playlist adds, 24 saves. Daily streams ~29 (Sep 26) -> 49 (Sep 29) -> ~52 (Sep 30) -> ~46 (Oct 1).
Source split: active 169 (65%), programmed 92 (35%), other 1. Programmed ~19/day by Oct 1.
Spotify Showcase "grow audience" conversion: 35 new active listeners (29 light, 6 moderate).
artist.tools: streams <1,000, popularity 10%, no high-risk playlists.

**Showcase ad** (`halos-showcase-2026-10-03.csv`): Australia, Sep 27/28 – Oct 2, spent GBP 30.64 of
80.00 (incl. tax), reach 2,912, clicks 111, 35 converted listeners, 2.4 active streams/listener,
15 saves, 5 playlist adds. Stats keep updating until Oct 16. Direct return ~84 streams ~ $0.13.

**Money assumptions**: blended ~$0.0015/stream (sauvachi export: fell from $0.0057 over 18 months).
Australia may pay above blended. Halos assumed 100% owned by NST (UNCONFIRMED; ask user).
Discovery Mode: 30% commission, needs 30 days since release (~Oct 25), 20+ streams in
Radio/Autoplay/Mixes in 28 days, 1,000+ streams/12mo.

**Comparables**: Against The World (solo) 1,398 lifetime; PEAK (solo) <1,000, ~$1 earned;
THE SPLIT ~35K lifetime early; CARBON/4 BRICKS DOWN 550-615K (Radio/Mixes/DM-driven, 65-75% programmed).
Album model (rev 5) year-1 per-track tiers: solid ~90K streams, breakout ~550K.

## Projection so far (cumulative from release, $0.0015/stream)
| Scenario | 3 mo | 6 mo | 1 yr |
|---|---|---|---|
| Flat 48/day forever | 4.3K / $6.40 | 8.7K / $13 | 17.4K / $26 |
| Base: ad boost fades, programmed holds (active 29/d half-life 14d->3; programmed 19/d half-life 60d->6) | 2.2K / $3.40 | 3.3K / $5.00 | 5.1K / $7.70 |
| Bear: programmed fades too (half-life 30d->2) | 1.4K / $2.10 | 1.8K / $2.70 | 2.4K / $3.50 |
| Solid (Radio/Mixes take over) | 18K / $27 | 40K / $61 | 90K / $135 |
| Breakout | 110K / $165 | 248K / $371 | 550K / $825 |

Model: cumulative = 262 (at Oct 1, day 7) + exponential-decay daily rate toward a floor; Solid/Breakout use
20% / 45% / 100% of year-1 streams at 3 / 6 / 12 months.

## Key reads to carry forward
1. Showcase ad does not pay for itself; its value is the algorithmic signal.
2. Watch **programmed** streams (not total, which the ad inflated and which drops after Oct 2): ~20/day
   sustained through October = better than other solo tracks; <5/day = bear case.
3. Check in S4A which programmed streams are Radio/Autoplay/Mixes (DM-eligible) vs Discover Weekly/Daylist.
4. Remaining ~GBP 50 ad budget: wait for Oct 16 final Showcase results.
5. Playlist pitches (PlaylistDock/SubmitHub) usually give a short bump, not steady streams. Verify with follower counts.

## Open questions for the user
- Does NST own 100% of Halos? Any distributor/label split?
- Fresher S4A numbers (suggest pulls ~Oct 10 and ~Oct 17) to re-fit the decay.
- Wants a one-page chart or spreadsheet of the scenarios?

## Stored data (under `halos-projection/data/`)
- `nst-s4a/` — S4A pulls: per-track detail, songs, playlists, countries, cities, release engagement (2026-09-28), 12-month monthly data, weekly log, audience timeline, DM/Radio notes, momentum analysis.
- `royalties/` — distributor royalty analysis (README with per-stream rate findings), NST monthly history + projection CSVs.
- `album-projection/` — album model rev 5 (README, Discovery Mode rules and campaign data, artist.tools extract, `model_rev2.py`, CSV).
- `playlisting/` — playlisting strategy, tracker.csv, Groover pitches for Halos.
- `screenshots/` — the 5 screenshots from 2026-10-03 (1 artist.tools header, 2 S4A daily streams, 3 source split, 4 Showcase conversion, 5 Showcase delivery). Order matches upload order.
- `nst-release-catalog.md` — ISRCs and release dates.
- `halos-showcase-2026-10-03.csv` (one level up) — Showcase campaign export.
Not stored: media (mp4/cover art), decks/pptx, sauvachi-only per-track files, the original zip.
