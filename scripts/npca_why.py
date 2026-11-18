"""Why does the piecewise-linear (npca) curve read more recent growth than the logistic? Prints four checks.

1. Where the two capability scales differ: slope of npca capability on logistic capability, by range.
2. Whether particular benchmarks drive it: the capability gap between today's strongest models and those of a
   year ago, as each benchmark's own scores imply it under each curve, with each benchmark's weight.
3. Whether the data ask for it: with capability fixed at the logistic's, is the same benchmark steeper or flatter
   among models above 150 than among models at 125-150?
4. Whether fit quality depends on it: stretch everything above 150 by a factor, refit the free curves, and report
   the in-sample error.
Run: python npca_why.py   (about a minute; reads data/curve_fits.json, so run curve_fits.py first)
"""
import json, warnings
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

import eci_fit
import npca_accel as A
import npca_build as NB

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
RAW, names, MI, BI, Y = NB.RAW, NB.NAMES, NB.MI, NB.BI, NB.Y
dates = np.array(NB.DATES)
C = {v["key"]: v for v in json.load(open(ROOT / "data" / "curve_fits.json"))["variants"]}
thN = np.array(C["monotone"]["theta"])
cap, dif, dis = (np.array(RAW["fit"][k]) for k in ("cap", "dif", "dis"))
a, b = eci_fit.to_eci(cap, names)
thL, ediL, slL = a + b * cap, a + b * dif, dis / b          # least-squares logistic, on the ECI scale
sig = lambda z: 1 / (1 + np.exp(-z))

print("1. Slope of npca capability on logistic capability (models since GPT-4)")
ok = np.isfinite(thN) & (dates >= "2023-03-14")
for lo, hi in [(110, 130), (130, 150), (150, 160), (160, 180)]:
    k = ok & (thL >= lo) & (thL < hi)
    print(f"   logistic {lo}-{hi}: n {k.sum():3d}  slope {np.polyfit(thL[k], thN[k], 1)[0]:.2f}  mean shift {(thN[k] - thL[k]).mean():+.1f}")

print("\n2. Gap between current and year-ago strong models, as each benchmark's scores imply it")
impN = np.concatenate([np.array(x) for x in C["monotone"]["imp"]])
wN = np.concatenate([np.array(x) for x in C["monotone"]["w"]])
yc = np.clip(Y, .01, .99)
impL = ediL[BI] + np.log(yc / (1 - yc)) / slL[BI]
pL = sig(slL[BI] * (thL[MI] - ediL[BI]))
wL = slL[BI] * pL * (1 - pL)
end = np.datetime64(RAW["snapshot"])
cur = np.flatnonzero((dates >= str(end - 110)) & (thL >= 165))
old = np.flatnonzero((dates >= str(end - 470)) & (dates < str(end - 320)) & (thL >= 148))
print(f"   {len(cur)} current models, {len(old)} from a year ago; overall gap: logistic {thL[cur].mean() - thL[old].mean():.1f}, npca {thN[cur].mean() - thN[old].mean():.1f}")
tot = lambda w: sum((w[BI == q][np.isin(MI[BI == q], cur)] ** 2).sum() for q in range(NB.NB))
TL, TN = tot(wL), tot(wN)
print("   benchmark                         score then -> now | implied gap: logistic  npca | weight now: logistic  npca")
for k, bd in enumerate(RAW["b"]):
    m = BI == k
    mc, mo = np.isin(MI[m], cur), np.isin(MI[m], old)
    if mc.sum() < 3 or mo.sum() < 3:
        continue
    print(f"   {bd['name'][:32]:32s}  {Y[m][mo].mean():.2f} -> {Y[m][mc].mean():.2f}   |   {impL[m][mc].mean() - impL[m][mo].mean():+6.1f}  {impN[m][mc].mean() - impN[m][mo].mean():+6.1f}   |"
          f"   {(wL[m][mc] ** 2).sum() / TL * 100:4.1f}%  {(wN[m][mc] ** 2).sum() / TN * 100:4.1f}%")

print("\n3. Same benchmark, logistic slope fitted separately on models at 125-150 and above 150 (capability fixed)")
fit = lambda x, y, s0, d0: least_squares(lambda p: sig(p[0] * (x - p[1])) - y, [s0, d0], bounds=([1e-3, 0], [5, 400])).x
for nm, th in [("logistic scale", thL), ("npca scale", thN)]:
    r = []
    for k, bd in enumerate(RAW["b"]):
        m = BI == k
        x, xl, y = th[MI[m]], thL[MI[m]], Y[m]
        lo, hi = (xl >= 125) & (xl < 150), xl >= 150
        if lo.sum() < 10 or hi.sum() < 10 or np.ptp(y[lo]) < 0.25 or np.ptp(y[hi]) < 0.25:
            continue
        r.append(fit(x[hi], y[hi], slL[k], ediL[k])[0] / fit(x[lo], y[lo], slL[k], ediL[k])[0])
    r = np.array(r)
    print(f"   {nm}: {len(r)} benchmarks, slope above / below: median {np.median(r):.2f}, geometric mean {np.exp(np.log(r).mean()):.2f}, flatter above in {(r < 1).sum()}")

print("\n4. Free-curve in-sample RMSE when everything above 150 on the logistic scale is stretched")
_, _, opt, par, _ = next(v for v in A.VARIANTS if v[0] == "monotone")


def rmse(th):
    c = A.curves_for(opt, par, th, MI, BI, Y, NB.NB)
    return np.sqrt(sum(float(np.sum((c[k](th[MI[BI == k]]) - Y[BI == k]) ** 2)) for k in range(NB.NB) if c[k] is not None) / len(Y))


for s in [0.8, 1.0, 1.2, 1.5, 2.0]:
    print(f"   x{s:.1f}: {rmse(np.where(thL > 150, 150 + s * (thL - 150), thL)):.4f}")
print(f"   npca's own scale: {rmse(thN):.4f}")
