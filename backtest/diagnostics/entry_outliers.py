"""Entry-print anomalies: SENSEX short legs whose price jumps strongly in the minute after the 09:16 entry bar."""
from common import *
d = cycles('HOLD', 'HOLD_SETTLE'); rows = []
for r in d.itertuples():
    c = Cy.load(r.und, str(r.expiry)[:10]); px = A.Px(c)
    for lid in ('SCE', 'SPE'):
        hm = c['legs'][lid]['hm']; t0 = scen.epoch(c['d1'], hm); p0 = px.bar_open(lid, t0); p1 = px.bar_open(lid, t0 + 60); f = c['frames'][lid][0]; b = f[f.hm == hm]; 
        if not len(b) or not p0 or not p1: continue
        b = b.iloc[0]; prev = f[f.hm < hm]; pc = prev.iloc[-1].close if len(prev) else np.nan
        rows.append(dict(und=r.und, expiry=str(r.expiry)[:10], split=r.split, subset=r.subset, leg=lid, entry_hm=hm, p_prev_close=pc, p0_open=p0, p1_open=p1, drift_pct=100 * (p1 / p0 - 1), vol_entry_bar=b.volume, jump_vs_prev_close_pct=100 * (p0 / pc - 1), K=r.K, net=r.net))
O = pd.DataFrame(rows); O.to_csv(f'{RES}/entry_print_check.csv', index=False)
pd.set_option('display.width', 250)
for u in ('SENSEX', 'NIFTY'):
    x = O[O.und == u]; print(u, 'share |drift|>10%:', (x.drift_pct.abs() > 10).mean().round(3), ' by split:', x.groupby('split').apply(lambda g: (g.drift_pct.abs() > 10).mean()).round(3).to_dict())
print(O[(O.und == 'SENSEX')].sort_values('drift_pct', ascending=False).head(12).round(2).to_string(index=False))
big = O[O.drift_pct.abs() > 10]; print('cycles w/ at least one anomalous short leg:', big.groupby('und').size().to_dict())
