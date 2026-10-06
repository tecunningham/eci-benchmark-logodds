"""Build plot data from Epoch's ECI files (data/epoch/*.csv, from benchmark_data.zip, 1 Oct 2026 snapshot).

Writes data/frontier_all.json (all labs, from GPT-4 on) and data/frontier_anthropic.json.
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
rel = B.set_index("benchmark_name").benchmark_release_date


def nn(v):
    return None if pd.isna(v) else float(v)


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


def build(E, P, extra=None):
    E = E.sort_values(["date", "eci"])
    F = frontier(E)
    P = P.copy()
    P["p"] = P.performance.clip(EPS, 1 - EPS)
    P["logit"] = np.log(P.p / (1 - P.p))
    P["fr"] = P.Model.isin(set(F.Model))
    out = []
    for b, g in P.groupby("benchmark"):
        g = g.sort_values("date")
        out.append(dict(name=b, rel=str(rel.get(b, "")) or None, area=area(b),
                        fr=pts(g[g.fr]), all=pts(g[~g.fr])))
    out.sort(key=lambda x: (ORDER.index(x["area"]), x["rel"] or "9999"))
    D = dict(
        b=out,
        eci=[[d.strftime("%Y-%m-%d"), m, e, nn(lo), nn(hi)]
             for m, d, e, lo, hi in zip(F.Model, F.date, F.eci, F.eci_ci_low, F.eci_ci_high)],
        alleci=[[d.strftime("%Y-%m-%d"), m, e] for m, d, e in zip(E.Model, E.date, E.eci)],
        nf=int(P.fr.sum()), nall=len(P), areas=ORDER, cols=COL,
    )
    if extra:
        D.update(extra)
    return D


if __name__ == "__main__":
    start = pd.Timestamp("2023-03-14")  # GPT-4
    E, P = E0[E0.date >= start], P0[P0.date >= start]
    json.dump(build(E, P), open(ROOT / "data" / "frontier_all.json", "w"), separators=(",", ":"))

    A = E0[E0.Organization.str.contains("Anthropic", na=False)]
    ov = frontier(E0)
    extra = dict(overall=[[d.strftime("%Y-%m-%d"), m, e] for m, d, e in zip(ov.Model, ov.date, ov.eci)])
    json.dump(build(A, P0[P0.Model.isin(set(A.Model))], extra),
              open(ROOT / "data" / "frontier_anthropic.json", "w"), separators=(",", ":"))
    print("wrote data/frontier_all.json, data/frontier_anthropic.json")
