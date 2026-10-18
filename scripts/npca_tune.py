"""Reproduce the 5-fold CV choices behind the constants in npca_fit.py.

  curves   LAM_SMOOTH x LAM_SHRINK for the one-factor monotone fit (grid below). The surface is flat
           (about 0.0926-0.0940); 30 / 10 is near, not at, the minimum, so treat the pull as a choice.
  twofac   axis-2 prior sd (PRIOR_SD[1]) and angle prior sd (ALPHA_SD) for the two-factor fits. Chose 3 / 15 deg.

Same folds and the same start (ECI refit on each fold's training cells) as npca_build.py. Held-out RMSE on
these folds is nearly blind to how models are spaced above the upper anchor, so this tuning says nothing
about the size of any acceleration; see npca_forward.py for the test that does. Run: python npca_tune.py
[curves|twofac]  (default both; about 25 + 10 minutes on 3 cores). Prints a table; writes nothing.
"""
import itertools
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import npca_build as NB
import npca_fit as F

warnings.filterwarnings("ignore")
FOLDS = NB.folds()
SMOOTH = [3, 10, 30, 100, 300]
SHRINK = [1, 3, 10, 30, 100]
TWOFAC = [(3, 15, "monotone"), (6, 15, "monotone"), (6, 30, "monotone"), (12, 30, "monotone"), (3, 15, "logistic")]


def errors(k, kind, f, iters=25):
    tr, te = np.flatnonzero(FOLDS != f), np.flatnonzero(FOLDS == f)
    D = F.Data(NB.MI[tr], NB.BI[tr], NB.Y[tr], NB.NM, NB.NB, NB.NAMES)
    r = F.fit(D, NB.eci_on(tr)[0], k=k, kind=kind, iters=iters)
    return F.predict(r["U"], r["alpha"], r["curves"], NB.MI[te], NB.BI[te]) - NB.Y[te]


def curve_job(a):
    sm, sh, f = a
    F.LAM_SMOOTH, F.LAM_SHRINK = sm, sh
    return (sm, sh), errors(1, "monotone", f)


def twofac_job(a):
    psd, asd, kind, f = a
    F.PRIOR_SD, F.ALPHA_SD = (F.PRIOR_SD[0], psd), np.deg2rad(asd)
    return (psd, asd, kind), errors(2, kind, f, iters=12)


def run(job, configs):
    res = {}
    with ProcessPoolExecutor(3) as ex:
        for key, e in ex.map(job, [c + (f,) for c in configs for f in range(NB.FOLDS)]):
            res.setdefault(key, []).extend(e)
    return {k: float(np.sqrt(np.mean(np.square(v)))) for k, v in res.items()}


def main(parts):
    if "curves" in parts:
        r = run(curve_job, list(itertools.product(SMOOTH, SHRINK)))
        print("one-factor monotone: random 5-fold RMSE, rows = smoothness, columns = shrinkage (pull)")
        print("smooth \\ shrink " + "".join(f"{s:>9}" for s in SHRINK))
        for sm in SMOOTH:
            print(f"{sm:>15} " + "".join(f"{r[(sm, sh)]:9.4f}" for sh in SHRINK))
        print("best:", min(r, key=r.get), f"{min(r.values()):.4f}", flush=True)
    if "twofac" in parts:
        r = run(twofac_job, TWOFAC)
        print("two-factor: random 5-fold RMSE (axis-2 prior sd, angle prior sd in degrees, curve)")
        for k, v in r.items():
            print(f"  {k}: {v:.4f}")
        print("best:", min(r, key=r.get), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["curves", "twofac"])
