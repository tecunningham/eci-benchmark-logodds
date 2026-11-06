# Benchmark-level vs item-level logistics

ECI fits one logistic per **benchmark**: `score_mb = sigmoid(a_b (cap_m − d_b))`. Classic IRT puts the logistic on each **item**. A benchmark score is then an average of item logistics with spread-out difficulties (and slopes), which is not exactly logistic. This note asks how much that matters, whether the ECI data show it, and how a task-level ECI would work. Code: [`scripts/item_mixture_check.py`](scripts/item_mixture_check.py) → `data/item_mixture_check.json`.

## 1. What a mixture of item logistics looks like at benchmark level

"A mixture of logistics is flatter" is true but mostly harmless. The flattening is a lower slope, and ECI's free per-benchmark slope absorbs it. Only the *shape* left over after refitting a logistic is detectable. That residual shape depends on the mechanism, and different mechanisms push it in opposite directions.

Each benchmark curve below is built from 4,000 items with item slope 1, then fitted with a logistic. `γ_low`/`γ_high` are extra cubic log-odds terms on each side of the midpoint. Negative means that tail approaches 0%/100% **more slowly** than the logistic.

| Item-level mechanism | Fitted slope | Max score error of best logistic | γ_low | γ_high |
|---|---|---|---|---|
| Normal difficulties (sd 1.5) | 0.74 | 0.7 pts | +0.29 | +0.25 |
| Uniform difficulties (±3) | 0.66 | 1.4 pts | +0.67 | +0.69 |
| Bimodal difficulties (easy + hard halves) | 0.49 | 4.6 pts | +2.96 | +2.96 |
| Long right tail of hard items | 0.70 | 2.3 pts | +1.01 | −0.23 |
| Item slopes spread (lognormal sd 0.8) | 0.84 | 3.4 pts | −0.54 | −0.54 |
| 10% unsolvable items (mislabelled/broken) | 0.66 | 7.9 pts | +1.04 | −1.08 |
| 25% chance floor (3PL) | 0.45 | 13.7 pts | −4.19 | +5.41 |

- **Thin-tailed difficulty spreads** (normal, uniform, bimodal) make the curve flatter in the middle. In log-odds it is *steeper* in the tails, approaching 0% and 100% faster than the fitted logistic. A normal spread is almost exactly logistic: within 0.7 points, which is undetectable against model-level noise.
- **Slope heterogeneity, a tail of very hard items, or unsolvable items** make the top approach 100% *more slowly*. That is the direction of the forward-test miss in the README: later models score 10 points below the logistic above 80%.
- **Noise in estimated capability** convolves the curve with a normal distribution, exactly like a normal spread of difficulties. It biases the test toward "steeper tails", so a "flatter top" finding is conservative.

## 2. What the ECI data show

**Method.** For each benchmark, capabilities are refit by ECI's own objective *without that benchmark*, so the curve being tested doesn't also place the models. Then a logistic plus the two tail terms is fit to its scores. The sample is 42 benchmarks with ≥20 scores and a range above 30 points (2,579 scores).

**Findings:**

- **In sample, the logistic fits benchmark-level scores well, except at the very top.** Residual (score − logistic prediction) by predicted score:

  | Predicted | 0–5% | 5–15% | 15–30% | 30–50% | 50–70% | 70–85% | 85–95% | 95–100% |
  |---|---|---|---|---|---|---|---|---|
  | n | 171 | 288 | 408 | 523 | 602 | 370 | 150 | 67 |
  | mean residual (pts) | +0.4 | −0.5 | −0.1 | +0.4 | −0.5 | +0.6 | −0.3 | **−2.0 ± 0.6** |

- **Pooled tail shape:** γ_low +0.12 (90% interval −0.23 to +0.86), γ_high −0.21 (−0.37 to +1.31). The point estimates match "a tail of hard or unsolvable items": the bottom is steeper and the top flatter. Neither is distinguishable from zero across benchmarks.
- **Benchmarks disagree with each other.** The per-benchmark top tail is clearly flatter than logistic only for **GPQA diamond**. That fits its known share of questions with disputed answers: the "unsolvable items" row. OTIS Mock AIME and VPCT lean the same way. Several benchmarks lean steeper (WeirdML, DTBench, Fiction.LiveBench, Surface Evolver Bench, ProofBench), which fits a thin-tailed spread of difficulties. Treat per-benchmark top-tail estimates for benchmarks that never get near 100% as extrapolation.
- **No sign of the large signatures:** strongly bimodal composites (γ ≈ +3 on both sides) or chance floors (a large negative γ_low). The scores already appear to be chance-corrected.

