"""Approximate inference cost per model, from the run costs that benchmarks report.

Epoch's benchmark_data.zip has no price table, but 15 benchmark files give what each run cost in dollars (per task,
per run or in total). Costs differ by orders of magnitude between benchmarks, so fit
    log10(cost) = model effect + benchmark effect
by least squares over (model, benchmark) pairs, and call 10^(model effect) the model's cost index: roughly, dollars
per task on a typical benchmark. Where the benchmark's score column is known (benchmark_metadata.csv), a model's
cost on that benchmark is the cost of its best-scoring version, since that is the score ECI uses; otherwise the
median over its versions and settings.

Caveats: it is what each benchmark's runner paid (list price x tokens used, with their harness and reasoning
setting, at prices on the day), not a price per token; a model with costs on only 2-3 benchmarks can be off by a
factor of two or more; about a third of ECI models have no cost at all.

Run: python cost_index.py path/to/benchmark_data.zip   -> data/cost_index.json
"""
import io, json, sys, zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COST = {"aider_polyglot_external.csv": "Cost", "ale_bench_external.csv": "Cost", "arc_agi_2_external.csv": "Cost per task",
        "arc_agi_external.csv": "Cost per task", "critpt_external.csv": "Cost", "cursorbench_external.csv": "Cost per task",
        "deepswe_external.csv": "Mean cost (USD)", "exploitbench_external.csv": "Spend", "frontierswe_external.csv": "Average cost (USD)",
        "osworld_2_external.csv": "Estimated cost (USD)", "proofbench_external.csv": "Cost per test (USD)",
        "surface_evolver_bench_external.csv": "Total cost (USD)", "the_agent_company_external.csv": "Average costs",
        "weirdml_external.csv": "Cost per run", "weirdml_v3_external.csv": "Cost per run"}


def main(zip_path):
    zf = zipfile.ZipFile(zip_path)
    rd = lambda n: pd.read_csv(io.BytesIO(zf.read(n)), low_memory=False)
    mm = rd("model_metadata.csv").dropna(subset=["model_version"])[["model_version", "model_group"]]
    score_col = rd("benchmark_metadata.csv").drop_duplicates("source_file").set_index("source_file").score_column
    eci = pd.read_csv(ROOT / "data" / "epoch" / "eci_scores.csv")
    pairs = []
    for f, c in COST.items():
        d = rd(f)
        t = pd.DataFrame(dict(model_version=d["Model version"], bench=f.replace("_external.csv", "").replace(".csv", ""),
                              cost=pd.to_numeric(d[c].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce"),
                              score=pd.to_numeric(d[score_col[f]], errors="coerce") if f in score_col.index and score_col[f] in d else np.nan))
        t = t[t.cost > 0].merge(mm, on="model_version")
        t = t[t.model_group.isin(eci.Model)]
        for (g, b), x in t.groupby(["model_group", "bench"]):
            pairs.append((g, b, x.loc[x.score.idxmax(), "cost"] if x.score.notna().any() else x.cost.median()))
    G = pd.DataFrame(pairs, columns=["model", "bench", "cost"])
    G["lc"] = np.log10(G.cost)

    def fit(G):
        ms, bs = sorted(G.model.unique()), sorted(G.bench.unique())
        X = np.zeros((len(G), len(ms) + len(bs)))
        X[np.arange(len(G)), [ms.index(m) for m in G.model]] = 1
        X[np.arange(len(G)), [len(ms) + bs.index(b) for b in G.bench]] = 1
        coef = np.linalg.lstsq(np.vstack([X, 1e-3 * np.eye(X.shape[1])]), np.r_[G.lc, np.zeros(X.shape[1])], rcond=None)[0]
        res = G.lc - X @ coef
        return pd.Series(coef[:len(ms)] + coef[len(ms):].mean(), index=ms), 1 - res.var() / G.lc.var(), res.std()

    idx, r2, sd = fit(G)
    n = G.groupby("model").bench.nunique()
    # how much the index depends on any one benchmark: refit without each, compare on the models that remain
    loo = []
    for b in sorted(G.bench.unique()):
        alt, _, _ = fit(G[G.bench != b])
        k = alt.index.intersection(idx.index)
        d = (alt[k] - alt[k].mean()) - (idx[k] - idx[k].mean())
        loo.append((b, float(np.sqrt((d ** 2).mean())), float(d.abs().max())))
    out = dict(pairs=len(G), r2=round(float(r2), 3), resid_factor=round(float(10 ** sd), 2), benchmarks=sorted(G.bench.unique()),
               models={m: [float(f"{10 ** idx[m]:.3g}"), int(n[m])] for m in idx.index})
    json.dump(out, open(ROOT / "data" / "cost_index.json", "w"), separators=(",", ":"))
    print(f"{len(G)} pairs, {len(idx)} of {len(eci)} ECI models, R2 {r2:.3f}, residual factor x{10 ** sd:.2f}")
    print("dropping one benchmark changes the index by (rms factor, max factor):")
    for b, r, mx in sorted(loo, key=lambda t: -t[1])[:6]:
        print(f"  {b:24s} x{10 ** r:.2f}  x{10 ** mx:.2f}")
    e = eci.set_index("Model").eci
    for m in e.sort_values(ascending=False).index[:14]:
        print(f"  {m:22s} ECI {e[m]:.1f}  cost index {out['models'][m][0] if m in out['models'] else '-'}  ({out['models'].get(m, [0, 0])[1]} benchmarks)")


if __name__ == "__main__":
    main(sys.argv[1])
