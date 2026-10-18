"""Does the choice of benchmark curve change how fast frontier capability is growing, and whether it is accelerating?

For each curve option in npca_links.py, capability is re-estimated jointly with the curves:
    repeat ITERS times: fit every benchmark's curve on current theta -> place every model by grid search
            (given the curves, weak N(mean, 25^2) prior as in npca_fit.place) -> affine re-anchor so
            Claude 3.5 Sonnet = 130 and GPT-5 = 150
starting from Epoch's published ECI. The frontier's growth is recorded after every iteration, because with a
curve that is free per benchmark the spacing of models is not identified: such fits keep stretching the top
of the axis, and where they stop depends on the penalties, not the data. Options whose growth settles are
bootstrapped (benchmarks resampled with replacement); the rest are reported as trajectories only. Isotonic
curves are left out: step functions give a model no direction to move in, so placement just keeps the start.

Frontier: running maximum by release date from GPT-4 on, straight lines between records, flat after the last.
Growth: over the last 12 months to the data snapshot and the 12 months before.

Writes data/npca_accel.json.
"""
import json
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.optimize import nnls

import npca_build as NB
import npca_fit as F
import npca_links as LKS

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
NAMES, DATES = NB.NAMES, np.array(NB.DATES, dtype="datetime64[D]")
START, END = np.datetime64("2023-03-14"), np.datetime64(NB.RAW["snapshot"])
W = [END - 730, END - 365, END]           # previous 12 months, last 12 months
LOW, HIGH = NAMES.index(F.ANCHOR_LOW[0]), NAMES.index(F.ANCHOR_HIGH[0])
ITERS, BOOT_ITERS, BOOT = 80, 60, 100
OPTS = {o[0]: o for o in LKS.OPTIONS}
VARIANTS = [  # key, label, curve option, extra fit arguments, settles (bootstrapped)?
    ("logistic", "Logistic (ECI's curve)", "logistic", {}, True),
    ("four_pl", "Logistic + floor + ceiling", "four_pl", {}, True),
    ("shared", "One free shape shared by all benchmarks", "shared", {}, True),
    ("monotone", "Piecewise-linear monotone (npca, pull 10)", "monotone", {}, True),
    ("logit_spline", "Monotone spline in logit space", "logit_spline", {"lam": 1.0}, False),
    ("monotone_weak", "Piecewise-linear, pull 1", "monotone", {"shrink": 1.0}, False),
    ("monotone_free", "Piecewise-linear, pull 0.1", "monotone", {"shrink": 0.1}, False),
    ("monotone_q", "Piecewise-linear, knots at model quantiles (pull 10)", "monotone_q", {}, False),
    ("item_mixture", "Mixture of item difficulties", "item_mixture", {"s": 0.6, "lam": 0.02}, False),
]


def fit_q(x, y, knots, shrink=F.LAM_SHRINK, smooth=F.LAM_SMOOTH):
    """npca_fit.fit_curve with given (uneven) knots: smoothness penalises changes in slope per unit theta."""
    a, d = F.fit_logistic(x, y)
    base, w = F.sig(a * (knots - d)), np.diff(knots)
    n = len(w)
    A = np.c_[np.ones(len(x)), np.clip((x[:, None] - knots[None, :-1]) / w[None, :], 0, 1)]
    D = np.zeros((n - 1, n))
    for k in range(n - 1):
        D[k, k], D[k, k + 1] = -1 / w[k], 1 / w[k + 1]
    D *= np.median(w)
    c, _ = nnls(np.vstack([A, np.c_[np.zeros((n - 1, 1)), np.sqrt(smooth) * D], np.sqrt(shrink) * np.eye(n + 1)]),
                np.r_[y, np.zeros(n - 1), np.sqrt(shrink) * np.r_[base[0], np.diff(base)]], maxiter=3000)
    return F.Curve(knots, c[0] + np.r_[0, np.cumsum(c[1:])], (a, d))


