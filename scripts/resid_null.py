"""What the residual viewer would show if Epoch's logistic were exactly true: a parametric bootstrap.

The residual tab plots every score against its model's fitted ECI with a kernel-smoothed local average.
Even when the logistic holds, that average is not flat at zero:
  * each model's ECI is estimated from these same scores (own-score leverage shrinks residuals),
  * ECI is a noisy estimate, so scores plotted against it flatten at the extremes (errors in variables),
  * scores of 0% / 100% are pinned at 1% / 99% in log-odds, and a noisy score near the floor is often 0,
    which pulls log-odds tails towards the middle.
To give the eye the right yardstick, simulate scores from the fitted model, refit ECI exactly as Epoch
does (scripts/eci_fit.py), and record the same statistics the page computes.

Noise model: score = Binomial(N_b, p) / N_b, with p = sigmoid(slope_b (ECI - difficulty_b)) from the
fit, and N_b chosen per benchmark so the simulated in-sample RMSE matches the real one. Real residual SDs
scale like sqrt(p(1-p)) (about 0.18 sqrt(p(1-p)) overall, i.e. ~30 effective items), and this reproduces
the share of exact zeros near the floor.

Writes data/resid_null.json, per benchmark (in the page's benchmark order):
  grid      ECI grid of the page's local average (49 points over the benchmark's observed range)
  band      {mode: [lo[], hi[]]}: simultaneous 90% band for the local average, as a deviation from the
            fitted curve (modes: rl = log-odds residual, rs = score residual; the band is the same whether
            drawn around the zero line or the fitted curve, since it is measured relative to the fit)
  mis, p    the page's misfit statistic (RMS of the local average of log-odds residuals) and the share of
            simulations at least as large
plus global summaries. Run: python scripts/resid_null.py [--sims 200]   (~5 min on 4 cores)
"""
import argparse, json, sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import eci_fit  # noqa: E402

EPS = 0.01
LGMAX = np.log((1 - EPS) / EPS)
D = json.load(open(ROOT / "data" / "eci_data.json"))
NAMES = [m[0] for m in D["models"]]
NM, NB = len(NAMES), len(D["b"])
MI = np.array([q[0] for b in D["b"] for q in b["p"]])
BI = np.array([k for k, b in enumerate(D["b"]) for _ in b["p"]])
Y = np.array([q[1] for b in D["b"] for q in b["p"]])
ANCHOR = [b["name"] for b in D["b"]].index(D["fit"]["anchor"])
CAP, DIF, DIS = (np.array(D["fit"][k]) for k in ("cap", "dif", "dis"))
DATE = np.array([np.datetime64(m[2]) for m in D["models"]])


def to_eci_params(cap, dif, dis):
    a, sc = eci_fit.to_eci(cap, NAMES)
    return a + sc * cap, a + sc * dif, dis / sc        # ECI, difficulty, slope (logits per ECI point)


ECI0, EDI0, SL0 = to_eci_params(CAP, DIF, DIS)
SIG = lambda z: 1 / (1 + np.exp(-z))
LG = lambda y: np.log(np.clip(y, EPS, 1 - EPS) / (1 - np.clip(y, EPS, 1 - EPS)))

# the page's local-average grid and bandwidth, from the real (published-fit) ECI range of each benchmark
GRID, H = [], []
for k in range(NB):
    x = ECI0[MI[BI == k]]
    lo, hi = x.min(), x.max()
    GRID.append(lo + (hi - lo) * np.arange(49) / 48)
    H.append(max(2.5, (hi - lo) / 7))


def smooth(x, y, k):
    w = np.exp(-0.5 * ((x[None, :] - GRID[k][:, None]) / H[k]) ** 2)
    sw = w.sum(1)
    out = (w @ y) / sw
    out[sw < 3] = np.nan
    return out


def stats(y, eci, edi, sl):
    """Per benchmark: local average of log-odds and score residuals on the grid, and the misfit statistic."""
    out = []
    for k in range(NB):
        m = BI == k
        x, yy = eci[MI[m]], y[m]
        z = sl[k] * (x - edi[k])
        rl = LG(yy) - np.clip(z, -LGMAX, LGMAX)
        rs = yy - SIG(z)
        sl_, ss = smooth(x, rl, k), smooth(x, rs, k)
        v = sl_[np.isfinite(sl_)]
        out.append(dict(rl=sl_, rs=ss, mis=float(np.sqrt((v ** 2).mean())) if m.sum() > 4 and len(v) else 0.0))
    return out


