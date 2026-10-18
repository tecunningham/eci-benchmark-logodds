"""Forward test of the joint fits: does a more flexible curve predict models above the upper anchor better?

The acceleration in npca_accel.py depends on how models are spaced above GPT-5 (= 150), where the anchors
pin nothing and only the curve shape decides. This is the one held-out test that touches that spacing:

  1. Joint fit (curves and positions, as npca_accel.joint) on models released before CUT only, starting from
     Epoch's ECI refit on those same scores (no later score enters through the start). Both anchors are
     released before CUT, so the scale is fixed the same way as in the full fits.
  2. Each later model is placed from a random half of its scores with the curves frozen (wide grid search,
     same weak prior, no re-anchoring). The frozen piecewise-linear curves are refit on knots reaching PAD
     points above the top training model; beyond the data the pull and smoothness penalties decide their
     shape, so they can rise past the top instead of going flat (which would cap every later model).
  3. The other half of its scores are predicted. Only benchmarks with >= 5 training scores count.

Variants: logistic, logistic + floor + ceiling, one shared free shape, and the npca piecewise-linear curve
at pulls towards the logistic of 0.1, 1, 3, 10 (the page default) and 30. Every variant runs the same
number of rounds (ITERS, as in npca_accel). Also reported: the frontier growth over the last 12 months
implied by the placed later models (curves fit only on earlier ones), next to the full-data value.

Writes data/npca_forward.json.
"""
import json
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import npca_accel as A
import npca_build as NB
import npca_fit as F

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
ITERS = A.ITERS
VARIANTS = [  # key, label, curve option, fit arguments
    ("logistic", "Logistic (ECI's curve)", "logistic", {}),
    ("four_pl", "Logistic + floor + ceiling", "four_pl", {}),
    ("shared", "One free shape shared by all benchmarks", "shared", {}),
    ("pull30", "Piecewise-linear, pull 30", "monotone", {"shrink": 30.0}),
    ("pull10", "Piecewise-linear, pull 10 (default)", "monotone", {"shrink": 10.0}),
    ("pull3", "Piecewise-linear, pull 3", "monotone", {"shrink": 3.0}),
    ("pull1", "Piecewise-linear, pull 1", "monotone", {"shrink": 1.0}),
    ("pull0.1", "Piecewise-linear, pull 0.1", "monotone", {"shrink": 0.1}),
]
TR, CA, TE, LATE = NB.forward_split()
PAD = 80   # how far above the top training model the frozen monotone curves extend (logistic-type curves extend anyway)


def place_new(th, curves, models, cells, spans=(100, 25, 6, 1.5), n=41):
    """Place each later model from its calibration cells, curves frozen, no re-anchoring."""
    th = th.copy()
    mean = th[np.isin(np.arange(NB.NM), NB.MI[TR])].mean()
    for m in models:
        r = [i for i in cells[NB.MI[cells] == m] if curves[NB.BI[i]] is not None]
        th[m] = 150.0
        if not r:
            th[m] = np.nan
            continue
        for span in spans:
            g = np.linspace(th[m] - span, th[m] + span, n)
            f = F.NOISE_VAR * ((g - mean) / F.PRIOR_SD[0]) ** 2
            for i in r:
                f = f + (curves[NB.BI[i]](g) - NB.Y[i]) ** 2
            th[m] = g[np.argmin(f)]
    return th


def run(v):
    key, _, opt, par = v
    mi, bi, y = NB.MI[TR], NB.BI[TR], NB.Y[TR]
    th = NB.eci_on(TR)[0]
    path = []
    for it in range(ITERS):
        c = A.curves_for(opt, par, th, mi, bi, y, NB.NB)
        th = A.place(th, c, mi, bi, y, NB.NM)
        if (it + 1) % 10 == 0:
            path.append(it + 1)
    c = A.curves_for(opt, par, th, mi, bi, y, NB.NB)
    if opt == "monotone":   # refit the frozen curves on a wide knot range so they can extrapolate past the top
        lo, hi = th.min() - 15, th.max() + PAD
        c = [F.fit_curve(th[mi[bi == b]], y[bi == b], lo, hi, "monotone", **par) if (bi == b).sum() >= 2 else None
             for b in range(NB.NB)]
    full = place_new(th, c, LATE, CA)
    pred = np.array([c[NB.BI[i]](full[NB.MI[i]]) if c[NB.BI[i]] is not None else np.nan for i in TE])
    s = A.stats(np.where(np.isfinite(full), full, -np.inf))
    return key, pred, full, s["prev"], s["last"]


def main():
    with ProcessPoolExecutor(3) as ex:
        res = {k: (p, th, pv, ls) for k, p, th, pv, ls in ex.map(run, VARIANTS)}
    y, groups = NB.Y[TE], NB.MI[TE]
    rmse = lambda e: float(np.sqrt(np.nanmean(e ** 2)))
    rng = np.random.default_rng(NB.SEED)
    g = np.unique(groups)
    idx = {m: np.flatnonzero(groups == m) for m in g}
    draws = [np.concatenate([idx[m] for m in rng.choice(g, len(g))]) for _ in range(400)]
    ref = res["logistic"][0]
    full_accel = {v["key"]: v for v in json.load(open(ROOT / "data" / "npca_accel.json"))["variants"]}
    accel_key = dict(logistic="logistic", four_pl="four_pl", shared="shared", pull10="monotone", pull1="monotone_weak",
                     **{"pull0.1": "monotone_free"})
    out = dict(cut=NB.CUT, iters=ITERS, n_test=len(TE), n_late=len(LATE), n_train=len(TR), variants=[])
    print(f"{'variant':42s} {'RMSE':>7s} {'vs logistic (90%)':>24s} {'bias by predicted score':>32s}  last-12 growth (forward / full)")
    for key, label, _, _ in VARIANTS:
        p, th, pv, ls = res[key]
        d = [100 * (rmse(p[r] - y[r]) / rmse(ref[r] - y[r]) - 1) for r in draws]
        bins = [0, .2, .5, .8, 1.01]
        bias = [round(float(np.nanmean((y - p)[(p >= bins[k]) & (p < bins[k + 1])])), 4) for k in range(4)]
        fa = full_accel.get(accel_key.get(key, ""), {})
        row = dict(key=key, label=label, rmse=round(rmse(p - y), 4),
                   d=[round(100 * (rmse(p - y) / rmse(ref - y) - 1), 2), round(float(np.percentile(d, 5)), 2), round(float(np.percentile(d, 95)), 2)],
                   bias=bias, prev_fwd=round(pv, 2), last_fwd=round(ls, 2),
                   prev_full=fa.get("prev"), last_full=fa.get("last"),
                   late=[[NB.NAMES[m], NB.DATES[m], None if not np.isfinite(th[m]) else round(float(th[m]), 2)] for m in LATE])
        out["variants"].append(row)
        print(f"{label:42s} {row['rmse']:7.4f} {row['d'][0]:+7.2f}% [{row['d'][1]:+.1f},{row['d'][2]:+.1f}]  "
              f"{' '.join(f'{b:+.3f}' for b in bias)}   {ls:5.1f} / {fa.get('last', float('nan')):5.1f}", flush=True)
    json.dump(out, open(ROOT / "data" / "npca_forward.json", "w"), separators=(",", ":"))
    print("wrote data/npca_forward.json")


if __name__ == "__main__":
    main()
