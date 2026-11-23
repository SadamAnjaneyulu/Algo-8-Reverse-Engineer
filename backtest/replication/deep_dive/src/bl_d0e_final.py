"""Consequences of the SENSEX strangle timetable (post-hoc): relabel, re-run the AUC gate for strangle cells, and re-check the counter-sell and replacement AUCs with strangle legs taken out.
Outputs bl_d0e_fin_relabel.csv, bl_d0e_fin_auc.csv, bl_summary_d0e5.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
exec(open('bl_d0e_repl.py').read().split("# ---------------- E1")[0])
PR = pd.read_csv(f'{OUT}/bl_d0e_str_pairs.csv'); STR = PR[PR.dk == 2]; R = {}
leg_idx = set(STR.ce_idx) | set(STR.pe_idx); SO['strangle'] = SO.index.isin(leg_idx)
RL = SO.groupby(['slice', 'strangle']).lots.sum().unstack().fillna(0).astype(int); RL.columns = ['not a strangle leg', 'strangle leg']; RL['strangle share of slice'] = RL['strangle leg'] / RL.sum(axis=1); RL.to_csv(f'{OUT}/bl_d0e_fin_relabel.csv'); print(RL.to_string())
R['strangle_lots'] = int(SO[SO.strangle].lots.sum()); R['strangle_by_slice'] = SO[SO.strangle].groupby('slice').lots.sum().to_dict()
order = PN.groupby('cid').expiry.first().sort_values(); tr = list(order.index[:int(len(order) * 2 / 3)]); te_c = list(order.index[int(len(order) * 2 / 3):])
SL = SO[SO.strangle & (SO.row >= 0)]
def clock(ref_cycles, ev):
    out = pd.Series(0.0, index=PN.index)
    for (u, v), g in PN.groupby(['und', 'version']):
        cyc = set(g.cid.unique())
        for c in cyc:
            refc = [x for x in ref_cycles if x != c and x in cyc]
            if not refc: continue
            e = ev[(ev.und == u) & (ev.version == v) & ev.cid.isin(refc)]; m = e.groupby('j').cid.nunique(); idx = g[g.cid == c].index; out.loc[idx] = g.loc[idx, 'j'].map(m).fillna(0).values / len(refc)
    return out
allc = list(PN.cid.unique()); PN['str_clock'] = clock(allc, SL); PN['str_clock_fw'] = clock(tr, SL)
cs = SL.groupby('row').lots.sum(); PN['y_strangle'] = PN.row.map(cs).fillna(0).gt(0).astype(float)
for sl, yc in (('counter-sell solo', 'y_counter_ns'), ('replacement solo', 'y_repl_ns'), ('other solo', 'y_other_ns')):
    c_ = SO[(SO.row >= 0) & (SO.slice == sl) & ~SO.strangle].groupby('row').lots.sum(); PN[yc] = PN.row.map(c_).fillna(0).gt(0).astype(float)
G['strclock'] = ['str_clock']; V1 = ['base', 'spot', 'prem', 'book', 'bb']; rows = []
def one(nm, yc, gs, fw=False):
    cols = sum([G[g] for g in gs], []); p = loco(PN, cols, yc); sc = score(PN, p, yc); cf = [('str_clock_fw' if c_ == 'str_clock' else c_) for c_ in cols]
    m = mk().fit(PN[PN.cid.isin(tr)][cf].values, PN[PN.cid.isin(tr)][yc].values); d = PN[PN.cid.isin(te_c)]; fwd = roc_auc_score(d[yc], m.predict_proba(d[cf].values)[:, 1]) if d[yc].nunique() > 1 else np.nan
    rows.append(dict(outcome=yc, model=nm, cells=int(PN[yc].sum()), auc=sc['auc'], lo=sc['lo'], hi=sc['hi'], within_cycle_auc=sc['within_cycle_auc'], forward_auc=fwd)); print(rows[-1])
one('clock feature only (strangle times of other cycles)', 'y_strangle', ['strclock']); one('clock + clock position', 'y_strangle', ['strclock', 'base']); one('V1 causal', 'y_strangle', V1); one('V1 + clock feature', 'y_strangle', V1 + ['strclock'])
for yc in ('y_counter_ns', 'y_repl_ns', 'y_other_ns'): one('V1 causal, strangle legs removed from the outcome', yc, V1)
cols = ['str_clock', 'hour', 'min_in_15']; pl = score(PN, loco(PN, cols, 'y_strangle', perm=True), 'y_strangle'); rows.append(dict(outcome='y_strangle', model='placebo (clock + position shuffled within cycle)', cells=int(PN.y_strangle.sum()), auc=pl['auc'], lo=pl['lo'], hi=pl['hi'], within_cycle_auc=pl['within_cycle_auc'], forward_auc=np.nan))
A = pd.DataFrame(rows); A.round(4).to_csv(f'{OUT}/bl_d0e_fin_auc.csv', index=False)
# SENSEX V1 composition of D0 sells
g = SO[(SO.und == 'SENSEX') & (SO.version == 'V1')]; R['sensex_v1_solo_lots'] = int(g.lots.sum()); R['sensex_v1_strangle_share'] = float(g[g.strangle].lots.sum() / g.lots.sum())
rec('d0e5', dict(auc=A.round(4).to_dict('records'), relabel=RL.reset_index().to_dict('records'), **R)); print(R)
