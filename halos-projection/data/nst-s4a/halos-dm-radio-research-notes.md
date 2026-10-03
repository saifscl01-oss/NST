# Discovery Mode & Radio — Research Notes

**Compiled:** Sept 4, 2026. Consolidated findings from web research this session, vetted against real NST/sauvachi data where possible. Method used throughout: trace every specific number to its source, check who benefits if the claim is believed, cross-check against real verified data when available, and separate mechanism claims (how the system works) from magnitude claims (specific thresholds/percentages).

---

## 1. Discovery Mode eligibility — confirmed, official

Song-level requirements (all three required):
1. Released on Spotify ≥30 days
2. **≥20 streams in "Discovery Mode contexts" in the trailing 28 days**
3. Met Spotify's monetization eligibility criteria the prior month

Artist-team level: ≥3 eligible songs, ≥25,000 monthly listeners. NST clears this alone (79,752 monthly listeners in the last measured period).

**"Discovery Mode contexts" is a specific, narrow definition — not any algorithmic exposure**: it is **Spotify Radio, Autoplay, and Spotify Mixes** (Daily, Artist, Mood, Decade, Genre Mixes) only. It explicitly excludes **Your DJ and Smart Shuffle**, which are separate algorithmic surfaces already tracked in NST's per-track playlist-source breakdowns but don't count toward this threshold.

Correction from earlier in this project: NST's own account already has distributor-level Discovery Mode access. The "No campaigns — reach out to your distributor" empty state was misread previously as an access gate; it's the same UI shown when a song simply hasn't cleared per-song eligibility yet. See `project_nst_dm_eligibility_not_access` in memory.

