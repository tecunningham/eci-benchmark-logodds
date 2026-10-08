"""Epoch's ECI fit (github.com/epoch-research/eci-public, src/eci/fitting.py), solved by Levenberg-Marquardt.

Same model and objective as Epoch's code:
    score = sigmoid(disc_b * (cap_m - diff_b)),  scores clipped to [1e-3, 1 - 1e-3]
    minimise  sum (pred - score)^2  +  0.1 * |params|^2 / n_params
with the anchor benchmark's discriminability pinned and the result mapped so that
Claude 3.5 Sonnet = 130 and GPT-5 = 150. scipy's least_squares stops at ftol = 1e-8;
this runs a little further, reaching a slightly lower objective (published ECIs are
reproduced to within 0.06 points). The interactive page runs the same algorithm in JS.
"""
import numpy as np

REG, CLIP = 0.1, 1e-3
ANCHOR_LOW, ANCHOR_HIGH = ("Claude 3.5 Sonnet", 130.0), ("GPT-5", 150.0)


@np.errstate(all="ignore")  # macOS Accelerate BLAS raises spurious matmul warnings
def fit(y, mi, bi, nm, nb, anchor, anchor_disc=1.0, x0=None, iters=300):
    """Returns raw (cap[nm], diff[nb], disc[nb])."""
    y = np.clip(y, CLIP, 1 - CLIP)
    if x0 is None:
        rng = np.random.default_rng(42)
        x0 = np.concatenate([rng.normal(0, .1, nm), rng.normal(0, .1, nb), np.ones(nb)])
    x = np.array(x0, float)
    x[nm + nb + anchor] = anchor_disc
    free = np.ones(nm + 2 * nb, bool)
    free[nm + nb + anchor] = False
    lam = REG / free.sum()
    lo = np.r_[np.full(nm + nb, -10.), np.full(nb, .1)]
    hi = np.full(nm + 2 * nb, 10.)
    rows = np.arange(len(y))

    def cost(x):
        c, d, a = x[:nm], x[nm:nm + nb], x[nm + nb:]
        r = 1 / (1 + np.exp(-a[bi] * (c[mi] - d[bi]))) - y
        return r @ r + lam * (x[free] @ x[free])

    f, mu = cost(x), 1e-3
    for _ in range(iters):
        c, d, a = x[:nm], x[nm:nm + nb], x[nm + nb:]
        s = 1 / (1 + np.exp(-a[bi] * (c[mi] - d[bi])))
        ds = s * (1 - s)
        J = np.zeros((len(y), nm + 2 * nb))
        J[rows, mi] = ds * a[bi]
        J[rows, nm + bi] = -ds * a[bi]
        J[rows, nm + nb + bi] = ds * (c[mi] - d[bi])
        J = J[:, free]
        H = J.T @ J + lam * np.eye(free.sum())
        g = J.T @ (s - y) + lam * x[free]
        gain = 0.0
        while mu < 1e8:
            xn = x.copy()
            xn[free] = np.clip(x[free] + np.linalg.solve(H + mu * np.diag(np.diag(H)), -g), lo[free], hi[free])
            fn = cost(xn)
            if fn < f:
                gain, x, f, mu = f - fn, xn, fn, max(mu / 3, 1e-9)
                break
            mu *= 4
        if gain < 1e-12 * f:
            break
    return x[:nm], x[nm:nm + nb], x[nm + nb:]


def to_eci(cap, names):
    """Affine map (a, b) with eci = a + b * cap, from the two anchor models."""
    cl, ch = cap[names.index(ANCHOR_LOW[0])], cap[names.index(ANCHOR_HIGH[0])]
    b = (ANCHOR_HIGH[1] - ANCHOR_LOW[1]) / (ch - cl)
    return ANCHOR_LOW[1] - b * cl, b
