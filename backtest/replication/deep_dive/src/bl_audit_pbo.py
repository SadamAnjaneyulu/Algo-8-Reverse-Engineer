"""Audit of the 0.60 probability of backtest overfitting (pre-paper battery gate G4). Independent re-computation of CSCV on the saved weekly matrix, plus a noise null with the same shape
(158 weeks x 41 columns, mean pairwise correlation 0.95, zero true differences between columns). Not about the late-sale score: it measures whether tuning the SIMULATOR has out-of-sample value.
Output outputs/audit/pbo_audit.json."""
import sys, os, json, glob, itertools, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); PP = f'{OUT}/prepaper'; AU = f'{OUT}/audit'; rng = np.random.default_rng(1234)
def cscv(M, S_=16):
    T_, n = M.shape; blocks = np.array_split(np.arange(T_), S_); lam = []; star = []
    for comb in itertools.combinations(range(S_), S_ // 2):
        isx = np.concatenate([blocks[i] for i in comb]); oos = np.concatenate([blocks[i] for i in range(S_) if i not in comb]); a = M[isx]; b = M[oos]
        s_is = a.mean(0) / a.std(0, ddof=1); s_oos = b.mean(0) / b.std(0, ddof=1); k = int(np.argmax(s_is)); w = (np.sum(s_oos < s_oos[k]) + 1) / (n + 1); lam.append(np.log(w / (1 - w))); star.append(k)
    lam = np.array(lam); return float((lam <= 0).mean()), np.array(star), lam
if __name__ == '__main__':
    V = pd.concat([pd.read_csv(f) for f in glob.glob(f'{PP}/var_*.csv')]); V = V[V.ok]; V['wk'] = pd.to_datetime(V.d0).dt.strftime('%G-%V')
    cand = ['full'] + sorted(v for v in V.variant.unique() if v != 'full' and not v.startswith('null')); W = V[V.variant.isin(cand)].pivot_table(index='wk', columns='variant', values='net', aggfunc='sum').sort_index().fillna(0.0)[cand]; M = W.values
    pbo, star, lam = cscv(M); chosen = pd.Series(np.array(cand)[star]).value_counts(normalize=True)
    # noise null: common factor + idiosyncratic noise, corr rho between columns, same mean level and scale, zero true column differences
    rho = float(np.corrcoef(M.T)[np.triu_indices(M.shape[1], 1)].mean()); mu = M.mean(); sd = M.std(0, ddof=1).mean(); T_, n = M.shape; nulls = []
    for _ in range(60):
        f = rng.normal(size=(T_, 1)); e = rng.normal(size=(T_, n)); X = mu + sd * (np.sqrt(rho) * f + np.sqrt(1 - rho) * e); nulls.append(cscv(X)[0])
    nulls = np.array(nulls)
    # same, but with column differences = the observed spread of the column Sharpe ratios (i.e. true differences exist, as large as observed)
    sr = M.mean(0) / M.std(0, ddof=1); res = dict(weeks=int(T_), columns=int(n), mean_pairwise_corr=rho, PBO_recomputed=pbo, PBO_reported=0.60, share_is_best_is_full=float(chosen.get('full', 0.0)), top_is_best=chosen.head(5).round(3).to_dict(),
        noise_null_PBO_mean=float(nulls.mean()), noise_null_PBO_p05=float(np.quantile(nulls, .05)), noise_null_PBO_p95=float(np.quantile(nulls, .95)), observed_in_null_pctile=float((nulls < pbo).mean()),
        sharpe_spread=dict(full=float(sr[0]), min=float(sr.min()), max=float(sr.max()), sd=float(sr.std(ddof=1))), median_logit=float(np.median(lam)))
    json.dump(res, open(f'{AU}/pbo_audit.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
