"""Nonparametric version of ECI: a monotone-link, low-rank model of the model x benchmark score matrix.

ECI is a rank-1 logistic PCA:      score_mb = sigmoid(a_b * (theta_m - d_b))
Here each benchmark gets its own monotone curve g_b, and models may have k = 1 or 2 coordinates:

    score_mb = g_b(u_m . dir_b),   g_b nondecreasing,   dir_b = (cos alpha_b, sin alpha_b)

With k = 1 this is score = g_b(theta_m): a "nonparametric ECI". With k = 2 every model is a point in the
plane, every benchmark a direction, and a benchmark's score rises (monotonically, in its own shape) with
a model's projection onto that direction. Curves are either
    "logistic": the ECI shape, sigmoid(a (eta - d)), or
    "monotone": piecewise linear on a fixed knot grid with nonnegative rises (fit by NNLS), penalised
                for curvature and shrunk towards that benchmark's logistic fit, so benchmarks with few
                scores fall back to the ECI shape and well-measured ones can bend.
The 2 x 2 of {logistic, monotone} x {k=1, k=2} separates the effect of the link from the effect of rank.

Fit by alternating: curves given positions; directions given positions (grid over angles); positions given
curves (grid search per model, coarse to fine). Same objective as Epoch's ECI: squared error in score
space, plus small penalties. Positions are kept on the ECI scale by pinning Claude 3.5 Sonnet = 130 and
GPT-5 = 150 on the first axis. With a free monotone link only the ORDER of models along that axis is
identified; its spacing is inherited from the ECI start and the anchors, not estimated.
"""
import numpy as np
from scipy.optimize import nnls

ANCHOR_LOW, ANCHOR_HIGH = ("Claude 3.5 Sonnet", 130.0), ("GPT-5", 150.0)
NKNOT = 28            # knots per monotone curve, spread over the range of the index across all models
LAM_SMOOTH = 30.0     # penalty on changes in slope between neighbouring segments (chosen by 5-fold CV)
LAM_SHRINK = 10.0     # penalty on departures from the benchmark's logistic curve (chosen by 5-fold CV)
PRIOR_SD = (25.0, 3.0)    # N(mean, sd^2) prior on each model coordinate (ECI points); axis-2 sd chosen by 5-fold CV
NOISE_VAR = 0.006     # residual variance used to weigh that prior against squared error
ALPHA_MAX = np.deg2rad(70)
ALPHA_SD = np.deg2rad(15)  # chosen by 5-fold CV


def sig(z):
    return 1 / (1 + np.exp(-z))


class Curve:
    """A nondecreasing curve, stored as values at knots and evaluated by linear interpolation."""
    def __init__(self, knots, vals, logi):
        self.knots, self.vals, self.logi = knots, np.clip(vals, 0, 1), logi  # logi = (slope, midpoint)

    def __call__(self, x):
        return np.interp(x, self.knots, self.vals)


def fit_logistic(x, y, init=None, iters=40):
    """Least squares sigmoid(a (x - d)) with a > 0, by damped Gauss-Newton; light ridge on log a."""
    a, d = init if init is not None else (0.1, np.median(x))
    def cost(a, d):
        r = sig(a * (x - d)) - y
        return r @ r + 1e-3 * np.log(a / 0.1) ** 2
    f, mu = cost(a, d), 1e-2
    for _ in range(iters):
        s = sig(a * (x - d)); ds = s * (1 - s)
        J = np.c_[ds * (x - d), -ds * a]
        g = J.T @ (s - y); H = J.T @ J
        step = None
        while mu < 1e6:
            st = np.linalg.solve(H + mu * np.diag(np.diag(H) + 1e-9), -g)
            an, dn = np.clip(a + st[0], 0.005, 2.0), d + st[1]
            fn = cost(an, dn)
            if fn < f:
                step = f - fn; a, d, f, mu = an, dn, fn, mu / 3
                break
            mu *= 4
        if step is None or step < 1e-10:
            break
    return a, d