Sources: [Getting access to Discovery Mode](https://support.spotify.com/us/artists/article/getting-access-to-discovery-mode/), [Discovery Mode contexts](https://support.spotify.com/us/artists/article/discovery-mode-contexts/)

## 2. Why 20 DM-context streams is a low-risk bar for Halos specifically

Cross-checked against real catalog data: Radio alone was 43–72% of total streams across CARBON, 4 BRICKS DOWN, and THE SPLIT even at reduced scale; THE SPLIT alone pulled 14,882 Radio streams in one 28-day window at 75 days old. Halos isn't cold-starting — it inherits a warm relationship with an algorithm that already has NST's catalog deeply embedded (CARBON alone sits on 1,391 total playlist placements). The real risk is speed of clearing the bar, not whether it clears at all.

## 3. Source vetting — a claim traced back and retracted

**Chartlex**, the source behind a first batch of specific numeric growth-hacking thresholds (20% save rate, 2.5+ streams/listener, 200+ saves in 48h, 40–60% placement lift from 200+ pre-saves), turned out on inspection to be a paid promotion company selling $129–$799 Spotify/Meta/YouTube ad campaigns, with an undisclosed stream-acquisition methodology — a direct conflict of interest.

Cross-checked against real NST/sauvachi data (see `nst-12month-monthly-data.md`): CARBON never exceeded a 1.98 streams/listener ratio across 12 months (claim: "2.5+ target"), and its best save/stream month was ~2.6% (claim: "20% for Discover Weekly expansion, 4-6% average"). These are demonstrably successful, heavily DM-amplified tracks — the numbers didn't survive contact with real data. **Retracted**: don't use any specific percentage threshold from this or similarly-incentivized sources without independent verification.

**Method that generalizes:** trace every specific number to its origin page (not the search-snippet synthesis, which can make one self-interested source look like "convergent findings"); check the source's business model; cross-check against real data whenever available.

## 4. How Radio actually works — what's confirmed vs. trade secret

**Confirmed, primary-source (patents + Spotify Research publications):**
- **Radio and Autoplay run on a different system than the Home-screen recommender.** Home/shelf recommendations use **BaRT** ("Bandits for Recommendations as Treatments," a real 2018 Spotify Research paper — Explore, Exploit, Explain), an explore/exploit bandit system measuring success by a 30-second-listen threshold. This is Home-screen specific.
- **Radio's actual documented mechanism** (per a real Spotify patent, "Generating a playlist," USPTO): a seed track is converted into a "construct" from a frequency-domain representation of the audio; the system finds other tracks whose constructs fall within a similarity range, combined with co-listening/collaborative behavioral signals ("fans of the seed artist also listen to you"). This is graph-expansion from a seed node, not a bandit-style engagement optimizer.
- A newer, confirmed-in-production system, **Impatient Bandits** ([Spotify Research, real named authors including Mounia Lalmas, Spotify's actual head of research](https://research.atspotify.com/publications/impatient-bandits-optimizing-for-the-long-term-without-delay)), optimizes recommendations for long-term (weeks-later) satisfaction rather than short-term proxy signals — originally applied to podcasts, now "a core part of the recommender system."
- **Spotify has publicly acknowledged commercial considerations (i.e., paid Discovery Mode enrollment) directly influence which songs get recommended within Radio/Autoplay/Mix contexts**, and does not disclose which recommendations in a session are organic vs. commercially weighted. Practical read: DM enrollment buys a paid weighting boost inside those contexts — it's not purely "the algorithm rewarding organic momentum it detected." This is consistent with why both CARBON (compounding) and 4 BRICKS DOWN (declining) remained 63–69% DM-sourced in August despite opposite organic trajectories — DM likely kept 4BD's numbers from collapsing further even as its real engagement fell.

**Not known, and not a research gap that more searching would close** — Spotify treats the exact ranking/weighting function (how audio similarity, co-listening, recency, and paid priority combine for any specific placement decision) as a trade secret. No verified numeric threshold for any of this exists in any primary source found.

Sources: [Generating a playlist — patent](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11461388), [Impatient Bandits — Spotify Research](https://research.atspotify.com/publications/impatient-bandits-optimizing-for-the-long-term-without-delay), [Spotify Research — GitHub](https://github.com/spotify-research)

## 5. Strategic implications from the mechanism (not just the eligibility rule)

1. **Getting existing NST listeners to stream Halos directly, fast, is the single highest-leverage move** — a play from someone who already has CARBON/4BD as a strong node in their own Radio history creates a direct co-listening edge from an already-dominant node to the new track. This is mechanically faster than winning cold/new listeners, which is a separate, slower BaRT/Discover-Weekly objective.
2. **Sonic continuity with CARBON/4BD is a real, secondary lever** — closer "construct" similarity in the patent-documented sense shortens the graph distance, independent of fan behavior. Treat as a tiebreaker, not a mandate.
3. **Once DM-enrolled, don't read Radio/Mix volume alone as proof of organic health** — the paid boost can mask decay (as it may be doing for 4 BRICKS DOWN). The absolute-monthly-saves trend (see `halos-momentum-analysis.html`) remains the real signal DM can't manufacture.

## 6. Traffic-driving and off-platform tactics (lower-confidence, but mechanism-consistent)

- External traffic doesn't count toward the 20-stream DM-context tally directly (that requires the play to occur inside Radio/Autoplay/Mixes) — but high-intent external traffic that converts to saves/completions is what accelerates the algorithm's decision to start placing a song into *other* people's Radio/Mixes. Source-agnostic: "collaborative models respond to the quality of interaction, not the acquisition channel."
- Smart links (Linkfire/ToneDen/Feature.fm) for pre-save + cross-platform routing.
- TikTok sequencing: teaser clips pre-release (hook only) → strongest 15s + hard CTA on release day → sustain phase (duets, story-behind-the-song) for 2–4 weeks.
- Spotify Clips (native in-app short video, can surface to non-followers via Now Playing) — a genuine Spotify discovery surface, closer in kind to Radio/Mixes than an external platform; described in third-party sources as a multiplier on already-healthy retention, not an ignition source on its own.
- Spotify Canvas — cheap completion-rate lever during actual streams, commonly skipped.
- NLP/mood-language framing: Spotify's genre/mood classification reportedly picks up language used in press/captions/blurbs, not just audio — plausible, consistent with published architecture, but not confirmed by a primary source. Treat as credible-but-unconfirmed.

## 7. Display Campaigns (Marquee/Showcase) — live-tested mechanics

See `project_display_campaign_mechanics` in memory for full detail. Headlines:
- Three targeting goals: Grow audience (Potential/Collaborator's/Programmed listeners), Reactivate listeners (previously active, ≥28 days lapsed), Deepen fan engagement (Light 1–2/28d, Moderate 3–14/28d, Super 15+/28d).
- **Targeting only the existing-fan segment alone was rejected by the tool** ("not enough likely listeners") on THE SPLIT — must blend with broader Grow Audience targeting to have enough scale to run.
- **"Collaborator's audience" only appears when the specific promoted release has an actual featured credit** — present for THE SPLIT (sauvachi credited), completely absent for PEAK (true NST solo). This is tied to the release's own metadata, not the artist account's collaboration history. **Halos is confirmed solo, so this paid lever will not be available for it** — the fallback is sauvachi voluntarily cross-promoting outside the ad platform (confirmed as planned: an Instagram post).
- Marquee requires the release to be ≤18 days old; Showcase has no time restriction. Real benchmark pulled live (THE SPLIT, US, all 3 goals blended): suggested budget £1,851 → 117K–351K reach, 2.6K–7.7K clicks, £0.36/click (incl. 20% tax).
