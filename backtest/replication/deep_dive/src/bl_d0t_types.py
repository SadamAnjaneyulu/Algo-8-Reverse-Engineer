"""D0 step 1 (plan reports/D0_SELL_TYPES_PLAN.md): every D0 body sell order gets one type by a fixed precedence; chance levels; multi-label overlap; strike analysis per type; opening window vs the carried book.
Pairs: scheduled (OOF wave +-3 s) > opening (< 09:18) > re-centre (body buy-back, any right, 60 s before) > breakout (D-1 machine fire +-1 min) > other.
Solo: opening (< 09:18) > replacement (same-right buy-back 60 s before) > counter-sell (other-right buy-back +-60 s) > extreme (fresh 60-min favourable extreme in the minute) > late (>= 15:00) > other.
Outputs bl_d0t_orders.pkl.gz, bl_d0t_types.csv, bl_d0t_chance.csv, bl_d0t_overlap.csv, bl_d0t_strikes.csv, bl_d0t_hours.csv, bl_d0t_opening.csv, bl_summary_d0t1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
from scipy.stats import spearmanr, binomtest
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); B = pd.read_pickle(f'{OUT}/bl_d0s_bb.pkl.gz'); WF = pd.read_pickle(f'{OUT}/bl_d0s_waves_fold.pkl.gz')
SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); BK = pd.read_pickle(f'{OUT}/bl_d0b_book.pkl.gz'); OH1 = bl_ohlc.load(); rng = np.random.default_rng(23)
D0C = sorted(BK); S = S[S.cid.isin(D0C)].sort_values(['cid', 'tod']).reset_index(drop=True); R = {}
def fires(h, l):
    out = []; done = set()
    for j in range(75, 361):
        clock = 33300 + 60 * j; b0 = (clock // 1800) * 1800; a = int(np.ceil((b0 - 3600 - 33300) / 60)); e = int(np.ceil((b0 - 33300) / 60))
        if e - max(a, 0) < 2: continue
        H, L = h[max(a, 0):e].max(), l[max(a, 0):e].min()
        for s, fl in ((1, h[j] > H), (-1, l[j] < L)):
            if fl and (b0, s) not in done: out.append((j, s)); done.add((b0, s))
    return out
MK = {}
for i in D0C:
    r = CY.iloc[i]; sp = SPT[(r.und, r.expiry)]; op = OPT[(r.und, r.expiry)]; MK[i] = dict(h=sp.high.values, l=sp.low.values, c=sp.close.values, o0=sp.open.values[0], K=op['K'], op=op, ki={int(k): x for x, k in enumerate(op['K'])}, step=ref.STEP[r.und],
                                                                     fires=fires(sp.high.values, sp.low.values), w=WF[i % 2][(WF[i % 2].und == r.und) & (WF[i % 2].version == r.version)].t.values, d1close=OH1[(r.und, r.expiry)].close.values[-1])
def fresh(i, j, cp):
    m = MK[i]
    if j < 1: return False
    return bool(m['l'][j] < m['l'][max(j - 60, 0):j].min()) if cp == 'CE' else bool(m['h'][j] > m['h'][max(j - 60, 0):j].max())
def flags(df, shift=0, rnd=False):
    """multi-label flags per order; shift moves buy-back times (chance level); rnd replaces the sale minute by a random minute in the same hour for the extreme flag"""
    out = []
    for q in df.itertuples():
        i = q.cid; m = MK[i]; t = q.tod; b = B[B.cid == i]; bt = b.tod.values + shift; bc = b.cp.values; o = 'PE' if q.cp == 'CE' else 'CE'
        t0 = q.t0 if q.pid >= 0 else t; jj = q.j if not rnd else int(rng.integers(max((q.j // 60) * 60, 1), min((q.j // 60) * 60 + 60, 375)))
        out.append(dict(wave=bool(q.pid >= 0 and len(m['w']) and np.min(np.abs(m['w'] - t0)) <= 3), opening=bool(t0 < 33480), recentre=bool(q.pid >= 0 and ((bt >= t0 - 60) & (bt < t0)).any()),
                        breakout=bool(q.pid >= 0 and any(abs(f - q.j) <= 1 for f, _ in m['fires'])), replacement=bool(q.pid < 0 and ((bt >= t - 60) & (bt < t) & (bc == q.cp)).any()),
                        counter=bool(q.pid < 0 and ((bt >= t - 60) & (bt <= t + 60) & (bc == o)).any()), extreme=bool(q.pid < 0 and fresh(i, jj, q.cp)), late=bool(t >= 54000)))
    return pd.DataFrame(out, index=df.index)
F = flags(S)
def typ(q, f):
    if q.pid >= 0:
        for k, nm in (('wave', 'scheduled pair'), ('opening', 'opening pair'), ('recentre', 're-centre pair'), ('breakout', 'breakout pair')):
            if f[k]: return nm
        return 'other pair'
    for k, nm in (('opening', 'opening solo'), ('replacement', 'replacement solo'), ('counter', 'counter-sell solo'), ('extreme', 'extreme solo'), ('late', 'late solo')):
        if f[k]: return nm
    return 'other solo'
S['type'] = [typ(q, F.loc[ix]) for ix, q in zip(S.index, S.itertuples())]
# pair consistency: a pair takes the type of its first order
pt = S[S.pid >= 0].sort_values('tod').groupby(['cid', 'pid']).type.first(); S.loc[S.pid >= 0, 'type'] = [pt[(c_, p_)] for c_, p_ in zip(S[S.pid >= 0].cid, S[S.pid >= 0].pid)]
ORDER = ['scheduled pair', 'opening pair', 're-centre pair', 'breakout pair', 'other pair', 'opening solo', 'replacement solo', 'counter-sell solo', 'extreme solo', 'late solo', 'other solo']
def bshare(mask):
    per = S.groupby('cid').apply(lambda g: pd.Series(dict(a=g.lots[mask.loc[g.index]].sum(), b=g.lots.sum()))); bs = []
    for _ in range(1000): k = rng.choice(per.index, len(per)); bs.append(per.loc[k, 'a'].sum() / per.loc[k, 'b'].sum())
    return per.a.sum() / per.b.sum(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)
TY = []
for t in ORDER:
    g = S[S.type == t]; sh, lo, hi = bshare(S.type == t)
    TY.append(dict(type=t, lots=int(g.lots.sum()), orders=len(g), cycles=int(g.cid.nunique()), share_lots=sh, ci_lo=lo, ci_hi=hi, lots_per_order=g.lots.mean() if len(g) else np.nan, CE_share=float((g.lots * (g.cp == 'CE')).sum() / max(g.lots.sum(), 1)),
                   median_time=(lambda x: f'{int(x // 3600):02d}:{int(x % 3600 // 60):02d}')(np.median(g.tod)) if len(g) else '-'))
TYd = pd.DataFrame(TY); TYd.to_csv(f'{OUT}/bl_d0t_types.csv', index=False); print(TYd.round(3).to_string(index=False))
# chance levels along the precedence chain (among orders reaching that rule)
F0 = flags(S, 600); F1_ = flags(S, -600); FR = flags(S, rnd=True); ch = []; rem = S.copy()
for kind, rules in (('pair', [('wave', None), ('opening', None), ('recentre', 'shift'), ('breakout', None)]), ('solo', [('opening', None), ('replacement', 'shift'), ('counter', 'shift'), ('extreme', 'random'), ('late', None)])):
    left = S[(S.pid >= 0) if kind == 'pair' else (S.pid < 0)].index
    for k, how in rules:
        real = S.lots[left][F.loc[left, k]].sum() / max(S.lots[left].sum(), 1)
        if how == 'shift': null = (S.lots[left][F0.loc[left, k]].sum() + S.lots[left][F1_.loc[left, k]].sum()) / 2 / max(S.lots[left].sum(), 1)
        elif how == 'random': null = S.lots[left][FR.loc[left, k]].sum() / max(S.lots[left].sum(), 1)
        else: null = np.nan
        ch.append(dict(group=kind, rule=k, lots_reaching_rule=int(S.lots[left].sum()), share_flagged=real, chance_share=null, excess_lots=int(round((real - (null if null == null else 0)) * S.lots[left].sum())) if null == null else np.nan))
        left = left[~F.loc[left, k].values]
CH = pd.DataFrame(ch); CH.to_csv(f'{OUT}/bl_d0t_chance.csv', index=False); print(CH.round(3).to_string(index=False))
# multi-label overlap (solo lots)
so = S.pid < 0; ks = ['opening', 'replacement', 'counter', 'extreme', 'late']; ov = pd.DataFrame([[int(S.lots[so & F[a] & F[b]].sum()) for b in ks] for a in ks], index=ks, columns=ks); ov.to_csv(f'{OUT}/bl_d0t_overlap.csv'); R['solo_lots_no_flag'] = int(S.lots[so & ~F[ks].any(axis=1)].sum())
# ---------------- strikes
book = {}; rows = []; last = {}
for i in D0C:
    bk = {}
    for L in BK[i]['at_open']: bk[(L['cp'], int(L['strike']))] = bk.get((L['cp'], int(L['strike'])), 0) + 1
    carried = {k for k, v in bk.items() if v > 0}; ev = [(q.tod, 0, q) for q in S[S.cid == i].itertuples()] + [(q.tod, 1, q) for q in B[B.cid == i].itertuples()]; ev.sort(key=lambda x: (x[0], x[1]))
    m = MK[i]; lastsale = {}; lastbb = {'CE': [], 'PE': []}
    for t, kind, q in ev:
        k = (q.cp, int(q.strike))
        if kind == 1: bk[k] = bk.get(k, 0) - q.lots; lastbb[q.cp].append((t, int(q.strike))); continue
        j = q.j; c0 = m['c'][j - 1] if j > 0 else m['o0']; K = m['K']; atm = float(K[np.argmin(np.abs(K - c0))]); off = (q.strike - atm) / m['step'] * (1 if q.cp == 'CE' else -1)
        st = 'carried strike' if (bk.get(k, 0) > 0 and k in carried) else ('D0 strike' if bk.get(k, 0) > 0 else 'new strike')
        pr = m['op'][(q.cp, 'close')][:, max(j - 1, 0)]; ok = np.isfinite(pr); prem_rule = np.nan
        if q.cp in lastsale and ok.any(): prem_rule = float(K[ok][np.argmin(np.abs(pr[ok] - lastsale[q.cp][1]))] == q.strike)
        atm_px = m['op'][(q.cp, 'close')][m['ki'][int(atm)], max(j - 1, 0)] if int(atm) in m['ki'] else np.nan
        o = 'PE' if q.cp == 'CE' else 'CE'; rb = [s_ for tt, s_ in lastbb[q.cp] if t - 60 <= tt < t]; cb = [s_ for tt, s_ in lastbb[o] if t - 60 <= tt <= t + 60]
        cb_after = [s_ for tt, s_ in [(x.tod, int(x.strike)) for x in B[(B.cid == i) & (B.cp == o) & (B.tod > t) & (B.tod <= t + 60)].itertuples()]]
        rows.append(dict(cid=i, tod=t, j=j, cp=q.cp, strike=q.strike, lots=q.lots, type=S.loc[q.Index, 'type'], off_steps=off, exact_atm=off == 0, pm1=abs(off) <= 1, status=st, same_as_last=float(q.cp in lastsale and lastsale[q.cp][0] == q.strike) if q.cp in lastsale else np.nan,
                         prem_rule=prem_rule, repl_same_strike=float(q.strike in rb) if rb else np.nan, counter_same_strike=float(q.strike in (cb + cb_after)) if (cb or cb_after) else np.nan, px=q.px, px_over_atm=q.px / atm_px if atm_px == atm_px and atm_px > 0 else np.nan))
        lastsale[q.cp] = (q.strike, q.px); bk[k] = bk.get(k, 0) + q.lots
ST = pd.DataFrame(rows); pd.to_pickle(ST, f'{OUT}/bl_d0t_orders.pkl.gz'); sr = []
w = lambda g, col: float((g[col] * g.lots).sum() / g.lots[g[col].notna()].sum()) if g[col].notna().any() else np.nan
for t in ORDER + ['ALL']:
    g = ST if t == 'ALL' else ST[ST.type == t]
    if not len(g): continue
    off = np.repeat(g.off_steps.values, g.lots.values)
    sr.append(dict(type=t, lots=int(g.lots.sum()), exact_atm=w(g.assign(x=g.exact_atm.astype(float)), 'x'), within1=w(g.assign(x=g.pm1.astype(float)), 'x'), off_median=float(np.median(off)), off_q10=float(np.percentile(off, 10)), off_q90=float(np.percentile(off, 90)),
                   carried_strike=float(g.lots[g.status == 'carried strike'].sum() / g.lots.sum()), D0_strike=float(g.lots[g.status == 'D0 strike'].sum() / g.lots.sum()), new_strike=float(g.lots[g.status == 'new strike'].sum() / g.lots.sum()),
                   same_as_last_sale=w(g, 'same_as_last'), d1_premium_rule=w(g, 'prem_rule'), repl_same_strike_as_bb=w(g, 'repl_same_strike'), counter_same_strike_as_other_bb=w(g, 'counter_same_strike'), px_median=float(np.median(np.repeat(g.px.values, g.lots.values))),
                   px_over_atm_median=float(np.nanmedian(np.repeat(g.px_over_atm.values, g.lots.values)))))
SR = pd.DataFrame(sr); SR.to_csv(f'{OUT}/bl_d0t_strikes.csv', index=False); print(SR.round(3).to_string(index=False))
# hours
ST['half_hour'] = [f'{int(x // 3600):02d}:{"00" if (x % 3600) < 1800 else "30"}' for x in ST.tod]; HH = ST.pivot_table(index='half_hour', columns='type', values='lots', aggfunc='sum').fillna(0).astype(int).reindex(columns=[t for t in ORDER if t in set(ST.type)]); HH.to_csv(f'{OUT}/bl_d0t_hours.csv')
# ---------------- opening window 09:15-09:30 vs the carried book
op_ = []
for i in D0C:
    g = ST[(ST.cid == i) & (ST.tod < 34200)]; m = MK[i]; bk = {}
    for L in BK[i]['at_open']: bk[L['cp']] = bk.get(L['cp'], 0) + 1
    gap = (m['o0'] - m['d1close']) / m['step']; ce = float((g.lots * (g.cp == 'CE')).sum() / g.lots.sum()) if len(g) else np.nan
    op_.append(dict(cid=i, gap_steps=gap, open_sell_lots=int(g.lots.sum()), CE_share=ce, carried_S_CE=bk.get('CE', 0), carried_S_PE=bk.get('PE', 0), heavier='CE' if bk.get('CE', 0) > bk.get('PE', 0) else ('PE' if bk.get('PE', 0) > bk.get('CE', 0) else 'equal'),
                    share_on_heavier=float((g.lots * (g.cp == ('CE' if bk.get('CE', 0) > bk.get('PE', 0) else 'PE'))).sum() / g.lots.sum()) if len(g) and bk.get('CE', 0) != bk.get('PE', 0) else np.nan,
                    carried_strike_share=float(g.lots[g.status == 'carried strike'].sum() / g.lots.sum()) if len(g) else np.nan, new_strike_share=float(g.lots[g.status == 'new strike'].sum() / g.lots.sum()) if len(g) else np.nan,
                    types='; '.join(f'{k} {v}' for k, v in g.groupby('type').lots.sum().items())))
OP = pd.DataFrame(op_); OP.to_csv(f'{OUT}/bl_d0t_opening.csv', index=False); oo = OP.dropna(subset=['CE_share'])
rho, p_ = spearmanr(oo.gap_steps, oo.CE_share); fav = ((oo.CE_share - 0.5) * np.sign(oo.gap_steps)); k_ = int((fav > 0).sum()); n_ = int((fav != 0).sum())
R.update(open_cycles_with_sells=int(len(oo)), open_lots=int(oo.open_sell_lots.sum()), open_by_type=ST[ST.tod < 34200].groupby('type').lots.sum().astype(int).to_dict(), open_status=ST[ST.tod < 34200].groupby('status').lots.sum().astype(int).to_dict(),
         gap_vs_CE_share_spearman=[float(rho), float(p_)], gap_up_sells_more_CE=[k_, n_, float(binomtest(k_, n_).pvalue) if n_ else np.nan], heavier_side_share_median=float(oo.share_on_heavier.median()),
         heavier_side_sign=[int((oo.share_on_heavier > 0.5).sum()), int((oo.share_on_heavier.notna() & (oo.share_on_heavier != 0.5)).sum())])
R['types'] = TYd.round(4).to_dict('records'); rec('d0t1', R); print({k: v for k, v in R.items() if k != 'types'}); print(OP.round(2).to_string(index=False))
# ---------------- post-hoc refinement (plan addendum): far-OTM solo (>= 3 steps OTM) as its own type after opening solo; roll-out test
ST['type2'] = np.where((ST.type != 'opening solo') & (~ST.type.str.endswith('pair')) & (ST.off_steps >= 3), 'far-OTM solo', ST.type)
# replacement / counter / extreme chance after removing far-OTM lots from the solo chain
Fx = F.loc[S.index]; key = pd.Series(ST.index, index=list(zip(ST.cid, ST.tod, ST.cp, ST.strike)))
farmask = pd.Series(False, index=S.index)
for ix, q in zip(S.index, S.itertuples()):
    k = (q.cid, q.tod, q.cp, q.strike)
    if k in key.index: farmask[ix] = bool((ST.loc[key[k] if np.isscalar(key[k]) else key[k].iloc[0], 'type2']) == 'far-OTM solo')
ch2 = []; left = S[(S.pid < 0) & ~farmask & ~F.opening].index
for k, how in (('replacement', 'shift'), ('counter', 'shift'), ('extreme', 'random')):
    real = S.lots[left][F.loc[left, k]].sum() / max(S.lots[left].sum(), 1)
    null = (S.lots[left][F0.loc[left, k]].sum() + S.lots[left][F1_.loc[left, k]].sum()) / 2 / max(S.lots[left].sum(), 1) if how == 'shift' else S.lots[left][FR.loc[left, k]].sum() / max(S.lots[left].sum(), 1)
    ch2.append(dict(rule=k, lots_reaching_rule=int(S.lots[left].sum()), share_flagged=real, chance_share=null, excess_lots=int(round((real - null) * S.lots[left].sum())))); left = left[~F.loc[left, k].values]
pd.DataFrame(ch2).to_csv(f'{OUT}/bl_d0t_chance2.csv', index=False)
T2 = ST.groupby('type2').agg(lots=('lots', 'sum'), orders=('lots', 'size'), cycles=('cid', 'nunique')).reset_index(); T2['share_lots'] = T2.lots / T2.lots.sum(); T2.to_csv(f'{OUT}/bl_d0t_types2.csv', index=False)
fo = ST[ST.type2 == 'far-OTM solo']; ro = []
for sh in (0, 600, -600):
    hit = 0; ratio = []
    for q in fo.itertuples():
        b = B[(B.cid == q.cid) & (B.cp == q.cp) & (B.tod + sh >= q.tod - 60) & (B.tod + sh < q.tod)]
        if len(b):
            m = MK[q.cid]; c0 = m['c'][max(q.j - 1, 0)]; bo = ((b.strike - c0) / m['step'] * (1 if q.cp == 'CE' else -1)).values; near = b[bo < q.off_steps - 0.5]
            if len(near): hit += q.lots; ratio.append(q.px / near.px.iloc[-1])
    ro.append(dict(shift=sh, share=hit / fo.lots.sum(), ratio_median=float(np.median(ratio)) if ratio else np.nan))
R['far_otm'] = dict(lots=int(fo.lots.sum()), cycles=int(fo.cid.nunique()), by_cycle={int(k): int(v) for k, v in fo.groupby('cid').lots.sum().sort_values(ascending=False).items()}, und=fo.merge(CY.reset_index().rename(columns={'index': 'cid'})[['cid', 'und', 'version']], on='cid').groupby(['und', 'version']).lots.sum().to_dict(),
                    time_q=fo.tod.quantile([.1, .5, .9]).tolist(), px_q=fo.px.quantile([.1, .5, .9]).tolist(), off_q=fo.off_steps.quantile([.1, .5, .9]).tolist(), rollout=ro)
R['far_otm']['und'] = {f'{a}_{b}': int(v) for (a, b), v in R['far_otm']['und'].items()}; R['chance2'] = ch2; R['types2'] = T2.round(4).to_dict('records'); rec('d0t1', R); print(T2.round(3).to_string(index=False)); print(pd.DataFrame(ch2).round(3).to_string(index=False)); print(R['far_otm'])