def one(args):
    seed, N = args
    rng = np.random.default_rng(seed)
    p = SIG(DIS[BI] * (CAP[MI] - DIF[BI]))
    y = rng.binomial(N[BI], p) / N[BI]
    cap, dif, dis = eci_fit.fit(y, MI, BI, NM, NB, ANCHOR, anchor_disc=DIS[ANCHOR],
                                x0=np.concatenate([CAP, DIF, DIS]))
    eci, edi, sl = to_eci_params(cap, dif, dis)
    z = sl[BI] * (eci[MI] - edi[BI])
    rmse = np.array([np.sqrt(((y[BI == k] - SIG(z[BI == k])) ** 2).mean()) for k in range(NB)])
    return stats(y, eci, edi, sl), rmse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=200)
    S = ap.parse_args().sims
    p0 = SIG(SL0[BI] * (ECI0[MI] - EDI0[BI]))
    real_rmse = np.array([np.sqrt(((Y[BI == k] - p0[BI == k]) ** 2).mean()) for k in range(NB)])
    pq = np.array([(p0[BI == k] * (1 - p0[BI == k])).mean() for k in range(NB)])
    # calibrate effective items per benchmark: start from the in-sample match, then correct once for the
    # shrinkage of in-sample residuals by refitting
    N = np.clip(np.round(pq / real_rmse ** 2), 3, 5000).astype(int)
    t = time.time()
    with Pool() as pool:
        cal = pool.map(one, [(10_000 + s, N) for s in range(24)])
        sim_rmse = np.mean([c[1] for c in cal], 0)
        N = np.clip(np.round(N * (sim_rmse / real_rmse) ** 2), 3, 5000).astype(int)
        print(f"calibrated N_b (median {np.median(N):.0f}, range {N.min()}-{N.max()}) in {time.time() - t:.0f}s")
        res = pool.map(one, [(s, N) for s in range(S)])
    sims = [r[0] for r in res]
    sim_rmse = np.mean([r[1] for r in res], 0)
    print(f"{S} sims in {time.time() - t:.0f}s; pooled RMSE real {np.sqrt((real_rmse ** 2).mean()):.4f} "
          f"sim {np.sqrt((sim_rmse ** 2).mean()):.4f}")
    real = stats(Y, ECI0, EDI0, SL0)

    def band(k, mode):
        A = np.array([s[k][mode] for s in sims])                      # sims x grid
        med = np.nanmedian(A, 0)
        sd = np.nanstd(A, 0)
        sd[~(sd > 0)] = np.nan
        t = np.nanmax(np.abs(A - med) / sd, 1)                         # each sim's worst standardised excursion
        c = np.nanquantile(t, 0.9)
        return [[None if not np.isfinite(v) else round(float(v), 4) for v in med - c * sd],
                [None if not np.isfinite(v) else round(float(v), 4) for v in med + c * sd]]

    out, ps = [], []
    for k, b in enumerate(D["b"]):
        null = np.array([s[k]["mis"] for s in sims])
        p = float((1 + (null >= real[k]["mis"] - 1e-12).sum()) / (1 + S))
        ps.append(p)
        out.append(dict(name=b["name"], N=int(N[k]), grid=[round(float(g), 3) for g in GRID[k]],
                        band=dict(rl=band(k, "rl"), rs=band(k, "rs")),
                        mis=round(real[k]["mis"], 4), null_mis=round(float(null.mean()), 4), p=round(p, 4)))
    # joint test across benchmarks: sum of misfit^2 relative to its null mean, against the same sum per sim
    nm = np.array([o["null_mis"] for o in out])
    T = lambda mis: float(np.sum(np.array(mis) ** 2 / nm ** 2))
    Treal = T([o["mis"] for o in out])
    Tnull = np.array([T([s[k]["mis"] for k in range(NB)]) for s in sims])
    p_all = float((1 + (Tnull >= Treal).sum()) / (1 + S))
    ps = np.array(ps)
    summary = dict(sims=S, n_p05=int((ps <= 0.05).sum()), n_p01=int((ps <= 0.01).sum()), expected_p05=round(0.05 * NB, 1),
                   T=round(Treal, 1), T_null=[round(float(np.quantile(Tnull, q)), 1) for q in (0.05, 0.5, 0.95)],
                   p_all=round(p_all, 4))
    print(json.dumps(summary))
    for o in sorted(out, key=lambda o: o["p"])[:12]:
        print(f"  {o['name'][:40]:40s} misfit {o['mis']:.2f} (null mean {o['null_mis']:.2f})  p {o['p']:.3f}  N {o['N']}")
    json.dump(dict(summary=summary, b=out), open(ROOT / "data" / "resid_null.json", "w"), separators=(",", ":"))
    print("wrote data/resid_null.json")


if __name__ == "__main__":
    main()
