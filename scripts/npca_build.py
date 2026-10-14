"""Fit the nonparametric ECI variants, cross-validate them, and write data/npca.json for npca.html.

Variants (see npca_fit.py): {logistic, monotone} curve x {k = 1, k = 2} model coordinates.
  - full fits on every score
  - random 5-fold CV over cells (stratified by model, so each model keeps >= 3 training scores)
  - forward CV: curves fit on models released before CUT; each later model is placed using half of its
    scores (curves frozen) and the other half are predicted. This tests extrapolation past each
    benchmark's training support, where a free monotone curve has nothing to go on.
  - bootstrap over models (k = 1 monotone) for bands around each benchmark's curve
Every fit starts from Epoch's ECI fitted on the same training cells (eci_fit.py), so no test score leaks
in through the starting point. Takes a few minutes on 4 cores.
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import eci_fit
import npca_fit as F

ROOT = Path(__file__).resolve().parents[1]
RAW = json.load(open(ROOT / "data" / "eci_data.json"))
NAMES = [m[0] for m in RAW["models"]]
DATES = [m[2] for m in RAW["models"]]
ECI = np.array([m[3] for m in RAW["models"]])
BEN = RAW["b"]
MI = np.array([q[0] for b in BEN for q in b["p"]])
BI = np.array([k for k, b in enumerate(BEN) for q in b["p"]])
Y = np.array([q[1] for b in BEN for q in b["p"]])
NM, NB = len(NAMES), len(BEN)
ANCHOR = [b["name"] for b in BEN].index("Winogrande")
VARIANTS = [(1, "logistic"), (1, "monotone"), (2, "logistic"), (2, "monotone")]
VKEY = ["k1_logistic", "k1_monotone", "k2_logistic", "k2_monotone"]
CUT = "2025-09-01"
FOLDS, NBOOT, SEED = 5, 40, 7
GRID = np.arange(50, 180.5, 1.0)   # common theta grid for k = 1 curves
LIGHT = dict(smooth=1.0, shrink=0.1)   # lightly penalised curves, to show where the data alone would bend


def eci_on(rows):
    """Epoch's ECI refit on the given cells: (eci scale theta per model, prediction function)."""
    cap, dif, dis = eci_fit.fit(Y[rows], MI[rows], BI[rows], NM, NB, ANCHOR)
    a, s = eci_fit.to_eci(cap, NAMES)
    return a + s * cap, lambda mi, bi: 1 / (1 + np.exp(-dis[bi] * (cap[mi] - dif[bi])))


def run_variant(args):
    rows, test, k, kind, new_models, calib = args
    D = F.Data(MI[rows], BI[rows], Y[rows], NM, NB, NAMES)
    theta0, _ = eci_on(rows)
    r = F.fit(D, theta0, k=k, kind=kind)
    U = r["U"]
    if new_models is not None:          # forward CV: place later models from their calibration half
        C = F.Data(MI[calib], BI[calib], Y[calib], NM, NB, NAMES)
        U = U.copy()
        U[new_models] = [130.0, 0.0]
        U = F.place(C, U, r["alpha"], r["curves"], new_models, k, r["mean"], spans=F.WIDE)
    return F.predict(U, r["alpha"], r["curves"], MI[test], BI[test])


def folds():
    rng = np.random.default_rng(SEED)
    f = np.empty(len(Y), int)
    for m in range(NM):                 # spread each model's cells over the folds
        r = np.flatnonzero(MI == m)
        f[r] = rng.permutation(np.arange(len(r)) % FOLDS)
    return f


def forward_split():
    rng = np.random.default_rng(SEED)
    late = np.array([DATES[m] >= CUT for m in MI])
    train = np.flatnonzero(~late)
    nb_train = np.bincount(BI[train], minlength=NB)
    calib, test = [], []
    for m in sorted(set(MI[late])):
        r = rng.permutation(np.flatnonzero(MI == m))
        h = (len(r) + 1) // 2
        calib += list(r[:h])
        test += [i for i in r[h:] if nb_train[BI[i]] >= 5]   # only benchmarks with a training curve
    return train, np.array(calib), np.array(test), sorted(set(MI[late]))


def boot_one(seed):
    rng = np.random.default_rng(seed)
    keep = {NAMES.index(F.ANCHOR_LOW[0]), NAMES.index(F.ANCHOR_HIGH[0])}
    pick = list(keep) + list(rng.choice(NM, NM - len(keep), replace=True))
    mi, bi, y = [], [], []
    for new, m in enumerate(pick):
        r = np.flatnonzero(MI == m)
        mi += [new] * len(r); bi += list(BI[r]); y += list(Y[r])
    D = F.Data(mi, bi, y, len(pick), NB, [NAMES[m] for m in pick])
    r = F.fit(D, ECI[pick], k=1, kind="monotone")
    return np.array([c(GRID) if c is not None else np.full(len(GRID), np.nan) for c in r["curves"]])


def r4(v):
    return [None if not np.isfinite(x) else round(float(x), 4) for x in np.atleast_1d(v)]