def curves_for(opt, par, th, mi, bi, y, nb):
    lo, hi = th.min() - 15, th.max() + 15
    if opt == "shared":
        ab, Gv = LKS.shared(th, mi, bi, y, nb)
        return [lambda t, b=b: np.interp(ab[b, 0] * (t - ab[b, 1]), LKS.ZK, Gv) for b in range(nb)]
    if opt == "monotone_q":
        q = np.quantile(th[mi], np.linspace(0, 1, F.NKNOT - 2))
        kn = np.unique(np.r_[lo, q[1:-1], hi])
    out = []
    for b in range(nb):
        r = bi == b
        if r.sum() < 2:
            out.append(None)
        elif opt == "monotone":
            out.append(F.fit_curve(th[mi[r]], y[r], lo, hi, "monotone", **par))
        elif opt == "monotone_q":
            out.append(fit_q(th[mi[r]], y[r], kn, **par))
        else:
            out.append(OPTS[opt][2](th[mi[r]], y[r], lo, hi, **par))
    return out


def place(th, curves, mi, bi, y, nm, spans=(30, 6, 1.2), n=41):
    mean, new = th.mean(), th.copy()
    for m in range(nm):
        r = [i for i in np.flatnonzero(mi == m) if curves[bi[i]] is not None]
        if not r:
            continue
        for span in spans:
            g = np.linspace(new[m] - span, new[m] + span, n)
            f = F.NOISE_VAR * ((g - mean) / F.PRIOR_SD[0]) ** 2
            for i in r:
                f = f + (curves[bi[i]](g) - y[i]) ** 2
            new[m] = g[np.argmin(f)]
    s = 20 / (new[HIGH] - new[LOW])
    return 130 + s * (new - new[LOW])


def joint(opt, par, mi, bi, y, nb, iters, track=False):
    th, path = NB.ECI.copy(), []
    for _ in range(iters):
        c = curves_for(opt, par, th, mi, bi, y, nb)
        th = place(th, c, mi, bi, y, NB.NM)
        if track:
            s = stats(th)
            path.append([round(s["prev"], 2), round(s["last"], 2)])
    c = curves_for(opt, par, th, mi, bi, y, nb)
    sse = sum(float(np.sum((c[b](th[mi[bi == b]]) - y[bi == b]) ** 2)) for b in range(nb) if c[b] is not None)
    return th, sse, path


def frontier(th):
    """Records: running max by release date from GPT-4 on (one model per date, the highest)."""
    idx = np.flatnonzero((DATES >= START) & np.isfinite(th))
    best, rec = -np.inf, []
    for d in np.unique(DATES[idx]):
        k = idx[DATES[idx] == d]
        m = k[np.argmax(th[k])]
        if th[m] > best:
            best = th[m]
            rec.append(m)
    return rec


def at(rec, th, t):
    """Frontier value at day t: straight lines between records, flat after the last."""
    return float(np.interp(np.asarray(t, dtype="datetime64[D]").astype(float), DATES[rec].astype(float), th[rec]))


def stats(th):
    rec = frontier(th)
    f = [at(rec, th, t) for t in W]
    return dict(prev=f[1] - f[0], last=f[2] - f[1], rec=rec)


def boot_job(args):
    key, seed = args
    _, _, opt, par, _ = next(v for v in VARIANTS if v[0] == key)
    rng = np.random.default_rng(seed)
    mi, bi, y = [], [], []
    for new, b in enumerate(rng.choice(NB.NB, NB.NB, replace=True)):
        r = np.flatnonzero(NB.BI == b)
        mi += list(NB.MI[r]); bi += [new] * len(r); y += list(NB.Y[r])
    th, _, _ = joint(opt, par, np.array(mi), np.array(bi), np.array(y), NB.NB, BOOT_ITERS)
    s = stats(th)
    return key, s["prev"], s["last"]


