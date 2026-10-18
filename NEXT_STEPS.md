# Next steps: handoff note (as of 18 Oct 2026)

Written for the next Claude session working in this repo. Read this first, then `README.md`.

## Where things stand

- Live: https://tecunningham.github.io/eci-benchmark-logodds/ (`index.html`, the dashboard) and
  https://tecunningham.github.io/eci-benchmark-logodds/npca.html (nonparametric / curve-shape analysis).
  GitHub Pages serves `main` from the repo root. Push to `main` and Pages rebuilds in about a minute.
- Always `git pull --ff-only` before starting. Another session (branch `claude/stoic-brown-estavv`, merged
  as PR #1) built the original npca page; this session built everything since.
- Both HTML pages are **generated**. Edit `scripts/page_template.html` / `scripts/npca_page_template.html`,
  then run `scripts/build_page.py` / `scripts/npca_build_page.py`. Never hand-edit `index.html` or `npca.html`.

## What has been established

1. **The question.** Does frontier capability growth look faster in the last 12 months (Oct 2025–Oct 2026)
   than in the 12 before, and how much does that depend on ECI's assumption that every benchmark follows a
   logistic curve of capability?
2. **Curve shape barely matters for fit.** In `scripts/npca_links.py`, seven per-benchmark curves are compared
   with capability held fixed. Held-out error is within about 2% of the logistic for all of them. On later
   models, the piecewise-linear npca curve is clearly best (−4.8%) and isotonic is worst. Logistic + floor +
   ceiling is about equal to the logistic, but only after the fix in item 6.
3. **Acceleration does depend on the curve** (`scripts/npca_accel.py`, joint fits, 80 rounds from published ECI).
   Growth in ECI points per year, previous 12 months → last 12:

   | Curve | Previous → last |
   |---|---|
   | Published ECI | 13.2 → 17.1 |
   | Logistic | 13.2 → 17.0 |
   | Floor + ceiling | 13.3 → 18.0 |
   | Shared free shape | 13.4 → 19.2 |
   | npca piecewise-linear (pull 10) | 13.6 → 21.0 |

   Curves free per benchmark with a weaker pull toward the logistic (pull 1 or 0.1, quantile knots, item
   mixture, logit spline) **never settle**. They keep stretching the top of the axis: 28–37 points a year
   at round 80, still rising.
4. **Mechanism.** Logistic curves fitted on older models saturate too fast. Later models score above
   prediction where predicted scores are low and below it near the top. The last points toward 100% take
   more capability than the logistic credits, so recent frontier models sit higher under flexible curves.
   This is visible on OTIS Mock AIME in the npca page's one-benchmark viewer with the log-odds y axis.
5. **Important caveat, found at the end of the session and not yet written into the pages.** The two
   anchors, Claude 3.5 Sonnet ≡ 130 (Jun 2024) and GPT-5 ≡ 150 (Aug 2025), bracket almost the whole
   *previous* window. So agreement on ~13.5 points a year there is largely mechanical. The *last* window
   lies entirely above GPT-5's 150, where nothing pins the spacing except the curve's shape. With a curve
   free per benchmark, spacing there is not identified, and the acceleration number reflects the penalties,
   not the data. Only the direction (more acceleration than ECI, never less) is robust. Among curves that
   settle, the shared free shape (19.2) is the most defensible flexible answer.
6. **Floor/ceiling fix.** Unconstrained least squares put a benchmark's "ceiling" at the *average* score
   of the strongest models: 96% on OTIS Mock AIME, with 26 of 172 scores above it. It is now constrained to
   floor ≤ min score and ceiling ≥ max score, pulled toward 0/1 with weight `PULL = 1` (in
   `npca_links.py`). Complementary log-log was dropped at the user's request.
7. **Which benchmarks drive the gap** (`scripts/curve_fits.py`, `data/curve_leverage.json`). No single
   benchmark: leaving any one out keeps the npca-minus-logistic gap at 3.6–5.9 points a year. GPQA diamond
   is the only benchmark with a sizeable push toward more acceleration on both measures (leave-one-out
   and implied shift). OTIS Mock AIME is the most influential either way.

## Open questions and next steps (the user has been told about the first)

1. **Joint-fit forward test across pull strengths** (offered to the user, not yet run; ~15–30 min compute).
   Fit curves *and* positions on models released before Sep 2025, place later models from half their
   scores, predict the other half. Run for npca pull ∈ {0.1, 1, 3, 10, 30} and the shared shape.
   Extrapolating past the anchors is the one held-out test that depends on spacing above 150. If it favours
   a particular pull, that is real evidence on the size of the acceleration. Reuse `npca_build.forward_split`
   and `npca_accel.joint` (which takes `mi, bi, y` subsets); placing later models needs curves frozen, as in
   `npca_build.run_variant`.
2. **Write the anchor-window caveat (item 5) into the npca page and README.** Consider showing growth
   *beyond the upper anchor* explicitly. Consider an alternative anchor pair (e.g. a 2026 model as the
   upper anchor) as a sensitivity check: does the "acceleration" move with the anchors?
3. **Verify the npca CV tuning.** `npca_fit.py` says `LAM_SMOOTH = 30` and `LAM_SHRINK = 10` were "chosen by
   5-fold CV", but the tuning code is not in the repo. Either reproduce it or soften the claim. Note: CV on
   held-out scores is nearly blind to spacing (in-sample RMSE 0.0725 / 0.0698 / 0.0691 at pull 10 / 1 / 0.1
   while last-year growth goes 21 → 28 → 31), so it cannot validate the acceleration number anyway.
4. **Possibly:** report acceleration with a measure less sensitive to the frontier's running max (e.g. a
   trend through the top-k models per quarter), and add bootstrap intervals for the npca-minus-logistic
   *gap* itself rather than for each curve separately.