def main():
    out = dict(cut=CUT, variants=VKEY, grid=[float(GRID[0]), float(GRID[-1]), 1.0])
    full = rows_all = np.arange(len(Y))
    with ProcessPoolExecutor(4) as ex:
        # ---- full fits ----
        D = F.Data(MI, BI, Y, NM, NB, NAMES)
        fits = {}
        for (k, kind), key in zip(VARIANTS, VKEY):
            fits[key] = F.fit(D, ECI, k=k, kind=kind)
            print(f"full {key}: rmse {np.sqrt(fits[key]['sse'] / len(Y)):.4f}", flush=True)

        # ---- random CV ----
        fo = folds()
        oof = {key: np.full(len(Y), np.nan) for key in VKEY + ["eci"]}
        jobs = []
        for f in range(FOLDS):
            tr, te = np.flatnonzero(fo != f), np.flatnonzero(fo == f)
            _, pred = eci_on(tr)
            oof["eci"][te] = pred(MI[te], BI[te])
            for (k, kind), key in zip(VARIANTS, VKEY):
                jobs.append((key, te, ex.submit(run_variant, (tr, te, k, kind, None, None))))
        for key, te, j in jobs:
            oof[key][te] = j.result()
        for key in oof:
            print(f"random CV {key}: rmse {np.sqrt(np.nanmean((oof[key] - Y) ** 2)):.4f}", flush=True)

        # ---- forward CV ----
        tr, ca, te, late = forward_split()
        fwd = {key: ex.submit(run_variant, (tr, te, k, kind, late, ca)) for (k, kind), key in zip(VARIANTS, VKEY)}
        fwd = {key: j.result() for key, j in fwd.items()}
        for key in VKEY:
            print(f"forward CV {key}: rmse {np.sqrt(np.mean((fwd[key] - Y[te]) ** 2)):.4f}", flush=True)

        # ---- bootstrap bands ----
        boots = np.array(list(ex.map(boot_one, range(100, 100 + NBOOT))))
    lo, hi = np.nanpercentile(boots, 10, axis=0), np.nanpercentile(boots, 90, axis=0)

    # bootstrap CV-style error bars: resample models, recompute RMSE of each variant
    rng = np.random.default_rng(SEED)
    def rmse_ci(err, groups):
        g = np.unique(groups)
        s = []
        for _ in range(400):
            pick = rng.choice(g, len(g))
            e = np.concatenate([err[groups == m] for m in pick])
            s.append(np.sqrt(np.nanmean(e ** 2)))
        return [round(float(np.sqrt(np.nanmean(err ** 2))), 4), round(float(np.percentile(s, 5)), 4), round(float(np.percentile(s, 95)), 4)]
    out["cv"] = dict(
        random={key: rmse_ci(oof[key] - Y, MI) for key in oof},
        forward={key: rmse_ci(fwd[key] - Y[te], MI[te]) for key in VKEY},
        n_random=len(Y), n_forward=len(te), n_late=len(late), n_train=len(tr))
    out["insample"] = {key: round(float(np.sqrt(fits[key]["sse"] / len(Y))), 4) for key in VKEY}

    # ---- models ----
    out["models"] = [dict(m=m[0], lab=m[1], d=m[2], eci=m[3],
                          t=round(float(fits["k1_monotone"]["U"][i, 0]), 2),
                          tl=round(float(fits["k1_logistic"]["U"][i, 0]), 2),
                          u=[round(float(v), 2) for v in fits["k2_monotone"]["U"][i]],
                          ul=[round(float(v), 2) for v in fits["k2_logistic"]["U"][i]])
                     for i, m in enumerate(RAW["models"])]

    # ---- benchmarks: scores, fitted and out-of-fold predictions, curves ----
    k1, k1l, k2, k2l = (fits[k] for k in VKEY)
    pin = {key: F.predict(fits[key]["U"], fits[key]["alpha"], fits[key]["curves"], MI, BI) for key in VKEY}
    fwd_full = {key: np.full(len(Y), np.nan) for key in VKEY}
    for key in VKEY:
        fwd_full[key][te] = fwd[key]
    bs = []
    for b, bd in enumerate(BEN):
        r = np.flatnonzero(BI == b)
        c1, c2, c2l = k1["curves"][b], k2["curves"][b], k2l["curves"][b]
        on = (GRID >= c1.knots[0]) & (GRID <= c1.knots[-1])
        th = k1["U"][MI[r], 0]
        cw = F.fit_curve(th, Y[r], c1.knots[0], c1.knots[-1], "monotone", c1.logi, **LIGHT)
        bs.append(dict(
            name=bd["name"], area=bd["area"], rel=bd["rel"], n=len(r),
            # cells: model, score, in-sample fits, random-CV out-of-fold predictions, forward-CV predictions
            c=[[int(MI[i]), round(float(Y[i]), 4)] + r4([pin[k][i] for k in VKEY]) + r4([oof[k][i] for k in VKEY + ["eci"]])
               + r4([fwd_full[k][i] for k in ["k1_logistic", "k1_monotone"]]) for i in r],
            g1=r4(np.where(on, c1(GRID), np.nan)), lo=r4(lo[b]), hi=r4(hi[b]), g1w=r4(np.where(on, cw(GRID), np.nan)),
            logi1=[round(float(c1.logi[0]), 5), round(float(c1.logi[1]), 3)],          # sigmoid fit on the same theta
            logiL=[round(float(k1l["curves"][b].logi[0]), 5), round(float(k1l["curves"][b].logi[1]), 3)],
            a2=round(float(k2["alpha"][b]), 4), k2=[r4(c2.knots), r4(c2.vals)],
            a2l=round(float(k2l["alpha"][b]), 4), logi2l=[round(float(c2l.logi[0]), 5), round(float(c2l.logi[1]), 3)]))
    out["b"] = bs
    out["areas"], out["cols"] = RAW["areas"], RAW["cols"]
    out["params"] = dict(nknot=F.NKNOT, smooth=F.LAM_SMOOTH, shrink=F.LAM_SHRINK, boot=NBOOT, folds=FOLDS,
                         light=LIGHT, prior2=F.PRIOR_SD[1], alpha_sd=round(float(np.rad2deg(F.ALPHA_SD)), 1))
    json.dump(out, open(ROOT / "data" / "npca.json", "w"), separators=(",", ":"))
    print("wrote data/npca.json")


if __name__ == "__main__":
    main()
