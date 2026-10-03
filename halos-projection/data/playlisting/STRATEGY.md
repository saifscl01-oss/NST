# NST Playlisting Strategy: $40, every free shot taken

**Built:** 2026-09-27 · **Lead track:** Halos (out 2026-09-25, 144 BPM) · **Runs:** 6 weeks

## The principle

At $40 the free lanes do most of the work. Cash only goes where there's proof. Free credits expire or refill on a timer, so a credit you don't claim is a lost submission. The job is to claim every refill, point it at a pre-vetted curator, and log the result.

## 1. Free lanes (claim all of it)

| Lane | Free allowance | Weekly max | Automation |
|---|---|---|---|
| SubmitHub standard | 2 credits every 4h | ~56 (4 windows/day) | `credit-reminder.plist` alerts at 10/14/18/22 |
| Daily Playlists | 10 standard/week | 10 | Monday alert text |
| PlaylistDock | 5/day per artist, max 3 per song per 24h | 21 (Halos) | same alerts |
| Direct curator pitches (email/IG) | unlimited, cap 10/day to keep them personal | 70 | `find_curators.py` builds the list; Gmail drafts on request |
| One-off free forms: Indiemono, Soundplate, musicto, Kolibri | 1 per track each | once | one sitting per track |
| Pandora AMP, Anghami for Artists (MENA, verify pitch tool) | official, free | once | one sitting |
| Spotify editorial pitch (S4A) | 1 per release | next single | pitch 3 to 4 weeks before release, 7 days minimum |

Standard SubmitHub credits get lower priority than premium ones, so aim them at curators whose stats show they actually listen to standard submissions (SubmitHub shows this on each profile). Once Halos has been pitched to every relevant curator, send the leftover free credits to **CARBON** and **THE SPLIT**, which already get strong Radio traffic (43 to 72% Radio share).

## 2. The $40

| When | Spend | What |
|---|---|---|
| Now | **$27**: SubmitHub 30 premium credits | Hip-hop curators at 1 to 2 credits each (~18 to 22 curators). Only curators with ≥10% approval, active in the last 30 days, and a clean bot check. Premium guarantees a reply in 48h. |
| Day 10 | **$13** held back, spent on whichever channel is working | If SubmitHub premium approval is ≥15%: buy the $10 / 10-credit pack. If it's lower: Groover, 6 curators at €2 each, focused on MENA and EU hip-hop plus radio and blogs, not just playlists. |

Target cost is **≤ $4 per approval**. The approval you already have counts. Thank that curator, share their playlist on IG stories with a tag, and save them for the next release. A repeat curator is the cheapest approval you'll ever get.

## 3. Skip these (they waste money or put the account at risk)

- Playlist Push, SoundCampaign: minimums well above $40.
- Anyone selling "guaranteed streams", Fiverr playlist gigs, or playlists over ~50k followers with no real contact route. Discovery Mode is live on the catalog, and artificial streams can get tracks pulled by DistroKid. Run every unfamiliar playlist through the artist.tools bot checker first. `find_curators.py` marks the likely offenders `suspect`.

## 4. Weekly loop (~20 min/day plus 1 hr on Monday)

1. **Monday:** run `find_curators.py` to refresh the vetted list. Bot-check the top 20. Use the 10 Daily Playlists credits. Review the tracker.
2. **Each alert (10/14/18/22):** spend 2 SubmitHub standard credits on the next 2 vetted curators. Log both.
3. **Daily:** send 10 direct pitches from `curators.csv` rows that have an email/IG (template below). Use 3 PlaylistDock credits.
4. **Day 7 after each direct pitch:** send one follow-up, then drop them.
5. **Approvals:** thank the curator, screenshot the add, share it, set `followup_due` to the next release.

Every submission goes in `tracker.csv`. The Monday NST Unit standup can read it (approval rate, cost per approval) next to S4A playlist-source streams. What we actually measure is streams from the playlist over 28 days, not the approval count.

## 4b. Targeting (from NST, 2026-09-28)

Halos sits with **Don Toliver, Travis Scott, TheKidSZN**, and especially melodic Travis (e.g. "Skeletons"). Target playlists built around those artists: search terms such as "don toliver", "travis scott melodic", "utopia vibes", "astroworld vibes", "melodic trap", "thekidszn". A good playlist has 2 or more of these artists among its recent adds. A SubmitHub song description and track description are already saved from the first pitch, so reuse them.

## 5. Pitch template (fits SubmitHub's limit; no em-dashes)

> Hey [name], NST here, a Bahrain-based hip-hop artist. 1M+ Spotify streams in year one. "Halos" dropped Sept 25: [one line on the vibe, e.g. 144 BPM, dark melodic energy]. I think it'd sit well next to [a specific track on their playlist] on [playlist name]. Appreciate you listening either way.
> open.spotify.com/artist/69iFhVcN7TLumZZXwxr4ak

Always name a real track on their playlist. That's the difference between a real pitch and spam.

## 6. What's automated and what isn't

- **Automated:** curator discovery, activity, contact, and bot flagging (`find_curators.py`); credit-window alerts (`credit-reminder.plist`); logging and analysis (`tracker.csv`); Gmail **drafts** for direct pitches (Claude writes them, you hit send).
- **Not automated, on purpose:** the submissions themselves. SubmitHub and Groover ban bots, and an account ban would cost more than the $40. Claude can speed up a batch in your Chrome (fill forms, you approve each batch before it's sent), but a person stays in the loop.

## Setup (one time)

1. Create a free Spotify developer app at developer.spotify.com/dashboard, then `export SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=...` and run `python3 find_curators.py`. Spotify's 2024 to 2026 API restrictions may block some playlists; the script skips those.
2. Install the alerts: `cp credit-reminder.plist ~/Library/LaunchAgents/com.nst.credit-reminder.plist && launchctl load ~/Library/LaunchAgents/com.nst.credit-reminder.plist`
3. Fill in the existing SubmitHub approval in `tracker.csv`.
