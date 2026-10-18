"""figures/npca_links.png: held-out error of each way of fitting a benchmark's curve, relative to the logistic."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
L = json.load(open(ROOT / "data" / "npca_links.json"))
O = L["options"]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), dpi=150, sharey=True)
ys = list(range(len(O)))[::-1]
for ax, key, title in [(axes[0], "drandom", "Random held-out scores (5-fold)"),
                       (axes[1], "dforward", f"Later models (curves fit before {L['cut'][:7]})")]:
    ax.axvline(0, color="#1d2433", lw=1)
    for y, o in zip(ys, O):
        pt, lo, hi = o[key]
        c = "#2f5bd3" if hi < 0 else "#d9480f" if lo > 0 else "#5d6577"
        ax.plot([lo, hi], [y, y], color=c, lw=2.2, solid_capstyle="round")
        ax.plot(pt, y, "o", color=c, ms=7, mec="white", mew=1)
        ax.text(hi + 0.4, y, f"{pt:+.1f}%", va="center", fontsize=8.5, color=c)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("Change in RMSE vs the logistic (%)  ·  lower is better")
    ax.grid(axis="x", alpha=.3)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_yticks(ys)
axes[0].set_yticklabels([o["label"] for o in O])
fig.suptitle("Ways to fit each benchmark's curve of capability: held-out error vs ECI's logistic\n"
             "Model capabilities fixed at ECI fitted on training scores only; bars = 90% interval from resampling models",
             fontsize=11)
fig.tight_layout()
fig.savefig(ROOT / "figures" / "npca_links.png")
print("wrote figures/npca_links.png")
