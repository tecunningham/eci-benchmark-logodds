"""Is each benchmark's curve logistic, or does it look like a mixture of item-level logistics?

ECI assumes score_mb = sigmoid(a_b (cap_m - d_b)). If instead each *item* is logistic, a benchmark score is
an average of item logistics with spread-out difficulties (and slopes), which is not exactly logistic.

1. Theory: build benchmark curves from item-level mechanisms, fit a logistic, and record the tail signature
   (gamma_low, gamma_high): extra cubic terms in log-odds on each side of the curve's midpoint.
   Convention: negative gamma = that tail approaches 0% / 100% more slowly than the logistic.
2. Data: capability for each benchmark is refit by ECI's own objective *without that benchmark*
   (leave-one-benchmark-out, cached in data/lobo_cap.npy; ~5 min on 4 cores), so the curve tested
   does not also place the models. Then fit each benchmark's logistic + tail terms on those capabilities.

Writes data/item_mixture_check.json. Run from the repo root:  python3 scripts/item_mixture_check.py
"""
import json, os, sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(__file__))
import eci_fit

sig = lambda z: 1 / (1 + np.exp(-z))
D = json.load(open("data/eci_data.json")); F = D["fit"]
NAMES = [m[0] for m in D["models"]]; NM, NB = len(NAMES), len(D["b"])
MI, BI, Y = map(np.array, zip(*[(m, j, s) for j, b in enumerate(D["b"]) for m, s in b["p"]]))
CAP0, DIF0, DIS0 = map(np.array, (F["cap"], F["dif"], F["dis"]))
ANCHOR = [b["name"] for b in D["b"]].index(F["anchor"])


def drop(j):
    """ECI fit without benchmark j; capabilities mapped back onto the full fit's raw scale via the anchors."""
    keep = BI != j
    ms = np.unique(MI[keep]); idx = {m: k for k, m in enumerate(ms)}
    bs = np.array([k for k in range(NB) if k != j]); bidx = {b: k for k, b in enumerate(bs)}
    a = bidx[ANCHOR] if j != ANCHOR else 0
    c, _, _ = eci_fit.fit(Y[keep], np.array([idx[m] for m in MI[keep]]), np.array([bidx[b] for b in BI[keep]]),
                          len(ms), len(bs), a, anchor_disc=DIS0[bs[a]], x0=np.r_[CAP0[ms], DIF0[bs], DIS0[bs]])
    out = np.full(NM, np.nan); out[ms] = c
    lo, hi = NAMES.index(eci_fit.ANCHOR_LOW[0]), NAMES.index(eci_fit.ANCHOR_HIGH[0])
    return cap_scale(out, lo, hi)


def cap_scale(out, lo, hi):
    return CAP0[lo] + (CAP0[hi] - CAP0[lo]) / (out[hi] - out[lo]) * (out - out[lo])


def tails(u):
    return (np.minimum(u, 0) / 3) ** 3, (np.maximum(u, 0) / 3) ** 3


def fit_tails(u, y):
    lo, hi = tails(u)
    return least_squares(lambda q: sig(q[0] + q[1] * u + q[2] * lo + q[3] * hi) - y, [0, 1, 0, 0]).x[2:]


