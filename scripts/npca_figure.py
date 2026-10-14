"""Static small multiples for the README: every benchmark's free monotone curve vs its best sigmoid.
data/npca.json -> figures/npca_curves.png"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
R = json.load(open(ROOT / "data" / "npca.json"))
G = np.arange(R["grid"][0], R["grid"][1] + 0.5, R["grid"][2])
T = np.array([m["t"] for m in R["models"]])
B = sorted(R["b"], key=lambda b: (R["areas"].index(b["area"]), b["logi1"][1]))


def arr(v):
    return np.array([np.nan if x is None else x for x in v])


def rmse(a):
    a = np.array([x for x in a if x is not None])
    return np.sqrt(np.mean(a ** 2))


cols, rows = 10, 6
fig, axs = plt.subplots(rows, cols, figsize=(20, 12.4), sharex=True, sharey=True)
x0, x1 = np.floor(T.min() / 10) * 10, np.ceil(T.max() / 10) * 10
for ax, b in zip(axs.flat, B):
    col = R["cols"][b["area"]]
    t = T[[c[0] for c in b["c"]]]
    y = np.array([c[1] for c in b["c"]])
    s0, s1 = t.min() - 1, t.max() + 1
    on = (G >= s0) & (G <= s1)
    g, lo, hi = arr(b["g1"]), arr(b["lo"]), arr(b["hi"])
    ax.fill_between(G[on], lo[on], hi[on], color="#1d2433", alpha=0.10, lw=0)
    a, d = b["logi1"]
    ax.plot(G, 1 / (1 + np.exp(-a * (G - d))), color="#1d2433", lw=1, ls=(0, (3, 2)), alpha=0.7)
    ax.plot(G, g, color=col, lw=0.8, alpha=0.35)
    ax.plot(G[on], g[on], color=col, lw=2)
    ax.scatter(t, y, s=5, color="#1d2433", alpha=0.45, lw=0)
    cvl = rmse([c[1] - c[6] if c[6] is not None else None for c in b["c"]])
    cvm = rmse([c[1] - c[7] if c[7] is not None else None for c in b["c"]])
    name = b["name"].replace("FrontierMath-", "FM ").replace("-Private", "").replace("OTIS Mock AIME 2024-2025", "OTIS Mock AIME")
    ax.set_title(f"{name[:26]}\n{b['n']} scores · CV {cvl:.3f} → {cvm:.3f}", fontsize=8, loc="left")
    ax.set_xlim(x0, x1); ax.set_ylim(-0.03, 1.03)
    ax.grid(color="#e3e5ea", lw=0.6); ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_color("#d4d7de")
    ax.tick_params(labelsize=7, colors="#5d6577")
for ax in axs.flat[len(B):]:
    ax.axis("off")
fig.suptitle("Each benchmark's free monotone curve (colour, with bootstrap 80% band) vs the best sigmoid on the same θ (dashed). "
             "x: one-factor nonparametric capability θ; y: score. CV = held-out RMSE, sigmoid → free curve.",
             fontsize=11, x=0.01, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.97))
fig.savefig(ROOT / "figures" / "npca_curves.png", dpi=110, facecolor="#fbfbf8")
print("wrote figures/npca_curves.png")
