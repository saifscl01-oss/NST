# sauvachi royalty analysis & NST split reconciliation

Analysis date: 28 August 2026
Source: `results.numbers` — sauvachi distributor line-item export, 30,488 rows,
sale months Dec 2021 – May 2026, 44 titles.

---

## Files

| File | What it is |
|---|---|
| `royalties.html` | Catalog dashboard — earnings history, 24-month projection, title trajectories, platform/territory mix. Open in a browser. |
| `nst_split_reconciliation.html` | NST split statement — ownership applied per ISRC, payable schedule from Aug 2026 forward. Open in a browser. |
| `results_parsed.csv` | The full export converted from .numbers to CSV. Everything else derives from this. |
| `sauvachi_earnings_projection.csv` | Whole-catalog monthly actuals + all five projection scenarios. |
| `catalog_monthly_by_title.csv` | Monthly earnings per title, Jan 2025 onward. |
| `nst_monthly_history.csv` | Monthly earnings on the five NST-credited masters. |
| `nst_projection.csv` | 24-month projection on those masters, bear/base/bull. |

Live versions:
- Catalog dashboard — https://claude.ai/code/artifact/4734bc19-ad03-4d5c-a7ff-02ba478a16e1
- Split reconciliation — https://claude.ai/code/artifact/19f1baa3-23f3-4d8d-951b-0962f1981c13

---

## Method notes (these matter if anyone re-runs the numbers)

**Reporting lag.** A sale month reaches 34.9% of its final value after one
reporting cycle and 99.7% after two. Months are therefore final at lag 2.
**May 2026 is excluded from all actuals** — it had one cycle behind it and shows
$2.05 against April's $578. That is incompleteness, not a collapse.

**Projection.** Fitted per title, never on the aggregate — a trend fitted to the
total would extrapolate the last year's growth and produce a nonsense number.
Each title gets a log-linear growth rate from its last five months, tapered
geometrically (φ=0.55) toward a terminal catalog-decay rate: −8%/mo base,
−13% bear, −4% bull. Titles under $0.50 across the last three months are dropped.
The release-cadence scenarios add a new-title cohort ramping on the observed
2025–26 cohort curve.

**Group by ISRC, never by title.** The distributor relabelled several masters
mid-life, so the same recording appears under two or three different
title/artist strings. Title-level accounting undercounts: it hides $129 on
4 BRICKS DOWN and $19 on CARBON.

---

## Catalog findings

- Trailing 12 months **$3,540**, against $128 the prior year. Lifetime $3,687 —
  96% of it earned since Jan 2025.
- Next 12 months: **$4,634 base case** on existing catalog alone
  ($3,553 bear / $5,738 bull). **$7,349** if release cadence matches last year's.
  That $2,715 gap is the release schedule, and it is the largest controllable
  variable in the whole picture.
- April 2026 ($578) is the peak of the current cycle, not a new floor. Every
  title past its peak decays at roughly −8%/month. On existing catalog alone the
  run rate halves within nine months.
- ~70% of current income comes from titles first reported inside the last twelve
  months. Nothing here is annuity income yet.
- **Revenue per stream has fallen 40% in eighteen months** ($0.0057 → $0.0015).
  Streams are growing much faster than earnings — the growth is coming from
  lower-paying territories (DE, BR) and platform mix. Any volume target that
  assumes the old rate will miss.
- Spotify is 88% of recent earnings. Single-platform concentration risk.

---

## NST split position

Ownership is the share — there is no separate split rate. ("The Split" is a
song title at 40%, not a 40% rate; this was misread earlier in the analysis
and corrected.)

| Master | ISRC | Ownership | Collected to Apr '26 | Yours | Gross yr 1 | Yours |
|---|---|---|---|---|---|---|
| 4 BRICKS DOWN | QZZ7X2586368 | 0% | $1,144.82 | $0.00 | $1,019 | $0.00 |
| CARBON | QZWFV2580455 | 0% | $437.52 | $0.00 | $1,408 | $0.00 |
| TUSS | QZZ7L2592634 | 50% | $58.84 | $29.42 | $72 | $36.02 |
| HULKS | QZES82558881 | 50% | $6.36 | already yours | $5 | already yours |
| PEAK | QT6FN2589183 | 100% | $1.09 | $1.09 | $0 | $0.00 |
| Against the World | — | 100% | not in export | — | — | — |
| The Split | — | 40% | not in export | — | — | — |
| **Total** | | | **$1,648.63** | **$30.51** | **$2,503** | **$36.02** |

Splits count from today forward; the historic column is context, not a
receivable. "From today" is read as sale months May 2026 onward — on a payment
basis instead, May–Aug shift out of the payable column.

### Open items

1. **The two masters at 0% are the whole question.** 4 BRICKS DOWN and CARBON
   are $1,582 already collected and $2,427 projected over the next year — against
   $36 on everything owned. A ratio of about 63 to 1. CARBON is also the only
   track in the entire catalog still climbing ($47 → $126 → $184 across Feb–Apr,
   not yet peaked). Whatever the reason for 0% — flat fee, work-for-hire,
   something agreed before it was written down — the restructure is the moment to
   confirm it was deliberate.
2. **Find "The Split" and "Against the World."** The two largest ownership
   stakes, neither reporting a cent through this account. "The Split" is known to
   exist (it had a Discovery Mode issue), so the question is which account it
   reports into.
3. **Don't split HULKS twice.** It already reports at a 50% team percentage —
   the NST half comes off at the distributor before these figures. When splits
   move to sauvachi personal and the Tracks Capital label account, either remove
   the source-level split or leave HULKS out of the new terms.
4. **Write ownership per ISRC, not per title.** An agreement naming titles will
   drift out of sync the next time a distributor relabels something.
5. **Define "from today"** — sale month or payment date. May–Aug 2026 are
   streamed but unreported, and the two readings differ.