def fit_curve(x, y, lo, hi, kind, init=None, smooth=None, shrink=None):
    """Curve for one benchmark from (index, score) pairs; knots span [lo, hi]. Penalties default to the module's."""
    smooth = LAM_SMOOTH if smooth is None else smooth
    shrink = LAM_SHRINK if shrink is None else shrink
    a, d = fit_logistic(x, y, init)
    knots = np.linspace(lo, hi, NKNOT)
    base = sig(a * (knots - d))
    if kind == "logistic":
        return Curve(knots, base, (a, d))
    # g(x) = c0 + sum_k rise_k * ramp_k(x); rises >= 0, c0 >= 0  -> NNLS on an augmented system
    w = np.diff(knots)
    ramps = np.clip((x[:, None] - knots[None, :-1]) / w[None, :], 0, 1)
    A = np.c_[np.ones(len(x)), ramps]
    n = NKNOT - 1
    D = np.diff(np.eye(n), axis=0) / w[0]           # change in slope between segments
    rise0 = np.diff(base)
    rows = [A, np.c_[np.zeros((n - 1, 1)), np.sqrt(smooth) * D],
            np.sqrt(shrink) * np.eye(n + 1)]
    rhs = [y, np.zeros(n - 1), np.sqrt(shrink) * np.r_[base[0], rise0]]
    coef, _ = nnls(np.vstack(rows), np.concatenate(rhs), maxiter=2000)
    return Curve(knots, coef[0] + np.r_[0, np.cumsum(coef[1:])], (a, d))


class Data:
    def __init__(self, mi, bi, y, nm, nb, names):
        self.mi, self.bi, self.y = np.asarray(mi), np.asarray(bi), np.asarray(y, float)
        self.nm, self.nb, self.names = nm, nb, list(names)
        self.by_b = [np.flatnonzero(self.bi == b) for b in range(nb)]
        self.by_m = [np.flatnonzero(self.mi == m) for m in range(nm)]

    def subset(self, rows):
        return Data(self.mi[rows], self.bi[rows], self.y[rows], self.nm, self.nb, self.names)


def dirs(alpha):
    return np.c_[np.cos(alpha), np.sin(alpha)]


def fit_curves(D, U, alpha, kind, prev=None):
    eta_all = U @ dirs(alpha).T          # every model's index on every benchmark
    curves = []
    for b in range(D.nb):
        r = D.by_b[b]
        lo, hi = eta_all[:, b].min() - 2, eta_all[:, b].max() + 2
        init = prev[b].logi if prev is not None and prev[b] is not None else None
        curves.append(fit_curve(eta_all[D.mi[r], b], D.y[r], lo, hi, kind, init) if len(r) else None)
    return curves


def curve_sse(c, x, y):
    r = c(x) - y
    return r @ r


def update_alpha(D, U, alpha, curves, kind):
    """Grid over each benchmark's angle; the curve is refit for each candidate angle."""
    grid = np.linspace(-ALPHA_MAX, ALPHA_MAX, 29)
    new, newc = alpha.copy(), list(curves)
    for b in range(D.nb):
        r = D.by_b[b]
        if len(r) == 0:
            continue
        best = None
        for t in np.r_[grid, alpha[b]]:
            eta_all = U @ np.array([np.cos(t), np.sin(t)])
            c = fit_curve(eta_all[D.mi[r]], D.y[r], eta_all.min() - 2, eta_all.max() + 2, kind, curves[b].logi)
            f = curve_sse(c, eta_all[D.mi[r]], D.y[r]) + NOISE_VAR * (t / ALPHA_SD) ** 2
            if best is None or f < best[0]:
                best = (f, t, c)
        new[b], newc[b] = best[1], best[2]
    return new, newc


WIDE = (60, 15, 4, 1)   # spans for placing a model with no sensible starting point


def place(D, U, alpha, curves, models, k, prior_mean, spans=(24, 6, 1.5), n=41):
    """Best position for each listed model given curves: coarse-to-fine grid search with a weak prior."""
    U = U.copy()
    dv = dirs(alpha)
    sd = np.array(PRIOR_SD[:k])
    for m in models:
        r = D.by_m[m]
        if len(r) == 0:
            continue
        b, y = D.bi[r], D.y[r]
        for span in spans:
            axes = [np.linspace(U[m, j] - span, U[m, j] + span, n) for j in range(k)]
            P = np.zeros((n ** k, 2))
            P[:, :k] = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, k)
            f = NOISE_VAR * (((P[:, :k] - prior_mean[:k]) / sd) ** 2).sum(1)
            for j, bb in enumerate(b):
                if curves[bb] is not None:
                    f += (curves[bb](P @ dv[bb]) - y[j]) ** 2
            U[m] = P[np.argmin(f)]
    return U


