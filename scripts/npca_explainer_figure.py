"""A picture of how the piecewise-linear (npca) fit works -> figures/npca_explainer.png.

Top row: the two alternating steps and the result. (1) With model positions fixed, one benchmark's curve: a chain of
straight segments that can only go up, pulled toward that benchmark's logistic. (2) With curves fixed, one model is
slid along the axis to where its squared misses are smallest. (3) After 80 rounds, with Claude 3.5 Sonnet = 130 and
GPT-5 = 150 pinned each round: where each model ends up against where the logistic puts it.
Bottom row: three benchmarks on the final scale, free curve against its logistic.
"""
import json, warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import eci_fit
import npca_accel as A
import npca_build as NB
import npca_fit as F

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
RAW, names, MI, BI, Y = NB.RAW, NB.NAMES, NB.MI, NB.BI, NB.Y
bn = [b["name"] for b in RAW["b"]]
thN = np.array(next(v for v in json.load(open(ROOT / "data" / "curve_fits.json"))["variants"] if v["key"] == "monotone")["theta"])
cap = np.array(RAW["fit"]["cap"]); a, b = eci_fit.to_eci(cap, names); thL = a + b * cap
_, _, opt, par, _ = next(v for v in A.VARIANTS if v[0] == "monotone")
curves = A.curves_for(opt, par, thN, MI, BI, Y, NB.NB)
INK, MUT, BLUE, PINK, GRID = "#1d2433", "#5d6577", "#1d64f2", "#e8177d", "#e3e5ea"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": "#b9bdc7", "axes.labelcolor": MUT,
                     "xtick.color": MUT, "ytick.color": MUT, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(2, 3, figsize=(15, 8.6), dpi=140)
pct = lambda x: x.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))


def bench(x, name, knots=False, title=None):
    k = bn.index(name); m = BI == k; c = curves[k]; t = thN[MI[m]]
    g = np.linspace(t.min() - 8, t.max() + 8, 400)
    x.scatter(t, Y[m], s=13, color=MUT, alpha=.55, lw=0, zorder=2)
    x.plot(g, F.sig(c.logi[0] * (g - c.logi[1])), "--", color=INK, lw=1.5, label="its logistic", zorder=3)
    x.plot(g, c(g), color=BLUE, lw=2.4, label="free curve (npca)", zorder=4)
    if knots:
        kk = c.knots[(c.knots > g[0]) & (c.knots < g[-1])]
        x.scatter(kk, c(kk), s=26, facecolor="white", edgecolor=BLUE, lw=1.4, zorder=5, label="knots")
    x.set_xlim(g[0], g[-1]); x.set_ylim(-.04, 1.04); pct(x); x.grid(color=GRID, lw=.7); x.set_xlabel("capability")
    x.set_title(title or name.replace(" 2024-2025", ""), loc="left", fontsize=10.5, color=INK, fontweight="bold")
    return k


# 1. one curve
k = bench(ax[0, 0], "SimpleBench", knots=True, title="Step 1. Curves, with models held still")
ax[0, 0].legend(frameon=False, loc="upper left", fontsize=9)
ax[0, 0].text(.98, .05, "SimpleBench: one dot per model.\nThe curve is straight segments between knots.\nEach segment may rise or stay flat, never fall.\nIt is pulled toward the dashed logistic and\npenalised for sharp bends.", transform=ax[0, 0].transAxes, ha="right", va="bottom", fontsize=8.6, color=MUT)

# 2. placing one model
x = ax[0, 1]; mod = names.index("Claude Opus 5.5"); r = np.flatnonzero(MI == mod)
g = np.linspace(thN[mod] - 28, thN[mod] + 22, 300)
tot = np.zeros_like(g)
for i in r:
    e = (curves[BI[i]](g) - Y[i]) ** 2; tot += e
    x.plot(g, e, color=MUT, lw=.8, alpha=.45)
x.plot(g, tot, color=PINK, lw=2.6)
x.axvline(g[np.argmin(tot)], color=PINK, lw=1, ls=":")
x.annotate("placed here:\nsmallest total miss", (g[np.argmin(tot)], tot.min()), xytext=(g[np.argmin(tot)] - 24, tot.max() * .55), color=PINK, fontsize=9, arrowprops=dict(arrowstyle="-", color=PINK, lw=.8))
x.set_xlabel("candidate capability for Claude Opus 5.5"); x.set_ylabel("squared miss"); x.grid(color=GRID, lw=.7)
x.set_title("Step 2. Models, with curves held still", loc="left", fontsize=10.5, color=INK, fontweight="bold")
x.text(.98, .97, f"Grey: the miss on each of its {len(r)} benchmarks\nas the model is slid along the axis.\nPink: their sum.", transform=x.transAxes, ha="right", va="top", fontsize=8.6, color=MUT)

# 3. result
x = ax[0, 2]; ok = (np.array(NB.DATES) >= "2023-03-14") & np.isfinite(thN) & (thL > 100)
x.plot([100, 185], [100, 185], color=INK, lw=1, ls="--")
x.scatter(thL[ok], thN[ok], s=14, color=BLUE, alpha=.6, lw=0)
for n, v in (("Claude 3.5 Sonnet", 130), ("GPT-5", 150)):
    x.scatter([v], [v], s=70, marker="D", facecolor="white", edgecolor=INK, lw=1.6, zorder=5)
    x.annotate(f"{n} = {v}\n(pinned every round)", (v, v), xytext=(v + 5, v - 13), fontsize=8.6, color=INK, arrowprops=dict(arrowstyle="-", color=INK, lw=.7))
top = names.index("GPT-6.2 Astra")
x.annotate(f"GPT-6.2 Astra\n{thL[top]:.0f} → {thN[top]:.0f}", (thL[top], thN[top]), xytext=(thL[top] - 30, thN[top] - 2), fontsize=8.6, color=BLUE, arrowprops=dict(arrowstyle="-", color=BLUE, lw=.7))
x.set_xlim(100, 185); x.set_ylim(100, 185); x.grid(color=GRID, lw=.7)
x.set_xlabel("capability with a logistic per benchmark"); x.set_ylabel("capability with a free curve per benchmark")
x.set_title("Repeat 80 times. Result: the top is stretched", loc="left", fontsize=10.5, color=INK, fontweight="bold")
x.text(.03, .97, "On the dashed line the two agree.\nBetween the pins they do; above 150\nthe free curves put models ~22% further apart.", transform=x.transAxes, ha="left", va="top", fontsize=8.6, color=MUT)

for x, n in zip(ax[1], ["OTIS Mock AIME 2024-2025", "GPQA diamond", "FrontierMath-Tier-4-v2-Private"]):
    bench(x, n, title={"FrontierMath-Tier-4-v2-Private": "FrontierMath Tier 4 v2"}.get(n))
ax[1, 0].legend(frameon=False, loc="upper left", fontsize=9)
ax[1, 0].set_ylabel("score")
fig.text(.012, .462, "Three benchmarks on the final scale. The free curve mostly follows the logistic and bends where the scores do, typically a slower approach to 100%.", fontsize=10, color=INK)
fig.suptitle("How the free-curve (npca) fit works", x=.012, ha="left", fontsize=15, color=INK, fontweight="bold")
fig.tight_layout(rect=(0, 0, 1, .95), h_pad=6.5)
fig.savefig(ROOT / "figures" / "npca_explainer.png", facecolor="#fbfbf8")
print("wrote figures/npca_explainer.png")
