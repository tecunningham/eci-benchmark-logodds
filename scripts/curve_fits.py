"""Capability under each benchmark-curve option, and the capability each score implies, for the main dashboard.

For every option whose joint fit settles (npca_accel.py), refit capability jointly with the curves (same
procedure, 80 rounds from published ECI) and store
  theta[m]        capability per model (ECI scale; Claude 3.5 Sonnet = 130, GPT-5 = 150)
  imp[b][i]       capability implied by the i-th score of benchmark b (same order as eci_data.json):
                  the score, pinned to [1%, 99%] like the log-odds view, mapped back through that benchmark's
                  own fitted curve. If the curve never reaches the score, the score is censored at the end of
                  the curve's range (flagged in cen).
Published ECI is included with Epoch's own difficulty and slope (edi_scores.csv): implied = edi + logit(y)/slope.

Also leave-one-benchmark-out: for the logistic and piecewise-linear curves, refit without each benchmark and
record the last-12-month frontier growth, to find which benchmarks drive the difference in acceleration.

Also, per benchmark: how much higher its own free curve puts last year's models than the logistic does,
relative to the year before (capability implied by each score, piecewise-linear minus published logistic).

Writes data/curve_fits.json (dashboard) and data/curve_leverage.json. `--shift-only` recomputes just that
last measure from existing files.
"""
import json
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import npca_accel as A
import npca_build as NB

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
RAW = NB.RAW
EPS = 0.01
SHOW = ["four_pl", "cloglog", "shared", "monotone"]   # options that settle, besides Epoch's published logistic


def implied(curve, ys, lo, hi):
    g = np.arange(lo, hi + 0.25, 0.25)
    v = np.maximum.accumulate(curve(g))
    out, cen = [], []
    for y in np.clip(ys, EPS, 1 - EPS):
        if y <= v[0]:
            out.append(g[0]); cen.append(-1)
        elif y >= v[-1]:
            out.append(g[np.argmax(v >= v[-1] - 1e-9)]); cen.append(1)
        else:
            k = np.searchsorted(v, y)            # v[k-1] < y <= v[k]
            j = k - 1
            while j > 0 and v[j - 1] == v[j]:    # start of a flat run: take the run's end
                j -= 1
            t = (y - v[k - 1]) / max(v[k] - v[k - 1], 1e-12)
            out.append(g[k - 1] + t * (g[k] - g[k - 1])); cen.append(0)
    return out, cen


def fit_variant(key):
    _, label, opt, par, _ = next(v for v in A.VARIANTS if v[0] == key)
    th, sse, _ = A.joint(opt, par, NB.MI, NB.BI, NB.Y, NB.NB, A.ITERS)
    curves = A.curves_for(opt, par, th, NB.MI, NB.BI, NB.Y, NB.NB)
    imp, cen = [], []
    for b, bd in enumerate(RAW["b"]):
        ys = np.array([q[1] for q in bd["p"]])
        o, c = implied(curves[b], ys, th.min() - 40, th.max() + 40)
        imp.append([round(float(x), 2) for x in o]); cen.append(c)
    s = A.stats(th)
    return dict(key=key, label=label, theta=[round(float(x), 2) for x in th], imp=imp, cen=cen,
                rmse=round(float(np.sqrt(sse / len(NB.Y))), 4), prev=round(s["prev"], 2), last=round(s["last"], 2))


def loo(args):
    key, drop = args
    _, _, opt, par, _ = next(v for v in A.VARIANTS if v[0] == key)
    keep = NB.BI != drop
    bi = NB.BI[keep]
    bi = np.where(bi > drop, bi - 1, bi)
    th, _, _ = A.joint(opt, par, NB.MI[keep], bi, NB.Y[keep], NB.NB - 1, 60)
    s = A.stats(th)
    return key, drop, s["prev"], s["last"]


