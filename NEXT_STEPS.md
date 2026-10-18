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
   with capability held fixed. Held-out error is within about 2% of the logistic for six of them; isotonic is
   +3.0%. On later
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

   Curves free per benchmark with a weaker pull toward the logistic (pull 1 or 0.1, item mixture, logit
   spline) **never settle**. They keep stretching the top of the axis: 22–31 points a year at round 80, still
   rising (the logit spline jumps 16.6 → 21.3 between rounds 40 and 60). The quantile-knot curve has flattened
   near 36.7 by round 80.
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

## Added in the session of 18 Oct 2026 (validation pass)

- **Audit.** Two independent audits re-derived the numbers from the code and data:
  - **ECI reimplementation is exact.** It matches eci-public's objective term for term. Max |diff| against published ECI is 0.062, and Epoch's own code, run here, gets 0.011. scipy at tol 1e-15 agrees to 1.2e-4. The JS and Python solvers agree to about 1e-13.
  - **Tables match the json.** Every table in README matches its json, and the 80-round joint fits reproduce: logistic 13.24 → 17.03, monotone 13.63 → 21.04.
  - **Corrected:** NEXT_STEPS items 2 and 3 above, and README's "chiefly OTIS / GPQA / ARC-AGI" framing.
- **Window-end sensitivity (new, important).** Published ECI's 13.2 → 17.1 depends on the windows ending at the 1 Oct snapshot. It is 15.0 → 14.7 ending 1 Sep and 16.8 → 13.6 ending 1 Aug. The *gap* between curves is stable across end dates (Jun–Oct 2026), in points a year of extra last-year growth over the logistic:
  - floor + ceiling: +0.8 to +1.0
  - shared shape: +1.0 to +2.3
  - pull 10: +2.5 to +4.0
  - pull 1 / 0.1: +7 to +14

  Recompute it from the stored frontiers in `data/npca_accel.json`.
- **Anchor sensitivity.** With Claude Opus 5 (162.94) as the upper anchor, monotone gives 12.67 → 19.66 (gap over logistic 2.65, not 4.0); logistic is unchanged. The last/previous *ratio* barely moves: monotone ≈ 1.54, logistic 1.29. Prefer reporting ratios.
- **Forward test done** (`scripts/npca_forward.py` → `data/npca_forward.json`; open question 1 below):
  - **Result:** weaker pull → better prediction of later models.
    - Error against the logistic, in %: pull 30 −2.7, pull 10 −4.9, pull 3 −6.7, pull 1 −9.2, pull 0.1 −9.8.
    - Two other calibration splits (seeds 11, 23) agree: pull 0.1 −13.4 and −17.4.
    - Floor + ceiling −0.6. The shared shape is +8.5 (interval −1.8 to +21).
  - **Logistic's systematic miss:** later models score +0.13 above prediction where predicted < 20%, and −0.10 where predicted > 80%.
  - **What it means:** it favours exactly the curves that never settle, so it says the logistic's spacing above 150 is too compressed without pinning the right spacing.
  - **Ignore `prev_fwd` / `last_fwd`** in the json: frontier growth from forward-placed models is 60–80 points a year for every curve, which is placement noise.
- **Bug found in `npca_build.run_variant`'s forward CV:** `Curve` is flat outside its knots, and that applies to the "logistic" kind too, so every later model is capped at about 152. README now says so. `npca_forward.py` refits frozen monotone curves on knots reaching 80 above the top. Its logistic-type curves (from `npca_links`) are true functions and extrapolate.
- **CV tuning reproduced** in `scripts/npca_tune.py` (open question 3 below):
  - **The curve-penalty surface is flat.** Random 5-fold RMSE runs 0.0926–0.0940 over smoothness {3…300} × pull {1…100}. The stated (30, 10) gives 0.0929; the minimum is (100, 3) at 0.0926.
  - **Spacing varies along that surface.** The auditor's joint fits give last-12-month growth of 28.1 at (100, 3), 23.5 at (100, 10) and 24.1 at (30, 3), against 21.0 at (30, 10). So CV can't choose the pull, and the "21" is a choice; docs now say so.
  - **Two-factor priors reproduce exactly:** (axis-2 sd 3, angle sd 15°) 0.0938 is best. 6/15° gives 0.0953, 6/30° 0.0968, 12/30° 0.0991, and the logistic at 3/15° 0.0952. Looser priors are steadily worse and approach the one-factor fit (0.0929) only by switching the second axis off, so the data don't support a second factor.
- **Other audit findings, not yet acted on:**
  - **`place()` prior in `npca_accel.py`.** It adds about 0.6 to the monotone − logistic gap: without it, 16.9 vs 20.3.
  - **Knot padding.** The ±15 pad changes monotone last-year growth: 20.7 at pad 3, 22.1 at pad 40. The npca page's frontier chart uses `npca.json` θ (±2 pad, at most 25 iterations), so it shows less stretch than the acceleration section.
  - **Leverage baseline.** Leave-one-out leverage in `curve_fits.py` uses 60-round refits against an 80-round baseline: every leverage is shifted about −0.09, comparable to the top contributors' size.
  - **One model carries the last-year number.** It is essentially Claude Opus 5.5's position minus about 150. The benchmark bootstrap doesn't resample models, so model-level noise isn't in any interval. Records with 4–7 benchmarks (GPT-5.3 Codex, GPT-5.2 Pro, GPT-5 Pro) drive part of ECI's own speed-up. Frontier of models with ≥ 8 benchmarks: 14.6 → 15.8.
  - **Small issues:** dead code at `curve_fits.py` lines 56–59. A model with every benchmark dropped in a bootstrap keeps its starting value (about 2% for 4-benchmark models).