def reanchor(U, names):
    """Affine map so the anchors sit at 130 / 150 on axis 1; axis 2 scaled alike and centred."""
    lo, hi = names.index(ANCHOR_LOW[0]), names.index(ANCHOR_HIGH[0])
    s = (ANCHOR_HIGH[1] - ANCHOR_LOW[1]) / (U[hi, 0] - U[lo, 0])
    V = U * s
    V[:, 0] += ANCHOR_LOW[1] - V[lo, 0]
    if U.shape[1] > 1:
        V[:, 1] -= V[:, 1].mean()
    return V


def objective(D, U, alpha, curves):
    dv = dirs(alpha)
    eta = (U[D.mi] * dv[D.bi]).sum(1)
    pred = np.array([curves[b](e) for b, e in zip(D.bi, eta)])
    return ((pred - D.y) ** 2).sum(), pred


def predict(U, alpha, curves, mi, bi):
    dv = dirs(alpha)
    eta = (U[mi] * dv[bi]).sum(1)
    return np.array([curves[b](e) if curves[b] is not None else np.nan for b, e in zip(bi, eta)])


def fit(D, theta0, k=1, kind="monotone", iters=25, U0=None, alpha0=None, tol=1e-6, verbose=False):
    """theta0: starting position on axis 1 (e.g. published ECI). Returns dict(U, alpha, curves, sse, hist)."""
    if U0 is None:
        U = np.c_[theta0, np.zeros(D.nm)]
    else:
        U = U0.copy()
    alpha = np.zeros(D.nb) if alpha0 is None else alpha0.copy()
    mean = np.array([np.mean(U[:, 0]), 0.0])
    curves = fit_curves(D, U, alpha, kind)
    if k == 2 and U0 is None:
        U, alpha, curves = init_second_axis(D, U, alpha, curves, kind)
    hist = []
    f_old = np.inf
    for it in range(iters):
        if k == 2:
            alpha, curves = update_alpha(D, U, alpha, curves, kind)
        U = place(D, U, alpha, curves, range(D.nm), k, mean)
        U = reanchor(U, D.names)
        curves = fit_curves(D, U, alpha, kind, curves)
        f, _ = objective(D, U, alpha, curves)
        hist.append(f)
        if verbose:
            print(f"  iter {it}: sse {f:.4f}")
        if f_old - f < tol * f_old and it > 2:
            break
        f_old = f
    return dict(U=U, alpha=alpha, curves=curves, sse=hist[-1], hist=hist, k=k, kind=kind, mean=mean)


def init_second_axis(D, U, alpha, curves, kind):
    """Start axis 2 from the leading rank-1 factor of the k = 1 residuals (observed cells only)."""
    res = D.y - predict(U, alpha, curves, D.mi, D.bi)
    r, w = np.ones(D.nm) * 0.0, np.ones(D.nb)
    rng = np.random.default_rng(0)
    r = rng.normal(0, 1, D.nm)
    for _ in range(50):
        num = np.zeros(D.nb); den = np.full(D.nb, 1e-3)
        np.add.at(num, D.bi, res * r[D.mi]); np.add.at(den, D.bi, r[D.mi] ** 2); w = num / den
        num = np.zeros(D.nm); den = np.full(D.nm, 1e-3)
        np.add.at(num, D.mi, res * w[D.bi]); np.add.at(den, D.mi, w[D.bi] ** 2); r = num / den
    # residual = slope_b * w_b * u2  =>  u2 ~ r in ECI-like units, small angles of sign(w)
    slopes = np.array([c.logi[0] if c is not None else 0.1 for c in curves])
    t = w / np.maximum(slopes, 0.02)
    scale = 10 / max(np.std(r), 1e-9)
    U = U.copy(); U[:, 1] = (r - r.mean()) * scale
    alpha = np.clip(np.arctan(t / scale), -ALPHA_MAX / 2, ALPHA_MAX / 2)
    return U, alpha, fit_curves(D, U, alpha, kind)
