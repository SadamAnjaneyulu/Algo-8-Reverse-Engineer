"""D0 'other solo' is mostly a strangle timetable (post-hoc, found in the SENSEX version before 16 Sep): a call one strike OTM and a put one strike OTM sold within 3 s at recurring clock times.
(1) detection among all D0 solo sales; (2) strikes against the ATM of the previous close; (3) the clock: out-of-fold timetable (cycle halves by parity) scored at the lot level; (4) what is left of 'other solo'.
Outputs bl_d0e_str_pairs.csv, bl_d0e_str_summary.csv, bl_d0e_str_tt.csv, bl_d0e_str_score.csv, bl_summary_d0e4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
exec(open('bl_d0e_repl.py').read().split("# ---------------- E1")[0])
CYI = CY.reset_index().rename(columns={'index': 'cid'}); R = {}
# ---- (1) near-simultaneous CE/PE solo pairs with different strikes
rows = []
for c, g in SO.groupby('cid'):
    ce = g[g.cp == 'CE']; pe = g[g.cp == 'PE']; used = set()
    for q in ce.sort_values('tod').itertuples():
        d = np.abs(pe.tod.values - q.tod); ok = [(dd, i) for i, dd in enumerate(d) if dd <= 3 and pe.index[i] not in used]
        if ok:
            dd, i = min(ok); p = pe.iloc[i]; used.add(pe.index[i]); rows.append(dict(cid=c, und=q.und, version=q.version, tod=q.tod, ce_k=q.strike, pe_k=p.strike, step=q.step, dk=(q.strike - p.strike) / q.step, ce_off=q.off_steps, pe_off=p.off_steps, ce_slice=q.slice, pe_slice=p.slice, lag=p.tod - q.tod, ce_lots=q.lots, pe_lots=p.lots, ce_idx=q.Index, pe_idx=pe.index[i]))
PR = pd.DataFrame(rows); PR.to_csv(f'{OUT}/bl_d0e_str_pairs.csv', index=False)
SM = PR.groupby(['und', 'version', 'dk']).agg(pairs=('tod', 'size'), cycles=('cid', 'nunique')).reset_index(); SM.to_csv(f'{OUT}/bl_d0e_str_summary.csv', index=False); print(SM.to_string(index=False))
STR = PR[PR.dk == 2].copy(); R['strangle_pairs'] = len(STR); R['strangle_lots'] = int(STR.ce_lots.sum() + STR.pe_lots.sum()); R['d0_sell_lots'] = 8336; R['share_of_d0_sell_lots'] = R['strangle_lots'] / 8336
R['strangle_by_group'] = STR.groupby(['und', 'version']).size().to_dict() if False else {f'{a}/{b}': int(n) for (a, b), n in STR.groupby(['und', 'version']).size().items()}; R['both_legs_one_step_otm'] = float(((STR.ce_off.round() == 1) & (STR.pe_off.round() == 1)).mean()); R['lag_s_q'] = STR.lag.quantile([.05, .5, .95]).tolist()
print(R)
# ---- (3) clock: out-of-fold timetable per group (cycle halves by parity); waves = times (+-3 s) present in >=50% of the group's training cycles
def waves(tr_cycles, grp):
    s = STR[STR.cid.isin(tr_cycles) & (STR.und == grp[0]) & (STR.version == grp[1])]
    if not len(s): return np.array([])
    t = np.sort(s.tod.values); out = []; used = np.zeros(len(t), bool)
    for a in range(len(t)):
        if used[a]: continue
        m = (np.abs(t - t[a]) <= 3) & ~used; sel = s[np.isin(s.tod.values, t[m])]; used |= m
        if sel.cid.nunique() >= max(2, 0.5 * len(set(tr_cycles) & set(PN[(PN.und == grp[0]) & (PN.version == grp[1])].cid.unique()))): out.append(float(np.median(sel.tod.values)))
    return np.array(out)
STOP = {}
for i in PN.cid.unique(): STOP[i] = 33300 + 60 * int(PN[PN.cid == i].j.max()) + 60
tp = fp = fn = 0; tt = []
for half in (0, 1):
    for grp in STR.groupby(['und', 'version']).size().index:
        trc = [c for c in PN.cid.unique() if c % 2 == half]; tec = [c for c in PN.cid.unique() if c % 2 != half]; W = waves(trc, grp); tt.append(dict(und=grp[0], version=grp[1], fold=half, waves=len(W), clock=';'.join(f'{int(w // 3600):02d}:{int(w % 3600 // 60):02d}:{int(w % 60):02d}' for w in W[:40])))
        for c in tec:
            if not ((PN.cid == c) & (PN.und == grp[0]) & (PN.version == grp[1])).any(): continue
            act = STR[(STR.cid == c)].tod.values; pw = W[W < STOP[c]]
            hit_w = sum(1 for w in pw if len(act) and np.min(np.abs(act - w)) <= 3); hit_a = sum(1 for a in act if len(pw) and np.min(np.abs(pw - a)) <= 3); tp += hit_a; fp += len(pw) - hit_w; fn += len(act) - hit_a
prec = (tp) / max(tp + fp, 1); rec_ = tp / max(tp + fn, 1); R['timetable_oof'] = dict(precision=prec, recall=rec_, f1=2 * prec * rec_ / max(prec + rec_, 1e-9), pairs_actual=int(tp + fn)); print(R['timetable_oof'])
pd.DataFrame(tt).to_csv(f'{OUT}/bl_d0e_str_tt.csv', index=False)
# ---- strike rule: CE = ATM(previous close) + 1 step, PE = ATM - 1 step
ok = []
for q in STR.itertuples():
    r = CY.iloc[q.cid]; sp = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz')[(r.und, r.expiry)]; c = sp.close.values; K = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz')[(r.und, r.expiry)]['K']; j = int((q.tod - 33300) // 60); atm = float(K[np.argmin(np.abs(K - c[max(j - 1, 0)]))])
    ok.append((q.ce_k == atm + q.step) and (q.pe_k == atm - q.step))
R['strike_rule_exact'] = float(np.mean(ok))
# ---- what is left of 'other solo'
used = set(STR.ce_idx) | set(STR.pe_idx); rest = SO[(SO.slice == 'other solo') & ~SO.index.isin(used)]; R['other_solo_lots'] = int(SO[SO.slice == 'other solo'].lots.sum()); R['other_solo_in_strangles'] = int(SO[(SO.slice == 'other solo') & SO.index.isin(used)].lots.sum()); R['other_solo_left_lots'] = int(rest.lots.sum()); R['other_solo_left_orders'] = len(rest)
R['left_by_group'] = {f'{a}/{b}': int(n) for (a, b), n in rest.groupby(['und', 'version']).lots.sum().items()}
rec('d0e4', R); pd.DataFrame([R]).drop(columns=['timetable_oof', 'strangle_by_group', 'left_by_group', 'lag_s_q']).T.to_csv(f'{OUT}/bl_d0e_str_score.csv'); print({k: v for k, v in R.items() if k != 'timetable_oof'})
