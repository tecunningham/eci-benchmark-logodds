"""Compare ways of fitting each benchmark's curve of capability: score_mb = g_b(theta_m).

Model positions are held fixed at Epoch's ECI refit on the training cells, so only the curve shape differs
between options (the joint, alternating fits are in npca_build.py). Options:

  logistic       sigmoid(a (theta - d))                                  ECI's curve
  four_pl        floor + (1 - floor - gap) * sigmoid(...)                 adds a floor and a ceiling
  cloglog        1 - exp(-exp(a (theta - d)))                             asymmetric: slow start, fast finish
  shared         G(a_b (theta - d_b)), one free monotone G for all        tests the sigmoid's shape globally
  logit_spline   sigmoid(h(theta)), h monotone, penalised for bending     bends; infinite penalty = logistic
  item_mixture   sum_j w_j sigmoid(s (theta - d_j)), w >= 0               a spread of item difficulties
  monotone       piecewise linear, nonneg rises, pulled to the logistic   the curve in npca_fit.py
  isotonic       any nondecreasing step function                          no smoothing at all

Held-out tests (same as npca_build.py):
  random   5-fold over cells; theta from ECI on the 4 training folds
  forward  curves fit on models released before CUT; theta from ECI fit on those plus half of each later
           model's scores; the other half are predicted (benchmarks with >= 5 training scores)
Tuning parameters (logit_spline, item_mixture) are chosen on the random folds, so their random-CV numbers
are slightly optimistic; the forward test is not used for tuning.

Writes data/npca_links.json (results + every curve on a theta grid, full data) and prints a table.
"""
import json
import warnings
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares, nnls
from sklearn.isotonic import IsotonicRegression

import npca_build as NB
import npca_fit as F

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
MI, BI, Y = NB.MI, NB.BI, NB.Y


def sig(z):
    return 1 / (1 + np.exp(-np.clip(z, -40, 40)))


# ---------- per-benchmark families: fit(x, y, lo, hi, **par) -> callable on new theta ----------
def logistic(x, y, lo, hi):
    a, d = F.fit_logistic(x, y)
    return lambda t: sig(a * (t - d))


def four_pl(x, y, lo, hi):
    a, d = F.fit_logistic(x, y)
    def res(p):   # floor c and gap e (1 - ceiling), lightly pulled to 0 so sparse benchmarks stay logistic
        la, d_, c, e = p
        return np.r_[c + (1 - c - e) * sig(np.exp(la) * (x - d_)) - y, 0.3 * c, 0.3 * e, 0.03 * (la - np.log(a))]
    la, d_, c, e = least_squares(res, [np.log(a), d, .01, .01], bounds=([-8, -np.inf, 0, 0], [2, np.inf, .5, .5])).x
    return lambda t: c + (1 - c - e) * sig(np.exp(la) * (t - d_))


def cloglog(x, y, lo, hi):
    a, d = F.fit_logistic(x, y)
    f = lambda p, t: 1 - np.exp(-np.exp(np.clip(np.exp(p[0]) * (t - p[1]), -30, 30)))
    p = least_squares(lambda p: np.r_[f(p, x) - y, 0.03 * (p[0] - np.log(a))], [np.log(a), d]).x
    return lambda t: f(p, t)


def logit_spline(x, y, lo, hi, lam=1.0, nk=8):
    """logit g = h(theta): h piecewise linear with positive slopes (log-parametrised) on nk knots, extended
    linearly beyond them; penalty on changes in log slope, so a large lam returns the logistic."""
    a, d = F.fit_logistic(x, y)
    kn = np.linspace(lo, hi, nk)
    w = kn[1] - kn[0]
    def h(p, t):
        v = p[0] + np.r_[0, np.cumsum(np.exp(p[1:]))]
        return (np.interp(t, kn, v) + np.where(t < kn[0], (t - kn[0]) * np.exp(p[1]) / w, 0)
                + np.where(t > kn[-1], (t - kn[-1]) * np.exp(p[-1]) / w, 0))
    p0 = np.r_[a * (kn[0] - d), np.full(nk - 1, np.log(a * w))]
    p = least_squares(lambda p: np.r_[sig(h(p, x)) - y, np.sqrt(lam) * 0.1 * np.diff(p[1:])], p0).x
    return lambda t: sig(h(p, t))


def item_mixture(x, y, lo, hi, s=0.6, lam=0.02, nd=30):
    """g = sum_j w_j sigmoid(s (theta - d_j)) over a grid of item difficulties d_j, w >= 0 (NNLS), smoothed
    across neighbouring difficulties. s is one item slope shared by every benchmark."""
    dg = np.linspace(lo - 30, hi + 30, nd)
    A = sig(s * (x[:, None] - dg[None, :]))
    M = np.vstack([A, np.sqrt(lam) * 10 * np.diff(np.eye(nd), axis=0), np.sqrt(lam) * np.eye(nd)])
    w, _ = nnls(M, np.r_[y, np.zeros(2 * nd - 1)], maxiter=3000)
    return lambda t: np.clip(sig(s * (np.atleast_1d(t)[:, None] - dg[None, :])) @ w, 0, 1)