5. **Small known UI items:** benchmark-label leader lines on the dashboard can run long when a series ends
   at 1%; the "From" zoom keeps the slope-matched ECI axis fixed rather than re-centring.

## Map of the code

| File | What it does | Runtime |
|---|---|---|
| `scripts/build_data.py` | Epoch CSVs → `data/eci_data.json` (models, scores, labs, warm-start fit params) | seconds |
| `scripts/eci_fit.py`, `scripts/eci_fit.js` | Epoch's ECI objective by Levenberg–Marquardt (Python and in-browser; agree to 1e-4) | — |
| `scripts/npca_fit.py`, `scripts/npca_build.py` | Original npca joint fits, 2×2 (logistic/monotone × 1/2 factors), CV, bootstrap → `data/npca.json` | ~15 min |
| `scripts/npca_links.py` | Seven curve shapes, capability fixed, random + forward CV → `data/npca_links.json` | ~20 s |
| `scripts/npca_accel.py` | Joint fits per curve, growth paths by round, bootstrap → `data/npca_accel.json`; `--only key1,key2` refits some and merges | ~21 min full |
| `scripts/curve_fits.py` | Dashboard curves (θ + implied capability per score), leave-one-out leverage, implied shift → `data/curve_fits.json`, `data/curve_leverage.json`; `--only`, `--no-leverage`, `--shift-only` | ~6 min full |
| `scripts/*_figure.py`, `scripts/make_figure.py` | Static PNGs in `figures/` | seconds |
| `scripts/build_page.py`, `scripts/npca_build_page.py` | Embed JSON (+ solver) into the templates → `index.html`, `npca.html` | seconds |

Gotchas:
- macOS numpy/Accelerate prints spurious matmul warnings; harmless.
- Plotly in the dashboard is from jsDelivr; the static PNG is the fallback.
- To check the full-width layout visually from the in-app browser, render with `Plotly.toImage` and POST it
  to a tiny local server; the browser pane itself is too narrow to judge.
