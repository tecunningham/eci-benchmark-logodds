"""Build plot data from Epoch's ECI files (data/epoch/*.csv, from benchmark_data.zip, 1 Oct 2026 snapshot).

Writes
  data/frontier_all.json  frontier across all labs, from GPT-4 on (used by make_figure.py)
  data/eci_data.json      every model and score from GPT-4 on, tagged by lab; the interactive
                          page computes the frontier for whichever lab is chosen
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from areas import area, ORDER, COL

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / "data" / "epoch"
P0 = pd.read_csv(EP / "processed_data_for_eci.csv")  # exact ECI fit input, already floor/ceiling normalised
E0 = pd.read_csv(EP / "eci_scores.csv", parse_dates=["date"])
B = pd.read_csv(EP / "edi_scores.csv")
P0["date"] = P0.Model.map(E0.set_index("Model").date)  # use ECI release dates throughout
EPS = 0.01  # pin 0/1 scores to 1%/99% so log-odds stay finite
START = pd.Timestamp("2023-03-14")  # GPT-4
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
    """Models once, scores as [model index, logit, score]; the page derives each lab's frontier."""
    E = E.sort_values(["date", "eci"]).reset_index(drop=True)
    idx = {m: i for i, m in enumerate(E.Model)}
    P = P[P.Model.isin(idx)].copy()
    P["logit"] = logit(P)
    out = []
    for b, g in P.groupby("benchmark"):
        g = g.sort_values("date")
        out.append(dict(name=b, rel=str(rel.get(b, "")) or None, area=area(b),
                        p=[[idx[m], round(l, 3), round(p, 4)] for m, l, p in zip(g.Model, g.logit, g.performance)]))
    out.sort(key=lambda x: (ORDER.index(x["area"]), x["rel"] or "9999"))
    n = E.lab.value_counts()
    return dict(
        models=[[m, l, d.strftime("%Y-%m-%d"), round(e, 2), nn(lo), nn(hi)]
                for m, l, d, e, lo, hi in zip(E.Model, E.lab, E.date, E.eci, E.eci_ci_low, E.eci_ci_high)],
        labs=sorted([l for l in n[n >= MIN_MODELS].index if l != "Other"], key=lambda l: -n[l]),
        b=out, areas=ORDER, cols=COL, start=START.strftime("%Y-%m-%d"), snapshot="2026-10-01",
    )


if __name__ == "__main__":
    E, P = E0[E0.date >= START], P0[P0.date >= START]
    json.dump(build_all(E, P), open(ROOT / "data" / "frontier_all.json", "w"), separators=(",", ":"))
    json.dump(build_compact(E, P), open(ROOT / "data" / "eci_data.json", "w"), separators=(",", ":"))
    print("wrote data/frontier_all.json, data/eci_data.json")