**Why the in-sample signal is weak while the forward test is strong.** Benchmark-level data can only detect shape *differences between benchmarks*. If every benchmark saturates more slowly than a logistic in the same way, the capability axis stretches to absorb it: recent models move closer together at the top, and in-sample residuals stay small. That is the spacing non-identification in NEXT_STEPS item 5, seen from the item side. The forward test catches it only because it holds the axis fixed from earlier models. So benchmark-level data cannot settle whether the logistic understates top-end spacing. Item-level data can, because items within one benchmark at different difficulties pin the metric under a testable assumption.

## 3. Sketch: ECI estimated from task-level data

**Model (2PL with benchmark structure):**

    P(model m solves item j of benchmark b, run r) = sigmoid(a_j (θ_m + η_mb − d_j))
    d_j ~ G_b         (difficulty distribution per benchmark; normal, or a mixture with a mass at "unsolvable")
    log a_j ~ N(ν_b, ω_b²)
    η_mb ~ N(0, σ_b²) (model × benchmark effect: scaffold, format, contamination)

- **η_mb is essential.** Without it, thousands of correlated items per benchmark give absurdly small standard errors on θ. In effect, it says a benchmark is one noisy draw of a model's ability, however many items it has. σ_b is the benchmark-level noise that ECI's least squares currently treats as equal across benchmarks.
- **Multiple runs / partial credit:** binomial on k of n epochs; ordinal or beta likelihood for graded items.
- **Guessing:** a per-benchmark floor c_b for multiple-choice benchmarks that aren't chance-corrected.
- **Hybrid likelihood for benchmarks with only aggregate scores:** most of the 60 have no public per-item data. For those, the expected score is the item model integrated over the benchmark's item distribution, `s_mb = E_{(a,d)~G_b}[sigmoid(a(θ_m + η_mb − d))]`. That is a mixture-of-logistics curve with a few parameters per benchmark, fitted with noise `s(1−s)/n_b + σ_b²`. Item-level benchmarks pin the metric, and aggregate-only benchmarks ride along with curves whose shape is implied rather than assumed.
- **Anchors** as in ECI: Claude 3.5 Sonnet = 130 and GPT-5 = 150.

**Estimation.** A few hundred models × ~10–50k items × a few runs is a few million Bernoulli observations, sparse. Options:
- MAP + Laplace or variational inference in NumPyro/JAX with index arrays.
- Alternating joint maximum likelihood, like the repo's `npca_accel.joint`: given θ, each item is a 2-parameter logistic regression; given items, each model is a 1-D problem.

**Checks that become possible:**
1. **Item fit.** Per-item residuals against θ, and local dependence within benchmarks (Yen's Q3), to test whether the item-level logistic itself holds. This is the assumption the benchmark-level analysis can't reach.
2. **Unsolvable / mislabelled items.** Items no strong model solves show up as d_j → ∞. Dropping or modelling them should remove most of GPQA-style top-tail flattening, and shows how much of "slow saturation" is item quality rather than capability.
3. **Spacing above 150.** Rerun the forward test (`npca_forward.py` split): fit on models before Sep 2025, place later models from half their *items*, predict the other half. Then recompute last-12-month versus previous-12-month frontier growth. Unlike the per-benchmark free curves, this metric should settle, because hard items within a benchmark identify spacing.
4. **Unidimensionality.** Compare a bifactor model (θ_m plus a model × area factor) with one factor, at item level.

**Data to pilot with** (availability to be checked):
- METR's own task suite: run-level successes, already the basis of time horizons. Time horizons are themselves an item-level logistic with log human time as the difficulty covariate.
- Per-sample logs from Epoch's own benchmark runs (GPQA diamond, OTIS Mock AIME, FrontierMath, SWE-bench Verified), if Epoch shares them.
- Public per-instance results: the SWE-bench experiments repo, HELM per-instance outputs, LiveBench per-question results.

Five or so item-level benchmarks spanning easy to frontier difficulty, with the rest on the hybrid likelihood, would be enough to test points 2 and 3.