def monotone(x, y, lo, hi):
    return F.fit_curve(x, y, lo, hi, "monotone")


def isotonic(x, y, lo, hi):
    return IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(x, y).predict


# ---------- shared free shape: g_b(theta) = G(a_b (theta - d_b)) ----------
ZK = np.linspace(-8, 8, 25)


def shared(th, mi, bi, y, nb, iters=8, lam=2.0):
    """Alternate: one monotone G on a z grid (NNLS, pulled to the sigmoid) / each benchmark's (a_b, d_b)."""
    ab = np.array([F.fit_logistic(th[mi[bi == b]], y[bi == b]) if (bi == b).sum() >= 2 else (0.1, 140.0)
                   for b in range(nb)])
    base = sig(ZK)
    for _ in range(iters):
        z = ab[bi, 0] * (th[mi] - ab[bi, 1])
        A = np.c_[np.ones(len(z)), np.clip((z[:, None] - ZK[None, :-1]) / (ZK[1] - ZK[0]), 0, 1)]
        coef, _ = nnls(np.vstack([A, np.sqrt(lam) * np.eye(len(ZK))]),
                       np.r_[y, np.sqrt(lam) * np.r_[base[0], np.diff(base)]], maxiter=3000)
        Gv = np.clip(coef[0] + np.r_[0, np.cumsum(coef[1:])], 0, 1)
        G = lambda z, Gv=Gv: np.interp(z, ZK, Gv)
        for b in range(nb):
            r = np.flatnonzero(bi == b)
            if len(r) >= 2:
                p = least_squares(lambda p: np.r_[G(np.exp(p[0]) * (th[mi[r]] - p[1])) - y[r], 0.03 * (p[0] - np.log(0.1))],
                                  [np.log(max(ab[b, 0], 1e-3)), ab[b, 1]]).x
                ab[b] = np.exp(p[0]), p[1]
    return ab, Gv


OPTIONS = [  # key, label, fitter, extra parameters per benchmark, keeps the spacing between models?
    ("logistic", "Logistic (ECI's curve)", logistic, "2", "yes"),
    ("four_pl", "Logistic + floor + ceiling", four_pl, "4", "yes"),
    ("cloglog", "Complementary log-log", cloglog, "2", "yes"),
    ("shared", "One free shape shared by all benchmarks", None, "2 (+ 1 shared curve)", "yes"),
    ("logit_spline", "Monotone spline in logit space", logit_spline, "8, penalised", "only through the penalty"),
    ("item_mixture", "Mixture of item difficulties", item_mixture, "30 weights, penalised", "no (keeps stretching in joint fits)"),
    ("monotone", "Piecewise-linear monotone (npca)", monotone, "28, penalised", "only through the pull to the logistic"),
    ("isotonic", "Isotonic (any step function)", isotonic, "up to n", "no"),
]
TUNE = dict(logit_spline=[dict(lam=v) for v in (0.3, 1, 3, 10, 30)],
            item_mixture=[dict(s=s, lam=l) for s in (0.25, 0.35, 0.6, 1.0) for l in (0.002, 0.02)])


def predict_cells(th, train, test, key, fn, par):
    out = np.full(len(test), np.nan)
    lo, hi = th.min() - 2, th.max() + 2
    if key == "shared":
        ab, Gv = shared(th, MI[train], BI[train], Y[train], NB.NB)
        return np.interp(ab[BI[test], 0] * (th[MI[test]] - ab[BI[test], 1]), ZK, Gv)
    for b in np.unique(BI[test]):
        rt, rv = train[BI[train] == b], np.flatnonzero(BI[test] == b)
        if len(rt) >= 2:
            out[rv] = fn(th[MI[rt]], Y[rt], lo, hi, **par)(th[MI[test[rv]]])
    return out


