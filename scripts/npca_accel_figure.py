"""figures/npca_accel.png: frontier capability under each benchmark curve, and whether its last-year growth settles."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
A = json.load(open(ROOT / "data" / "npca_accel.json"))
COL = dict(logistic="#1d2433", four_pl="#8b3dff", cloglog="#e8177d", shared="#00a86b", monotone="#1d64f2",
           logit_spline="#00b4d8", monotone_weak="#5b8def", monotone_free="#9db8f5", monotone_q="#ff7a00", item_mixture="#f4a259")
w0, w1, w2 = (pd.Timestamp(w) for w in A["windows"])

fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.6), dpi=150, gridspec_kw=dict(width_ratios=[1.15, 1]))
a1.axvspan(w0, w1, color="#1d2433", alpha=.05, lw=0)
a1.axvspan(w1, w2, color="#1d2433", alpha=.10, lw=0)
pub = A["published"]["frontier"]
a1.plot([pd.Timestamp(f[0]) for f in pub], [f[2] for f in pub], "--", color="#5d6577", lw=1.8,
        label=f"Published ECI: {A['published']['prev']:.1f} → {A['published']['last']:.1f}")
for v in A["variants"]:
    if not v["settles"]:
        continue
    f = v["frontier"]
    a1.plot([pd.Timestamp(x[0]) for x in f], [x[2] for x in f], "-o", ms=3, color=COL[v["key"]], lw=2.6 if v["key"] == "logistic" else 1.8,
            label=f"{v['label']}: {v['prev']:.1f} → {v['last']:.1f}" + (f" (sped up in {100 * v['ci']['p_accel']:.0f}%)" if v["ci"] else ""))
a1.set_xlim(pd.Timestamp("2024-01-01"), w2)
import matplotlib.dates as mdates
a1.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
a1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
a1.set_ylim(125, max(v["frontier"][-1][2] for v in A["variants"] if v["settles"]) + 3)
a1.set_ylabel("Frontier capability (ECI scale; Claude 3.5 Sonnet 130, GPT-5 150)")
a1.set_title("Frontier under each curve that settles\nlegend: growth in ECI points/yr, previous 12 months → last 12 months", fontsize=10.5)
a1.legend(fontsize=8, loc="upper left", frameon=False)
a1.grid(alpha=.3)
ends = []
for v in A["variants"]:
    p = [x[1] for x in v["path"]]
    a2.plot(range(1, len(p) + 1), p, "-" if v["settles"] else "--", color=COL[v["key"]], lw=2.2 if v["settles"] else 1.6)
    ends.append([p[-1], p[-1], v])
ends.sort(key=lambda e: e[0])
for k in range(1, len(ends)):           # spread end labels at least 1.4 points apart
    ends[k][1] = max(ends[k][1], ends[k - 1][1] + 1.4)
n = len(A["variants"][0]["path"])
for y, ly, v in ends:
    a2.annotate(v["label"].replace("One free shape shared by all benchmarks", "Shared shape").replace(" (npca, pull 10)", " (npca)")
                .replace("Piecewise-linear, knots at model quantiles (pull 10)", "PL, knots at model quantiles"),
                xy=(n, y), xytext=(n + 4, ly), fontsize=7.5, color=COL[v["key"]], va="center",
                arrowprops=dict(arrowstyle="-", lw=.5, color=COL[v["key"]]))
a2.axhline(A["published"]["last"], color="#5d6577", ls=":", lw=1)
a2.set_xlim(0, len(A["variants"][0]["path"]) * 1.42)
a2.set_xlabel("Round of fitting (curves ↔ model positions), from published ECI")
a2.set_ylabel("Last-12-month frontier growth (ECI points/yr)")
a2.set_title("Which answers settle? Dashed: curves free per benchmark keep stretching\nthe top of the axis, so their acceleration is set by the penalty", fontsize=10.5)
a2.grid(alpha=.3)
for a in (a1, a2):
    a.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(ROOT / "figures" / "npca_accel.png")
print("wrote figures/npca_accel.png")