def main(leverage=True):
    with ProcessPoolExecutor(8) as ex:
        fits = list(ex.map(fit_variant, SHOW))
        L = list(ex.map(loo, [(k, b) for k in ("logistic", "monotone") for b in range(NB.NB)])) if leverage else []
    E = pd.read_csv(ROOT / "data" / "epoch" / "edi_scores.csv").set_index("benchmark_name")
    pub_imp = []
    for bd in RAW["b"]:
        e, s = E.loc[bd["name"], "edi"], E.loc[bd["name"], "estimated_slope_scaled"]
        y = np.clip([q[1] for q in bd["p"]], EPS, 1 - EPS)
        pub_imp.append([round(float(e + np.log(v / (1 - v)) / s), 2) for v in y])
    out = dict(eps=EPS, variants=fits, published=dict(edi=[round(float(E.loc[b["name"], "edi"]), 3) for b in RAW["b"]],
               slope=[round(float(E.loc[b["name"], "estimated_slope_scaled"]), 5) for b in RAW["b"]], imp=pub_imp))
    json.dump(out, open(ROOT / "data" / "curve_fits.json", "w"), separators=(",", ":"))
    for f in fits:
        print(f"{f['label']:45s} rmse {f['rmse']:.4f}  prev {f['prev']:.1f}  last {f['last']:.1f}")
    if L:
        full = {v["key"]: v for v in json.load(open(ROOT / "data" / "npca_accel.json"))["variants"]}
        gap = full["monotone"]["last"] - full["logistic"]["last"]
        rows = []
        for b, bd in enumerate(RAW["b"]):
            lg = next(x for x in L if x[0] == "logistic" and x[1] == b)
            mo = next(x for x in L if x[0] == "monotone" and x[1] == b)
            rows.append(dict(name=bd["name"], area=bd["area"], n=len(bd["p"]),
                             logistic=round(lg[3], 2), monotone=round(mo[3], 2), gap=round(mo[3] - lg[3], 2),
                             leverage=round(gap - (mo[3] - lg[3]), 2)))
        rows.sort(key=lambda r: -r["leverage"])
        json.dump(dict(full_gap=round(gap, 2), full=dict(logistic=full["logistic"]["last"], monotone=full["monotone"]["last"]), rows=rows),
                  open(ROOT / "data" / "curve_leverage.json", "w"), separators=(",", ":"))
        print(f"\nfull gap (piecewise-linear minus logistic, last-12-month growth): {gap:.2f}")
        print(f"{'benchmark (dropped)':40s} {'n':>4s} {'logistic':>9s} {'pw-lin':>8s} {'gap':>6s} {'leverage':>9s}")
        for r in rows[:12] + [None] + rows[-5:]:
            if r is None:
                print("..."); continue
            print(f"{r['name'][:40]:40s} {r['n']:4d} {r['logistic']:9.1f} {r['monotone']:8.1f} {r['gap']:6.1f} {r['leverage']:+9.2f}")
    print("wrote data/curve_fits.json" + (", data/curve_leverage.json" if L else ""))


def implied_shift():
    """Per benchmark: mean(implied, piecewise-linear - logistic) over scores of models released in the last 12
    months, minus the same over the 12 months before. Positive: the logistic understates last year's gains there."""
    C = json.load(open(ROOT / "data" / "curve_fits.json"))
    W = [np.datetime64(w) for w in json.load(open(ROOT / "data" / "npca_accel.json"))["windows"]]
    mono = next(v for v in C["variants"] if v["key"] == "monotone")
    dates = np.array([m[2] for m in RAW["models"]], dtype="datetime64[D]")
    rows = []
    for k, b in enumerate(RAW["b"]):
        m = np.array([q[0] for q in b["p"]]); y = np.array([q[1] for q in b["p"]])
        gap = np.array(mono["imp"][k]) - np.array(C["published"]["imp"][k])
        last, prev = (dates[m] >= W[1]) & (dates[m] < W[2]), (dates[m] >= W[0]) & (dates[m] < W[1])
        if last.sum() >= 3 and prev.sum() >= 3:
            rows.append(dict(name=b["name"], area=b["area"], shift=round(float(gap[last].mean() - gap[prev].mean()), 2),
                             n_last=int(last.sum()), n_prev=int(prev.sum()), score_last=round(float(y[last].mean()), 3)))
    rows.sort(key=lambda r: -r["shift"])
    L = json.load(open(ROOT / "data" / "curve_leverage.json"))
    L["implied"] = rows
    json.dump(L, open(ROOT / "data" / "curve_leverage.json", "w"), separators=(",", ":"))
    for r in rows[:8]:
        print(f"{r['name'][:40]:40s} {r['shift']:+6.2f}  last-year scores {r['n_last']:3d}, mean {r['score_last']:.2f}")


if __name__ == "__main__":
    if "--shift-only" not in sys.argv:
        main(leverage="--no-leverage" not in sys.argv)
    implied_shift()
