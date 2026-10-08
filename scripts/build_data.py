"""Build plot data from Epoch's ECI files (data/epoch/*.csv, from benchmark_data.zip, 1 Oct 2026 snapshot).

Writes
  data/frontier_all.json  frontier across all labs, from GPT-4 on (used by make_figure.py)
  data/eci_data.json      every model and score in Epoch's fit, tagged by lab, plus raw fit parameters;
                          the interactive page computes each lab's frontier and can refit ECI
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import eci_fit
from areas import area, ORDER, COL

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / "data" / "epoch"
P0 = pd.read_csv(EP / "processed_data_for_eci.csv")  # exact ECI fit input, already floor/ceiling normalised
E0 = pd.read_csv(EP / "eci_scores.csv", parse_dates=["date"])
B = pd.read_csv(EP / "edi_scores.csv")
P0["date"] = P0.Model.map(E0.set_index("Model").date)  # use ECI release dates throughout
EPS = 0.01  # pin 0/1 scores to 1%/99% so log-odds stay finite
START = pd.Timestamp("2023-03-14")  # GPT-4
ANCHOR_BENCH = "Winogrande"  # Epoch pins its discriminability to 1
MIN_MODELS = 5  # labs with fewer models since START are offered only under "All labs"
rel = B.set_index("benchmark_name").benchmark_release_date

# Lab = first listed organisation, with a few aliases merged and missing ones filled by model family
ALIAS = {"Google": "Google DeepMind", "Microsoft Research": "Microsoft"}
FAMILY = {"PaLM": "Google DeepMind", "Qwen": "Alibaba", "CodeQwen": "Alibaba", "DeepSeek": "DeepSeek", "Yi-": "01.AI"}


def lab(row):
    if isinstance(row.Organization, str):
        o = row.Organization.split(",")[0].strip()
        return ALIAS.get(o, o)
    return next((v for k, v in FAMILY.items() if row.Model.startswith(k)), "Other")


E0["lab"] = E0.apply(lab, axis=1)


def nn(v):
    return None if pd.isna(v) else float(v)


def logit(P):
    p = P.performance.clip(EPS, 1 - EPS)
    return np.log(p / (1 - p))


def frontier(E):
    """Running max of ECI by release date, one model per date (the highest)."""
    E = E.sort_values(["date", "eci"])
    day = E.loc[E.groupby("date").eci.idxmax()].sort_values("date")
    rec, best = [], -1e9
    for r in day.itertuples():
        if r.eci > best:
            best = r.eci
            rec.append(r)
    return pd.DataFrame(rec)


def pts(h):
    return [[d.strftime("%Y-%m-%d"), round(l, 3), round(p, 4), m]
            for d, l, p, m in zip(h.date, h.logit, h.performance, h.Model)]


def build_all(E, P):
    E = E.sort_values(["date", "eci"])
    F = frontier(E)
    P = P.copy()
    P["logit"] = logit(P)
    P["fr"] = P.Model.isin(set(F.Model))
    out = []
    for b, g in P.groupby("benchmark"):
        g = g.sort_values("date")
        out.append(dict(name=b, rel=str(rel.get(b, "")) or None, area=area(b),
                        fr=pts(g[g.fr]), all=pts(g[~g.fr])))
    out.sort(key=lambda x: (ORDER.index(x["area"]), x["rel"] or "9999"))
    return dict(
        b=out,
        eci=[[d.strftime("%Y-%m-%d"), m, e, nn(lo), nn(hi)]
             for m, d, e, lo, hi in zip(F.Model, F.date, F.eci, F.eci_ci_low, F.eci_ci_high)],
        alleci=[[d.strftime("%Y-%m-%d"), m, e] for m, d, e in zip(E.Model, E.date, E.eci)],
        nf=int(P.fr.sum()), nall=len(P), areas=ORDER, cols=COL,
    )


def build_compact(E, P):
    """Every model in Epoch's fit (pre-GPT-4 ones flagged by date) and every score as [model index, score],
    plus our own full refit's raw parameters so the page can warm-start refits on a subset of benchmarks."""
    E = E.sort_values(["date", "eci"]).reset_index(drop=True)
    names = list(E.Model)
    idx = {m: i for i, m in enumerate(names)}
    out = []
    for b, g in P.groupby("benchmark"):
        g = g.sort_values("date")
        out.append(dict(name=b, rel=str(rel.get(b, "")) or None, area=area(b),
                        p=[[idx[m], round(p, 5)] for m, p in zip(g.Model, g.performance)]))
    out.sort(key=lambda x: (ORDER.index(x["area"]), x["rel"] or "9999"))
    mi = np.array([q[0] for o in out for q in o["p"]])
    bi = np.array([k for k, o in enumerate(out) for _ in o["p"]])
    y = np.array([q[1] for o in out for q in o["p"]])
    anchor = [o["name"] for o in out].index(ANCHOR_BENCH)
    cap, dif, dis = eci_fit.fit(y, mi, bi, len(names), len(out), anchor)
    a, sc = eci_fit.to_eci(cap, names)
    print(f"own full fit vs published ECI: max |diff| {np.abs(a + sc * cap - E.eci.values).max():.3f}")
    n = E[E.date >= START].lab.value_counts()
    return dict(
        models=[[m, l, d.strftime("%Y-%m-%d"), round(e, 2), nn(lo), nn(hi)]
                for m, l, d, e, lo, hi in zip(E.Model, E.lab, E.date, E.eci, E.eci_ci_low, E.eci_ci_high)],
        labs=sorted([l for l in n[n >= MIN_MODELS].index if l != "Other"], key=lambda l: -n[l]),
        b=out, areas=ORDER, cols=COL, start=START.strftime("%Y-%m-%d"), snapshot="2026-10-01",
        slope=float(B.estimated_slope_scaled.median()),
        fit=dict(anchor=ANCHOR_BENCH, low=list(eci_fit.ANCHOR_LOW), high=list(eci_fit.ANCHOR_HIGH),
                 reg=eci_fit.REG, clip=eci_fit.CLIP,
                 cap=[round(v, 6) for v in cap], dif=[round(v, 6) for v in dif], dis=[round(v, 6) for v in dis]),
    )


if __name__ == "__main__":
    E, P = E0[E0.date >= START], P0[P0.date >= START]
    json.dump(build_all(E, P), open(ROOT / "data" / "frontier_all.json", "w"), separators=(",", ":"))
    json.dump(build_compact(E0, P0), open(ROOT / "data" / "eci_data.json", "w"), separators=(",", ":"))
    print("wrote data/frontier_all.json, data/eci_data.json")
