"""Underlying during the closing auction (reports/D1_CLOSING_TIME.md). Since 3 Aug 2026 the published index stops at 15:15 (F&O stocks leave
continuous trading), shows indicative auction values 15:20-15:28 (swings of hundreds of points) and the official close from 15:29. Index options
keep trading to 15:40. Two cleaned copies of outputs/bt3x (only post-auction sessions, only minutes j >= 360 = 15:15 onwards are replaced):
  bt3f  frozen:    O=H=L=C = the 15:15 index value (what a continuous index feed shows; no signal after 15:15)
  bt3s  synthetic: O=H=L=C = put-call-parity forward K + C - P (median of the 3 strikes nearest the previous value, option closes)
                   minus its median basis to the index over 15:00-15:14 (close-only bars, so no range is invented)
No fitted parameter. Output outputs/bt3f/, outputs/bt3s/ (git-ignored), outputs/bt3s_basis.csv."""
import os, numpy as np, pandas as pd
OUT = '../outputs'; CAS = '2026-08-03'
for d in ('bt3f', 'bt3s'): os.makedirs(f'{OUT}/{d}', exist_ok=True)
def synth(o, s):
    K = o['K']; n = s.shape[0]; F = np.full(n, np.nan); prev = float(s.close.iloc[300])
    for j in range(300, n):
        idx = np.argsort(np.abs(K - prev))[:3]; v = [K[i] + o[('CE', 'close')][i, j] - o[('PE', 'close')][i, j] for i in idx]; v = [x for x in v if x == x]
        if v: F[j] = float(np.median(v)); prev = F[j]
    return F
if __name__ == '__main__':
    T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; rows = []
    for r in T.itertuples():
        c = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); cf = {k: v for k, v in c.items()}; cs = {k: v for k, v in c.items()}
        for t, d in (('1', r.d1), ('0', r.d0)):
            if d < CAS: continue
            s = c[f'spot{t}']; F = synth(c[f'opt{t}'], s); basis = float(np.nanmedian(F[345:360] - s.close.values[345:360])); froz = float(s.open.iloc[360])
            sf = s.copy(); ss = s.copy(); syn = pd.Series(F[360:] - basis).ffill().fillna(froz).values
            for col in ('open', 'high', 'low', 'close'): sf.loc[360:, col] = froz; ss.loc[360:, col] = syn
            cf[f'spot{t}'] = sf; cs[f'spot{t}'] = ss
            rows.append(dict(und=r.und, expiry=r.expiry, day=t, date=d, basis=basis, frozen=froz, official=c[f'spot_last{t}'], synth_1529=float(syn[374 - 360]), synth_end=float(syn[-1]),
                             indicative_range=float(s.high.iloc[360:375].max() - s.low.iloc[360:375].min()), synth_range=float(syn.max() - syn.min())))
        pd.to_pickle(cf, f'{OUT}/bt3f/{r.und}_{r.expiry}.pkl.gz'); pd.to_pickle(cs, f'{OUT}/bt3s/{r.und}_{r.expiry}.pkl.gz')
    B = pd.DataFrame(rows); B.to_csv(f'{OUT}/bt3s_basis.csv', index=False); B['synth_err_vs_official'] = B.synth_1529 - B.official
    print(B.groupby('und')[['basis', 'indicative_range', 'synth_range', 'synth_err_vs_official']].describe().round(1).T.to_string())
