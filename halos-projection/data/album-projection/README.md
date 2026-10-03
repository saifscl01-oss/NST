# NST 5-track album — earnings projection
Built 28 Aug 2026. Live dashboard (rev 5):
https://claude.ai/code/artifact/af04e64c-1c02-42ed-8b30-34f303fd1cd5

Scope: 5 tracks, 100% owned, solo, lead single then album 8 weeks later, releasing in 1-3 months.

## Headline (rev 5)
Year 1 base **$284** enrolled in Discovery Mode and net of its 30% commission
(bear $109 / bull $684). Unenrolled the same album makes **$183**.
Discovery Mode is worth +55% revenue / +93% streams, measured on sauvachi's own campaigns.

## Files
| File | What it is |
|---|---|
| `discovery-mode-campaign-data.md` | **sauvachi's actual campaign lift reporting — the measured numbers.** |
| `discovery-mode-rules.md` | Spotify Discovery Mode eligibility, contexts, 30% commission, and what it means here. Read this one first. |
| `artist-tools-extract-2026-08-28.md` | Per-track lifetime streams + breakout multiples + playlist reach from artist.tools |
| `model_rev2.py` | Current Monte Carlo (40k runs/scenario), recalibrated on artist.tools |
| `model.py` | Rev 1, superseded — kept to show what the recalibration changed |
| `album_projection.csv` | Rev 1 monthly + cumulative by scenario |

Upstream inputs live in `../sauvachi-royalties/` (distributor export, royalty analysis,
split reconciliation) and `../nst-analytics/` (Spotify for Artists extract).

## Revision history
- **Rev 1** — $846 yr 1. Modelled THE SPLIT as a ~200K-stream success case.
- **Rev 2** — $354 yr 1. artist.tools showed THE SPLIT at 35,049 lifetime / 0.7x typical
  (below average, and it lost both playlist placements). Solid tier was ~2x too high.
  Also surfaced: every track with traction is a sauvachi release ft. NST; both NST-solo
  releases (PEAK, Against The World) are the two deadest in the catalog.
- **Rev 3** — Discovery Mode analysis. Rules explain the pattern in rev 2 and constrain the plan.
- **Rev 4** — Licensor criterion confirmed satisfied (DM is live in S4A), so the constraint is
  purely track-level. Sharpened the Against The World diagnosis and added the path to eligibility.
- **Rev 5** — Pulled sauvachi's actual Discovery Mode campaign reporting. Median measured lift
  +282% across 11 song-months vs a 43% break-even. CARBON's historical lift is +5,744% and its
  Dec 2025 inflection matches sauvachi's first campaign exactly — CARBON was made by Discovery
  Mode, not found by the algorithm. Forced a modelling correction (archetypes already assume
  DM, so the commission belongs on them): headline $354 -> $284, unenrolled counterfactual $183.

## The four things to act on
1. **Read which criterion Against The World is failing in S4A.** One minute. If it's the
   20-algorithmic-stream bar, Spotify isn't serving NST-solo material at all and the album
   needs restructuring. If it's the hidden unique-listener minimum, the problem is reach and
   the album is fine as scoped. Opposite conclusions — check before committing.
   (PEAK can't be saved either way; it fails monetization at <1,000 streams/12mo.)
2. **Run a monthly campaign the way sauvachi does, and prune on the reporting.** Thirteen
   consecutive campaigns built the catalog you're benchmarking against. Enroll everything
   eligible, read the per-song lift, cut what isn't responding — TUSS sat in the June campaign
   for 776 streams. Enrollment is necessary, not sufficient.
3. **Design month one around clearing 20 algorithmic streams.** Not sales, not reach. That's
   ~15 engaged people for a week, against 406 super listeners and 7,786 monthly actives.
   Super listeners first, dense pre-saves, sequencing that lets Autoplay carry from CARBON.
   Clear it and Discovery Mode compounds from month two; miss it and the album never enters the loop.
4. **Settle the 0% masters.** CARBON + 4 BRICKS DOWN project $2,427 over 12 months against
   $354 for the whole album. Worth ~7x more than making five new songs.