def main():
    fo = NB.folds()
    folds = []
    for f in range(NB.FOLDS):
        tr, te = np.flatnonzero(fo != f), np.flatnonzero(fo == f)
        folds.append((tr, te, NB.eci_on(tr)[0]))

    def random_cv(key, fn, par):
        o = np.full(len(Y), np.nan)
        for tr, te, th in folds:
            o[te] = predict_cells(th, tr, te, key, fn, par)
        return o

    rmse = lambda e: float(np.sqrt(np.nanmean(e ** 2)))
    best = {}
    for key, _, fn, _, _ in OPTIONS:
        grid = TUNE.get(key, [{}])
        scores = [(rmse(random_cv(key, fn, p) - Y), i) for i, p in enumerate(grid)]
        best[key] = grid[min(scores)[1]]
        if len(grid) > 1:
            print(f"tuned {key}: {best[key]}  ({', '.join(f'{s:.4f}' for s, _ in scores)})", flush=True)
    oof = {key: random_cv(key, fn, best[key]) for key, _, fn, _, _ in OPTIONS}
    oof["eci_joint"] = np.full(len(Y), np.nan)
    for tr, te, _ in folds:
        oof["eci_joint"][te] = NB.eci_on(tr)[1](MI[te], BI[te])

    # forward: curves on pre-cut models; theta from ECI on those plus the later models' calibration halves
    tr, ca, te, late = NB.forward_split()
    th_f = NB.eci_on(np.r_[tr, ca])[0]
    fwd = {key: predict_cells(th_f, tr, te, key, fn, best[key]) for key, _, fn, _, _ in OPTIONS}

    rng = np.random.default_rng(NB.SEED)
    def paired(pred, ref, y, groups, n=400):
        """RMSE change vs the logistic, % (point, 5th, 95th percentile over resampled models)."""
        g = np.unique(groups)
        idx = {m: np.flatnonzero(groups == m) for m in g}
        pt = 100 * (rmse(pred - y) / rmse(ref - y) - 1)
        s = []
        for _ in range(n):
            r = np.concatenate([idx[m] for m in rng.choice(g, len(g))])
            s.append(100 * (rmse(pred[r] - y[r]) / rmse(ref[r] - y[r]) - 1))
        return [round(pt, 2), round(float(np.percentile(s, 5)), 2), round(float(np.percentile(s, 95)), 2)]

    res = []
    for key, label, _, npar, spacing in OPTIONS:
        res.append(dict(key=key, label=label, npar=npar, spacing=spacing, par=best[key],
                        random=round(rmse(oof[key] - Y), 4), forward=round(rmse(fwd[key] - Y[te]), 4),
                        drandom=paired(oof[key], oof["logistic"], Y, MI),
                        dforward=paired(fwd[key], fwd["logistic"], Y[te], MI[te])))
    eci_joint = dict(random=round(rmse(oof["eci_joint"] - Y), 4), drandom=paired(oof["eci_joint"], oof["logistic"], Y, MI))

    # where the free curves gain: per-benchmark change in held-out squared error, monotone vs logistic
    names = [b["name"] for b in NB.BEN]
    per_b = [dict(name=names[b], n=int((BI == b).sum()),
                  **{k: round(float(np.nansum((oof[k][BI == b] - Y[BI == b]) ** 2) - np.nansum((oof["logistic"][BI == b] - Y[BI == b]) ** 2)), 4)
                     for k in ("monotone", "item_mixture", "logit_spline")}) for b in range(NB.NB)]

    # every option's curve for every benchmark, fit on all scores, theta = ECI on all scores
    th = NB.eci_on(np.arange(len(Y)))[0]
    lo, hi = th.min() - 2, th.max() + 2
    ab, Gv = shared(th, MI, BI, Y, NB.NB)
    curves = []
    for b in range(NB.NB):
        r = np.flatnonzero(BI == b)
        g0, g1 = np.floor(th[MI[r]].min()) - 8, np.ceil(th[MI[r]].max()) + 8
        grid = np.arange(g0, g1 + 0.5, 1.0)
        c = dict(name=names[b], area=NB.BEN[b]["area"], n=len(r), g0=float(g0),
                 pts=[[round(float(th[MI[i]]), 2), round(float(Y[i]), 4), NB.NAMES[MI[i]]] for i in r], f={})
        for key, _, fn, _, _ in OPTIONS:
            v = np.interp(ab[b, 0] * (grid - ab[b, 1]), ZK, Gv) if key == "shared" else fn(th[MI[r]], Y[r], lo, hi, **best[key])(grid)
            c["f"][key] = [round(float(x), 4) for x in v]
        curves.append(c)

    out = dict(options=res, eci_joint=eci_joint, per_b=per_b, curves=curves,
               shared=dict(z=[round(float(z), 3) for z in ZK], G=[round(float(g), 4) for g in Gv],
                           maxdev=round(float(np.abs(Gv - sig(ZK)).max()), 4)),
               n_random=len(Y), n_forward=len(te), cut=NB.CUT, areas=NB.RAW["areas"], cols=NB.RAW["cols"])
    json.dump(out, open(ROOT / "data" / "npca_links.json", "w"), separators=(",", ":"))

    print(f"\n{'option':42s} {'random':>8s} {'vs logistic':>22s} {'forward':>8s} {'vs logistic':>22s}")
    for o in res:
        print(f"{o['label']:42s} {o['random']:8.4f} {o['drandom'][0]:+6.1f}% [{o['drandom'][1]:+.1f},{o['drandom'][2]:+.1f}]"
              f" {o['forward']:8.4f} {o['dforward'][0]:+6.1f}% [{o['dforward'][1]:+.1f},{o['dforward'][2]:+.1f}]")
    print(f"ECI joint fit (Epoch's code): random {eci_joint['random']:.4f}; shared shape max |G - sigmoid| = {out['shared']['maxdev']}")
    print("wrote data/npca_links.json")


if __name__ == "__main__":
    main()
