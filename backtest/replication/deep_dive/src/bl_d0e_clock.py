"""Is 'other solo' a clock-driven stream? (post-hoc, after the hour/clock-minute finding in bl_d0e_more.py; labelled post-hoc.)
(1) leave-one-cycle-out recurrence of sale times (+-2 s) per slice against a +-120..180 s shifted null, with cycle-bootstrap CI;
(2) the recurring clock times of other solo per underlying x version; (3) minute-cell AUC with a clock-only feature (how many other cycles of the same underlying x version sold other-solo in that minute of the day, on that right), alone and added to V1.
Outputs bl_d0e_clock1.csv, bl_d0e_clock_times.csv, bl_d0e_clock_auc.csv, bl_summary_d0e3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
exec(open('bl_d0e_repl.py').read().split("# ---------------- E1")[0])
order = PN.groupby('cid').expiry.first().sort_values(); tr = list(order.index[:int(len(order) * 2 / 3)]); te_c = list(order.index[int(len(order) * 2 / 3):]); R = {}
def cov(sub, shift=0, w=2):
    hit = 0; n = 0
    for (u, v), g in sub.groupby(['und', 'version']):
        for c in g.cid.unique():
            t = g[g.cid == c].tod.values + shift; o = np.sort(g[g.cid != c].tod.values)
            if len(o) == 0: continue
            k = np.searchsorted(o, t); d = np.minimum(np.abs(o[np.clip(k, 0, len(o) - 1)] - t), np.abs(o[np.clip(k - 1, 0, len(o) - 1)] - t)); hit += int((d <= w).sum()); n += len(t)
    return hit / max(n, 1)
rows = []
from scipy.stats import binomtest
def cov_cycle(sub, shift=0, w=2):
    out = {}
    for (u, v), g in sub.groupby(['und', 'version']):
        for c in g.cid.unique():
            t = g[g.cid == c].tod.values + shift; o = np.sort(g[g.cid != c].tod.values)
            if len(o) == 0: continue
            k = np.searchsorted(o, t); d = np.minimum(np.abs(o[np.clip(k, 0, len(o) - 1)] - t), np.abs(o[np.clip(k - 1, 0, len(o) - 1)] - t)); out[c] = float((d <= w).mean())
    return out
for sl in ['other solo', 'replacement solo', 'far-OTM solo', 'counter-sell solo', 'extreme solo']:
    sub = SO[SO.slice == sl]; real = cov(sub); nul = np.mean([cov(sub, s) for s in (150, -150, 120, -120, 180, -180)])
    pr = cov_cycle(sub); pn = {c: np.mean([cov_cycle(sub, s).get(c, np.nan) for s in (150, -150, 120, -120, 180, -180)]) for c in pr}; above = sum(1 for c in pr if pr[c] > pn[c]); n_c = sum(1 for c in pr if pr[c] == pr[c])
    rows.append(dict(slice=sl, orders=len(sub), loco_share_on_other_cycles_times=real, null_share=nul, ratio=real / max(nul, 1e-9), cycles_above_null=above, cycles=n_c, sign_test_p=float(binomtest(above, n_c, 0.5, alternative='greater').pvalue))); print(rows[-1])
C1 = pd.DataFrame(rows); C1.round(4).to_csv(f'{OUT}/bl_d0e_clock1.csv', index=False)
# ---- recurring times of other solo
OS = SO[SO.slice == 'other solo'].copy(); OS['sec'] = OS.tod.round().astype(int); tt = []
for (u, v), g in OS.groupby(['und', 'version']):
    ncyc = g.cid.nunique(); s = np.sort(g.sec.values); used = np.zeros(len(s), bool)
    for a in range(len(s)):
        if used[a]: continue
        m = (np.abs(s - s[a]) <= 2) & ~used; sel = g[np.isin(g.sec.values, s[m])]
        if sel.cid.nunique() >= 3: tt.append(dict(und=u, version=v, clock=f'{int(s[a] // 3600):02d}:{int(s[a] % 3600 // 60):02d}:{int(s[a] % 60):02d}', cycles=int(sel.cid.nunique()), of_cycles=ncyc, orders=len(sel), lots=int(sel.lots.sum()), CE_share=float((sel.cp == 'CE').mean())))
        used |= m
CT = pd.DataFrame(tt).sort_values(['und', 'version', 'clock']); CT.to_csv(f'{OUT}/bl_d0e_clock_times.csv', index=False); print(len(CT), 'recurring clock times (>=3 cycles)'); print(CT.groupby(['und', 'version']).agg(times=('clock', 'size'), orders=('orders', 'sum')).to_string())
tot = len(OS); cov_ = CT.orders.sum(); R['recurring_times'] = int(len(CT)); R['orders_at_recurring_times_share'] = float(cov_ / tot)
# ---- cell AUC: clock-only feature built LOCO (other cycles of the same und x version)
OS['m'] = OS.j; cntrow = {}
for (u, v), g in PN.groupby(['und', 'version']):
    cyc = g.cid.unique()
    for c in cyc:
        oth = OS[(OS.und == u) & (OS.version == v) & (OS.cid != c)]; n_other = max(len([x for x in cyc if x != c]), 1)
        for cp in ('CE', 'PE'):
            o2 = oth[oth.cp == cp].groupby('m').cid.nunique(); idx = g[(g.cid == c) & (g.cp == cp)].index
            PN.loc[idx, 'clock_share'] = g.loc[idx, 'j'].map(o2).fillna(0).values / n_other
            o3 = oth.groupby('m').cid.nunique(); PN.loc[idx, 'clock_share_any'] = g.loc[idx, 'j'].map(o3).fillna(0).values / n_other
def clock_fw(ref_cycles):
    """clock feature for the forward check: reference cycles are the training cycles only (train cells exclude their own cycle)"""
    out1 = pd.Series(0.0, index=PN.index); out2 = pd.Series(0.0, index=PN.index)
    for (u, v), g in PN.groupby(['und', 'version']):
        for c in g.cid.unique():
            refc = [x for x in ref_cycles if x != c and x in set(g.cid.unique())]
            if not refc: continue
            oth = OS[(OS.und == u) & (OS.version == v) & OS.cid.isin(refc)]
            for cp in ('CE', 'PE'):
                idx = g[(g.cid == c) & (g.cp == cp)].index; o2 = oth[oth.cp == cp].groupby('m').cid.nunique(); out1.loc[idx] = g.loc[idx, 'j'].map(o2).fillna(0).values / len(refc)
                o3 = oth.groupby('m').cid.nunique(); out2.loc[idx] = g.loc[idx, 'j'].map(o3).fillna(0).values / len(refc)
    return out1, out2
PN['clock_share_fw'], PN['clock_share_any_fw'] = clock_fw(tr)
cs = OS[OS.row >= 0].groupby('row').lots.sum(); PN['y_other'] = PN.row.map(cs).fillna(0).gt(0).astype(float); G['clock'] = ['clock_share', 'clock_share_any']; V1 = ['base', 'spot', 'prem', 'book', 'bb']
au = []
def one(nm, cols):
    p = loco(PN, cols, 'y_other'); sc = score(PN, p, 'y_other'); cf = [c_.replace('clock_share', 'clock_share') + ('_fw' if c_.startswith('clock_share') else '') for c_ in cols]; m = mk().fit(PN[PN.cid.isin(tr)][cf].values, PN[PN.cid.isin(tr)].y_other.values); d = PN[PN.cid.isin(te_c)]; sc['forward_auc'] = roc_auc_score(d.y_other, m.predict_proba(d[cf].values)[:, 1]); au.append(dict(model=nm, features=len(cols), **sc)); print(nm, round(sc['auc'], 3), round(sc['within_cycle_auc'], 3), round(sc['forward_auc'], 3))
one('clock feature only (other cycles\' times, +/-0 min)', G['clock']); one('clock feature + clock position (minute in block, hour)', G['clock'] + ['hour', 'min_in_15', 'min_in_5'])
one('V1 causal (market / book / past buy-backs)', sum([G[g] for g in V1], [])); one('V1 + clock feature', sum([G[g] for g in V1 + ['clock']], []))
cols = G['clock'] + ['hour', 'min_in_15']; au.append(dict(model='placebo (clock + position shuffled within cycle)', features=len(cols), **score(PN, loco(PN, cols, 'y_other', perm=True), 'y_other'), forward_auc=np.nan))
AU = pd.DataFrame(au); AU.round(4).to_csv(f'{OUT}/bl_d0e_clock_auc.csv', index=False)
rec('d0e3', dict(clock=C1.round(4).to_dict('records'), auc=AU.round(4).to_dict('records'), **R))