def full_job(v):
    key, _, opt, par, _ = v
    th, sse, path = joint(opt, par, NB.MI, NB.BI, NB.Y, NB.NB, ITERS, track=True)
    return key, th, sse, path


def forward_bias():
    """Later models vs curves fit on earlier ones (as in npca_links): mean residual by predicted score."""
    tr, ca, te, _ = NB.forward_split()
    th = NB.eci_on(np.r_[tr, ca])[0]
    bins = [0, .2, .5, .8, 1.01]
    out = {}
    for key in ("logistic", "monotone"):
        p = LKS.predict_cells(th, tr, te, key, OPTS[key][2], {})
        r = NB.Y[te] - p
        out[key] = [dict(lo=bins[k], hi=min(bins[k + 1], 1), n=int(((p >= bins[k]) & (p < bins[k + 1])).sum()),
                         resid=round(float(np.nanmean(r[(p >= bins[k]) & (p < bins[k + 1])])), 4)) for k in range(4)]
    return out


def main(only=None):
    """only: refit just these variant keys and merge them into the existing data/npca_accel.json."""
    sel = [v for v in VARIANTS if not only or v[0] in only]
    with ProcessPoolExecutor(8) as ex:
        full = {k: (th, sse, path) for k, th, sse, path in ex.map(full_job, sel)}
        boots = list(ex.map(boot_job, [(v[0], 1000 + i) for v in sel if v[4] for i in range(BOOT)]))
    pub = stats(NB.ECI)
    out = dict(windows=[str(w) for w in W], iters=ITERS, boot=BOOT, boot_iters=BOOT_ITERS, variants=[],
               published=dict(prev=round(pub["prev"], 2), last=round(pub["last"], 2),
                              frontier=[[str(DATES[m]), NAMES[m], round(float(NB.ECI[m]), 2)] for m in pub["rec"]]),
               bias=forward_bias())
    for key, label, opt, par, settles in sel:
        th, sse, path = full[key]
        s = stats(th)
        b = np.array([(p, l) for k, p, l in boots if k == key])
        ci = None
        if len(b):
            ci = dict(prev=np.percentile(b[:, 0], [5, 95]).round(2).tolist(), last=np.percentile(b[:, 1], [5, 95]).round(2).tolist(),
                      diff=np.percentile(b[:, 1] - b[:, 0], [5, 95]).round(2).tolist(), p_accel=round(float((b[:, 1] > b[:, 0]).mean()), 3))
        out["variants"].append(dict(
            key=key, label=label, settles=settles, rmse=round(float(np.sqrt(sse / len(NB.Y))), 4),
            prev=round(s["prev"], 2), last=round(s["last"], 2), ci=ci, path=path,
            frontier=[[str(DATES[m]), NAMES[m], round(float(th[m]), 2)] for m in s["rec"]]))
        print(f"{label:55s} rmse {np.sqrt(sse/len(NB.Y)):.4f}  prev12 {s['prev']:6.1f}  last12 {s['last']:6.1f}  "
              f"at iter 20/40/{ITERS}: {path[19][1]:.1f}/{path[39][1]:.1f}/{path[-1][1]:.1f}"
              + (f"  diff 90% [{ci['diff'][0]:+.1f},{ci['diff'][1]:+.1f}] P(accel) {ci['p_accel']:.2f}" if ci else ""), flush=True)
    print(f"{'Published ECI':55s}              prev12 {pub['prev']:6.1f}  last12 {pub['last']:6.1f}")
    print("forward bias:", out["bias"])
    if only:
        old = json.load(open(ROOT / "data" / "npca_accel.json"))
        new = {v["key"]: v for v in old["variants"]} | {v["key"]: v for v in out["variants"]}
        out["variants"] = [new[v[0]] for v in VARIANTS if v[0] in new]
    json.dump(out, open(ROOT / "data" / "npca_accel.json", "w"), separators=(",", ":"))
    print("wrote data/npca_accel.json")


if __name__ == "__main__":
    import sys
    main(sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None)