def theory():
    rng = np.random.default_rng(0); th = np.linspace(-6, 6, 241); N = 4000
    def bench(d, a=None):
        a = np.ones_like(d) if a is None else a
        return sig(a[None] * (th[:, None] - d[None])).mean(1)
    mech = {"normal difficulties (sd 1.5)": bench(rng.normal(0, 1.5, N)),
            "uniform difficulties (+-3)": bench(rng.uniform(-3, 3, N)),
            "bimodal difficulties (+-2.5)": bench(np.r_[rng.normal(-2.5, .5, N // 2), rng.normal(2.5, .5, N // 2)]),
            "long tail of hard items (gamma)": bench(rng.gamma(1.5, 1.5, N) - 2),
            "item slopes spread (lognormal sd .8)": bench(rng.normal(0, .5, N), np.exp(rng.normal(0, .8, N))),
            "10% unsolvable items": .9 * bench(rng.normal(0, 1, N)),
            "25% chance floor (3PL)": .25 + .75 * bench(rng.normal(0, 1, N))}
    out = {}
    for k, y in mech.items():
        m = (y > .02) & (y < .98)
        f = least_squares(lambda p: sig(p[0] * (th[m] - p[1])) - y[m], [1, 0]).x
        err = np.abs(sig(f[0] * (th[m] - f[1])) - y[m]).max()
        gl, gh = fit_tails(f[0] * (th[m] - f[1]), y[m])
        out[k] = dict(fitted_slope=f[0], max_score_err=err, gamma_low=gl, gamma_high=gh)
        print(f"  {k:38s} slope {f[0]:.2f}  max|err| {err:.3f}  low {gl:+6.2f}  high {gh:+6.2f}")
    return out


def pooled(Bs):
    n = len(Bs)
    def res(q):
        return np.concatenate([sig(q[2 * i] + q[2 * i + 1] * b["u"] + q[-2] * b["lo"] + q[-1] * b["hi"]) - b["y"]
                               for i, b in enumerate(Bs)])
    return least_squares(res, np.r_[np.tile([0, 1.], n), 0, 0]).x[-2:]


def main():
    print("THEORY: item-level mechanism -> benchmark curve -> logistic fit (item slope 1)")
    th = theory()
    path = "data/lobo_cap.npy"
    if not os.path.exists(path):
        with ProcessPoolExecutor() as ex:
            np.save(path, np.array(list(ex.map(drop, range(NB)))))
    T = np.load(path)
    a0, s0 = eci_fit.to_eci(CAP0, NAMES)
    B = []
    for j, b in enumerate(D["b"]):
        m = np.array([p[0] for p in b["p"]]); y = np.clip([p[1] for p in b["p"]], 1e-3, 1 - 1e-3)
        t = a0 + s0 * T[j, m]; ok = np.isfinite(t)
        if ok.sum() >= 20 and np.ptp(y) > .3:
            t, y = t[ok], y[ok]; c = t.mean()
            p = least_squares(lambda p: sig(p[0] * (t - c) + p[1]) - y, [.1, 0]).x
            u = p[0] * (t - c) + p[1]; lo, hi = tails(u)
            B.append(dict(name=b["name"], y=y, u=u, lo=lo, hi=hi))
    rng = np.random.default_rng(2)
    g = pooled(B); bs = np.array([pooled([B[i] for i in rng.integers(0, len(B), len(B))]) for _ in range(200)])
    print(f"\nDATA ({len(B)} benchmarks with >=20 scores and range > 30 pts, leave-one-benchmark-out capability)")
    print(f"  pooled  low {g[0]:+.2f} [90% {np.quantile(bs[:, 0], .05):+.2f}, {np.quantile(bs[:, 0], .95):+.2f}]"
          f"   high {g[1]:+.2f} [90% {np.quantile(bs[:, 1], .05):+.2f}, {np.quantile(bs[:, 1], .95):+.2f}]")
    per = []
    for b in B:
        n = len(b["y"]); gl, gh = fit_tails(b["u"], b["y"])
        bb = np.array([fit_tails(b["u"][i], b["y"][i]) for i in (rng.integers(0, n, n) for _ in range(100))])
        per.append(dict(name=b["name"], n=n, gamma_low=gl, gamma_high=gh, low_ci=list(np.quantile(bb[:, 0], [.05, .95])),
                        high_ci=list(np.quantile(bb[:, 1], [.05, .95])), max_score=float(b["y"].max())))
    print("  benchmarks whose top tail is clearly flatter than logistic (90% CI < 0):",
          ", ".join(r["name"] for r in per if r["high_ci"][1] < 0))
    print("  ... clearly steeper (CI > 0):", ", ".join(r["name"] for r in per if r["high_ci"][0] > 0))
    p = np.concatenate([sig(b["u"]) for b in B]); y = np.concatenate([b["y"] for b in B]); bands = []
    print("  score - logistic prediction, by predicted score:")
    for lo, hi in [(0, .05), (.05, .15), (.15, .3), (.3, .5), (.5, .7), (.7, .85), (.85, .95), (.95, 1)]:
        k = (p >= lo) & (p < hi); r = y[k] - p[k]; se = r.std() / np.sqrt(k.sum())
        bands.append(dict(lo=lo, hi=hi, n=int(k.sum()), mean=r.mean(), se=se))
        print(f"    {lo:4.0%}-{hi:4.0%}  n={k.sum():4d}  {r.mean():+.3f} +- {1.64 * se:.3f}")
    json.dump(dict(theory=th, pooled=dict(gamma_low=g[0], gamma_high=g[1],
                                          low_ci=list(np.quantile(bs[:, 0], [.05, .95])),
                                          high_ci=list(np.quantile(bs[:, 1], [.05, .95]))),
                   per_benchmark=per, bands=bands),
              open("data/item_mixture_check.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