- **Dashboard hover now shows each score's weight** in its model's capability: the curve's slope at the model's capability, squared, over the sum across that model's scores.
  - Slopes for the non-ECI curves are in `curve_fits.json` as `w` (`curve_fits.py --weights-only` adds them from the stored θ without refitting). ECI's are computed in the page from difficulty and slope, published or refit.
  - **Check:** these weights rebuild each model's capability as a weighted average of its score-implied capabilities, to a median of 0.12 points (90th percentile 0.8; 0.3 / 1.9 for the shared shape).
  - **Example:** Claude Opus 5.5's 87.5% on GPQA diamond implies 151.6 but has <0.1% weight, because the logistic is flat at 167.
- **`curve_fits.py` rerun on Linux:** four_pl and monotone reproduce bit for bit. The shared-shape fit moves one model by up to 2.2 points, but growth agrees (13.29 → 19.24 against 19.19 stored). The stored file was kept.
- **Scores of exactly 100%.** There are only 12 (and 90 of 0%). The fit predicts 93–100% for them; they carry 0.1% of the squared error and, on average, about a fifth of the pull on capability of a typical score. Score-space least squares makes near-ceiling misses cheap, which is part of why the logistic can saturate too fast at little cost.

## Open questions and next steps (the user has been told about the first)

1. **Done (18 Oct): see above.** Joint-fit forward test across pull strengths. Original note:
   Fit curves *and* positions on models released before Sep 2025, place later models from half their
   scores, predict the other half. Run for npca pull ∈ {0.1, 1, 3, 10, 30} and the shared shape.
   Extrapolating past the anchors is the one held-out test that depends on spacing above 150. If it favours
   a particular pull, that is real evidence on the size of the acceleration. Reuse `npca_build.forward_split`
   and `npca_accel.joint` (which takes `mi, bi, y` subsets); placing later models needs curves frozen, as in
   `npca_build.run_variant`.
2. **Write the anchor-window caveat (item 5) into the npca page and README.** Consider showing growth
   *beyond the upper anchor* explicitly. Consider an alternative anchor pair (e.g. a 2026 model as the
   upper anchor) as a sensitivity check: does the "acceleration" move with the anchors?
3. **Done (18 Oct): `scripts/npca_tune.py`; see above.** Verify the npca CV tuning. Note: CV on
   held-out scores is nearly blind to spacing (in-sample RMSE 0.0725 / 0.0698 / 0.0691 at pull 10 / 1 / 0.1
   while last-year growth goes 21 → 28 → 31), so it cannot validate the acceleration number anyway.
4. **Possibly:** report acceleration with a measure less sensitive to the frontier's running max (e.g. a
   trend through the top-k models per quarter), and add bootstrap intervals for the npca-minus-logistic
   *gap* itself rather than for each curve separately.
5. **Measure growth more robustly.** Report results for several window ends, or for a trend fit, not just the windows ending at the snapshot. Bootstrap over *models* as well as benchmarks. Report last/previous ratios.
6. **Fix the knot-padding / iteration mismatch** between `npca.json` (page frontier chart) and `npca_accel.py`. Make `Curve` extrapolate beyond its knots (logistic continuation) in `npca_fit.py`, so `npca_build`'s forward CV stops capping at 152.
7. **Small known UI items:** benchmark-label leader lines on the dashboard can run long when a series ends
   at 1%; the "From" zoom keeps the slope-matched ECI axis fixed rather than re-centring.

## Map of the code

| File | What it does | Runtime |
|---|---|---|
| `scripts/build_data.py` | Epoch CSVs → `data/eci_data.json` (models, scores, labs, warm-start fit params) | seconds |
| `scripts/eci_fit.py`, `scripts/eci_fit.js` | Epoch's ECI objective by Levenberg–Marquardt (Python and in-browser; agree to 1e-4) | — |
| `scripts/npca_fit.py`, `scripts/npca_build.py` | Original npca joint fits, 2×2 (logistic/monotone × 1/2 factors), CV, bootstrap → `data/npca.json` | ~15 min |
| `scripts/npca_links.py` | Seven curve shapes, capability fixed, random + forward CV → `data/npca_links.json` | ~20 s |
| `scripts/npca_forward.py` | Joint fits on pre-Sep-2025 models; place later models from half their scores; predict the rest; 8 curves → `data/npca_forward.json` | ~6 min (3 cores) |
| `scripts/npca_tune.py` | Reproduces the 5-fold CV behind `npca_fit.py`'s penalties and two-factor priors; prints only | ~35 min (3 cores) |
| `scripts/npca_accel.py` | Joint fits per curve, growth paths by round, bootstrap → `data/npca_accel.json`; `--only key1,key2` refits some and merges | ~21 min full |
| `scripts/curve_fits.py` | Dashboard curves (θ + implied capability per score), leave-one-out leverage, implied shift → `data/curve_fits.json`, `data/curve_leverage.json`; `--only`, `--no-leverage`, `--shift-only` | ~6 min full |
| `scripts/*_figure.py`, `scripts/make_figure.py` | Static PNGs in `figures/` | seconds |
| `scripts/build_page.py`, `scripts/npca_build_page.py` | Embed JSON (+ solver) into the templates → `index.html`, `npca.html` | seconds |

Gotchas:
- macOS numpy/Accelerate prints spurious matmul warnings; harmless.
- Plotly in the dashboard is from jsDelivr; the static PNG is the fallback.
- To check the full-width layout visually from the in-app browser, render with `Plotly.toImage` and POST it
  to a tiny local server; the browser pane itself is too narrow to judge.
