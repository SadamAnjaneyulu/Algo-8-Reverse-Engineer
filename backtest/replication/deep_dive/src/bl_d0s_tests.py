"""D0 chunk 1 tests T1-T4 (plan reports/D0_SELLS_PLAN.md). Needs bl_d0s_label.py outputs and the D0 spot/option caches.
T1 slot clock (grid pairs): per-slot share of cycles with a pair, first-pair offset spread, rule S0 out-of-fold (cid % 2), shifted-window null.
T2 D-1 reactive machine unchanged on D0 spot vs off-grid pair minutes (10:30-15:15), strike side, placebos (cycle-permuted spot, +15 min shift).
T3 solo: (a) direction after favourable move vs random-minute null; (b) D-1 solo ladder unchanged vs solo lots, placebo; (c) replacement after a same-right
buy-back <= 60 s; (d) counter-sell within +-60 s of an other-right buy-back; nulls with buy-back times shifted +-10 min; (e) burst structure.
T4 strike: pairs vs ATM of previous close; solo vs ATM and vs the D-1 premium-nearest-previous-sale rule.
Outputs bl_d0s_t1_slots.csv, bl_d0s_tests.csv, bl_d0s_bursts.csv, bl_summary_d0s1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); B = pd.read_pickle(f'{OUT}/bl_d0s_bb.pkl.gz')
SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); O = load_orders()
D0C = sorted(i for i, r in enumerate(CY.itertuples()) if ((O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)).any())
rng = np.random.default_rng(7); R = dict(cycles=len(D0C), cycles_with_sells=int(S.cid.nunique())); rows = []
def mk(i):
    r = CY.iloc[i]; o = SP[(r.und, r.expiry)]; op = OPT[(r.und, r.expiry)]
    return dict(h=o.high.values, l=o.low.values, c=o.close.values, K=op['K'], op=op, step=ref.STEP[r.und], ki={int(k): x for x, k in enumerate(op['K'])})
M = {i: mk(i) for i in D0C}
atm = lambda i, x: float(M[i]['K'][np.argmin(np.abs(M[i]['K'] - x))])
def match1(a, p, tol=1):
    """one-to-one greedy by |minute difference| <= tol; a, p arrays of minutes (lots). returns matched count"""
    a = np.sort(np.asarray(a, int)); p = np.sort(np.asarray(p, int)); cand = sorted((abs(int(x) - int(y)), ia, ip) for ia, x in enumerate(a) for ip, y in enumerate(p) if abs(int(x) - int(y)) <= tol)
    ua = set(); up = set(); n = 0
    for _, ia, ip in cand:
        if ia in ua or ip in up: continue
        ua.add(ia); up.add(ip); n += 1
    return n
def boot(per, reps=1000):
    """per: list of (tp, nf, na) per cycle -> F1 and 95% CI by cycle bootstrap"""
    a = np.array(per, float); f = lambda x: 2 * x[:, 0].sum() / max(x[:, 1].sum() + x[:, 2].sum(), 1)
    bs = [f(a[rng.integers(0, len(a), len(a))]) for _ in range(reps)]; return f(a), np.percentile(bs, 2.5), np.percentile(bs, 97.5)
def bshare(num, den, reps=1000):
    num = np.array(num, float); den = np.array(den, float); bs = []
    for _ in range(reps): k = rng.integers(0, len(num), len(num)); bs.append(num[k].sum() / max(den[k].sum(), 1))
    return num.sum() / max(den.sum(), 1), np.percentile(bs, 2.5), np.percentile(bs, 97.5)
# ---------------- T1 slot clock
SLOT = [33360 + 900 * k for k in range(24)]; P0 = S[S.pid >= 0].drop_duplicates(['cid', 'pid'])
t1 = []
for v in ('V1', 'V2'):
    cv = [i for i in D0C if CY.iloc[i].version == v]
    for k, st in enumerate(SLOT):
        offs = []
        for i in cv:
            g = P0[(P0.cid == i) & (P0.t0 >= st) & (P0.t0 < st + 180)]
            if len(g): offs.append(g.t0.min() - st)
        t1.append(dict(version=v, slot='%02d:%02d' % (st // 3600, (st // 60) % 60), cycles=len(cv), share_cycles_with_pair=len(offs) / len(cv), off_median_s=np.median(offs) if offs else np.nan, off_iqr_s=(np.percentile(offs, 75) - np.percentile(offs, 25)) if len(offs) > 1 else np.nan))
T1 = pd.DataFrame(t1); T1.to_csv(f'{OUT}/bl_d0s_t1_slots.csv', index=False)
R['t1_share_mean'] = T1.groupby('version').share_cycles_with_pair.mean().round(3).to_dict(); R['t1_off_iqr_median'] = T1.groupby('version').off_iqr_s.median().round(1).to_dict()
R['t1_off_median_median'] = T1.groupby('version').off_median_s.median().round(1).to_dict()
# window density null: lots per window-minute in grid windows vs shifted windows (all sells, and pairs only)
def dens(sh):
    mm = {(x + sh) % 60 for x in (1, 2, 3, 16, 17, 18, 31, 32, 33, 46, 47, 48)}; moh = (S.tod // 60) % 60; inw = moh.isin(mm) & (S.tod >= 33360) & (S.tod < 33360 + 900 * 24)
    return S[inw].lots.sum(), S[inw & (S.pid >= 0)].lots.sum()
for sh in (0, 5, 10): a, b = dens(sh); R[f't1_window_lots_shift{sh}'] = int(a); R[f't1_window_pairlots_shift{sh}'] = int(b)
# rule S0 out-of-fold
per = []; per_all = []; sk = [0, 0]
for i in D0C:
    v = CY.iloc[i].version; tr = [c for c in D0C if c % 2 != i % 2 and CY.iloc[c].version == v]; c = M[i]['c']
    for cp in ('CE', 'PE'):
        pj = []; pk = []
        for st in SLOT:
            offs = [g.t0.min() - st for c2 in tr for g in [P0[(P0.cid == c2) & (P0.t0 >= st) & (P0.t0 < st + 180)]] if len(g)]
            off = np.median(offs) if offs else 0.0; j = int((st + off - 33300) // 60); pj.append(j); pk.append(atm(i, c[max(j - 1, 0)]))
        g = S[(S.cid == i) & (S.cp == cp) & (S.lab == 'grid_pair')]; aj = np.repeat(g.j.values, g.lots.values); tp = match1(aj, pj); per.append((tp, len(pj), len(aj)))
        ga = S[(S.cid == i) & (S.cp == cp) & (S.pid >= 0)]; per_all.append((match1(np.repeat(ga.j.values, ga.lots.values), pj), len(pj), int(ga.lots.sum())))
        # strike agreement (same minute +-1, nearest)
        for jj, kk in zip(pj, pk):
            h = g[(g.j - jj).abs() <= 1]
            if len(h): sk[0] += 1; sk[1] += int(h.strike.iloc[0] == kk)
f, lo, hi = boot(per); rows.append(dict(test='T1 rule S0 (1 CE + 1 PE per slot, OOF offset) vs grid-pair lots', value=f, ci_lo=lo, ci_hi=hi, null=np.nan, n=sum(x[2] for x in per)))
a = np.array(per); R['t1_S0_precision'] = a[:, 0].sum() / a[:, 1].sum(); R['t1_S0_recall'] = a[:, 0].sum() / a[:, 2].sum()
f2, lo2, hi2 = boot(per_all); rows.append(dict(test='T1 rule S0 vs all pair lots', value=f2, ci_lo=lo2, ci_hi=hi2, null=np.nan, n=sum(x[2] for x in per_all))); R['t1_S0_strike_exact'] = sk[1] / max(sk[0], 1)
# lots per pair per slot (quantity)
gp = S[S.lab == 'grid_pair']; q = gp.assign(slot=((gp.t0 - 33360) // 900).astype(int)).groupby(['cid', 'slot', 'cp']).lots.sum(); R['t1_lots_per_slot_right_quantiles'] = q.quantile([.25, .5, .75, .9]).tolist(); R['t1_slots_with_more_than_1'] = float((q > 1).mean())
# ---------------- T2 reactive machine
def fires(d):
    h, l = d['h'], d['l']; out = []; done = set()
    for j in range(75, 361):
        clock = 33300 + 60 * j; b0 = (clock // 1800) * 1800; a = int(np.ceil((b0 - 3600 - 33300) / 60)); e = int(np.ceil((b0 - 33300) / 60))
        if e - max(a, 0) < 2: continue
        H, L = h[max(a, 0):e].max(), l[max(a, 0):e].min()
        for s, fl in ((1, h[j] > H), (-1, l[j] < L)):
            if fl and (b0, s) not in done: out.append((j, s)); done.add((b0, s))
    return out
OG = S[(S.lab == 'offgrid_pair')].drop_duplicates(['cid', 'pid'])
def t2(shift=0, perm=False):
    per = []
    for n, i in enumerate(D0C):
        src = D0C[(n + 1) % len(D0C)] if perm else i; F = [j + shift for j, _ in fires(M[src])]
        A = np.unique(OG[(OG.cid == i) & (OG.j >= 75) & (OG.j <= 360)].j.values); per.append((match1(A, F), len(F), len(A)))
    return per
for nm, kw in (('T2 D-1 breakout machine on D0 vs off-grid pair minutes 10:30-15:15', {}), ('T2 placebo: cycle-permuted spot', dict(perm=True)), ('T2 placebo: fires +15 min', dict(shift=15))):
    f, lo, hi = boot(t2(**kw)); rows.append(dict(test=nm, value=f, ci_lo=lo, ci_hi=hi, null=np.nan, n=int(sum(x[2] for x in t2(**kw)))))
pr = t2(); a = np.array(pr); R['t2_precision'] = a[:, 0].sum() / a[:, 1].sum(); R['t2_recall'] = a[:, 0].sum() / a[:, 2].sum(); R['t2_fires'] = int(a[:, 1].sum()); R['t2_targets'] = int(a[:, 2].sum())
R['t2_offgrid_pair_minutes_by_hour'] = OG.assign(h=(OG.t0 // 3600).astype(int)).groupby('h').size().to_dict()
# strike side for matched fires
ss = [0, 0, 0]
for i in D0C:
    c = M[i]['c']; st = M[i]['step']; g = OG[OG.cid == i]
    for j, s in fires(M[i]):
        h = g[(g.j - j).abs() <= 1]
        if not len(h): continue
        off = (h.strike.iloc[0] - atm(i, c[max(j - 1, 0)])) / st; ss[0] += 1; ss[1] += int(round(off) == s); ss[2] += int(np.sign(off) == s)
R['t2_strike_exact_atm_pm1_side'] = ss[1] / max(ss[0], 1); R['t2_strike_sign_side'] = ss[2] / max(ss[0], 1); R['t2_matched_for_strike'] = ss[0]
# ---------------- T3 solo
SO = S[S.lab == 'solo'].copy()
def fav(i, j, cp, n):
    c = M[i]['c']
    if j - 1 - n < 0: return np.nan
    mv = c[j - 1] - c[j - 1 - n]; return float(mv < 0) if cp == 'CE' else float(mv > 0)
for n in (5, 15):
    num = []; den = []; nul = []
    for i in D0C:
        g = SO[SO.cid == i]; x = [fav(i, j, cp, n) * k for j, cp, k in zip(g.j, g.cp, g.lots)]; num.append(np.nansum(x)); den.append(g.lots.sum())
        for j, cp, k in zip(g.j, g.cp, g.lots):
            lo_, hi_ = max(n + 1, (j // 60) * 60 - 0), min(374, (j // 60) * 60 + 59); jr = rng.integers(lo_, max(hi_, lo_ + 1), 50); nul.append(np.nanmean([fav(i, int(q), cp, n) for q in jr]) * k)
    v, lo, hi = bshare(num, den); rows.append(dict(test=f'T3a solo lots after a favourable {n}-min spot move', value=v, ci_lo=lo, ci_hi=hi, null=np.sum(nul) / max(sum(den), 1), n=int(sum(den))))
def ladder(d, resets):
    h, l, c, st = d['h'], d['l'], d['c'], 0.2 * d['step']; out = {'CE': [], 'PE': []}
    for cp in ('CE', 'PE'):
        evs = sorted(set(resets[cp])); ptr = 0; refp = None
        for j in range(1, 375):
            while ptr < len(evs) and evs[ptr] < j: refp = c[max(evs[ptr] - 1, 0)]; ptr += 1
            if refp is None: continue
            if not ((l[j] < l[max(j - 60, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - 60, 0):j].max())): continue
            if cp == 'CE' and l[j] < refp - st: out[cp].append(j); refp = refp - st * max(1, int((refp - l[j]) // st))
            elif cp == 'PE' and h[j] > refp + st: out[cp].append(j); refp = refp + st * max(1, int((h[j] - refp) // st))
    return out
def t3b(perm=False):
    per = []
    for n, i in enumerate(D0C):
        src = D0C[(n + 1) % len(D0C)] if perm else i; pj = S[(S.cid == i) & (S.pid >= 0)]; L = ladder(M[src], {cp: pj[pj.cp == cp].j.tolist() for cp in ('CE', 'PE')})
        for cp in ('CE', 'PE'): g = SO[(SO.cid == i) & (SO.cp == cp)]; a = np.repeat(g.j.values, g.lots.values); per.append((match1(a, L[cp]), len(L[cp]), len(a)))
    return per
for nm, kw in (('T3b D-1 solo ladder on D0 vs solo lots', {}), ('T3b placebo: cycle-permuted spot', dict(perm=True))):
    pp = t3b(**kw); f, lo, hi = boot(pp); a = np.array(pp); rows.append(dict(test=nm, value=f, ci_lo=lo, ci_hi=hi, null=np.nan, n=int(a[:, 2].sum()))); R[nm + ' precision/recall'] = [a[:, 0].sum() / max(a[:, 1].sum(), 1), a[:, 0].sum() / max(a[:, 2].sum(), 1)]
def near_bb(i, cp_rule, lo_s, hi_s, shift=0):
    g = SO[SO.cid == i]; b = B[B.cid == i]; out = []
    for t, cp, k in zip(g.tod, g.cp, g.lots):
        cpb = cp if cp_rule == 'same' else ('PE' if cp == 'CE' else 'CE'); tb = b[b.cp == cpb].tod.values + shift
        out.append(k * float(((tb >= t + lo_s) & (tb < t + hi_s)).any() if cp_rule != 'same' else ((tb > t + lo_s) & (tb <= t + hi_s)).any()))
    return sum(out), g.lots.sum()
for nm, rule, lo_s, hi_s in (('T3c replacement: same-right buy-back within 60 s before the sale', 'same', -60, 0), ('T3d counter-sell: other-right buy-back within 60 s before or after', 'other', -60, 60)):
    num = []; den = []; nl = []
    for i in D0C:
        a, b = near_bb(i, rule, lo_s, hi_s); num.append(a); den.append(b); nl.append((near_bb(i, rule, lo_s, hi_s, 600)[0] + near_bb(i, rule, lo_s, hi_s, -600)[0]) / 2)
    v, lo, hi = bshare(num, den); rows.append(dict(test=nm, value=v, ci_lo=lo, ci_hi=hi, null=sum(nl) / max(sum(den), 1), n=int(sum(den))))
# same lots after a buy-back
sl = [0, 0]
for i in D0C:
    b = B[B.cid == i]; g = SO[SO.cid == i]
    for t, cp, k in zip(b.tod, b.cp, b.lots):
        h = g[(g.cp == cp) & (g.tod > t) & (g.tod <= t + 60)]
        if len(h): sl[0] += 1; sl[1] += int(h.lots.iloc[0] == k)
R['t3c_bb_followed_by_same_right_solo'] = sl[0] / max(len(B[B.cid.isin(D0C)]), 1); R['t3c_same_lots'] = sl[1] / max(sl[0], 1)
# both conditions overlap
ov = [0, 0, 0, 0]
for i in D0C:
    g = SO[SO.cid == i]; b = B[B.cid == i]
    for t, cp, k in zip(g.tod, g.cp, g.lots):
        o_ = 'PE' if cp == 'CE' else 'CE'; s1 = ((b[b.cp == cp].tod > t - 60) & (b[b.cp == cp].tod <= t)).any(); s2 = ((b[b.cp == o_].tod >= t - 60) & (b[b.cp == o_].tod < t + 60)).any()
        ov[0] += k * (s1 and not s2); ov[1] += k * (s2 and not s1); ov[2] += k * (s1 and s2); ov[3] += k * (not s1 and not s2)
R['t3_solo_lots_repl_only_counter_only_both_neither'] = ov
# bursts
bu = []
for i in D0C:
    for cp in ('CE', 'PE'):
        g = SO[(SO.cid == i) & (SO.cp == cp)].sort_values('tod')
        if not len(g): continue
        gid = (g.tod.diff().fillna(1e9) > 30).cumsum()
        for _, x in g.groupby(gid):
            c = M[i]['c']; bu.append(dict(cid=i, cp=cp, t0=x.tod.min(), dur=x.tod.max() - x.tod.min(), orders=len(x), lots=int(x.lots.sum()), strikes=x.strike.nunique(), spot_move_steps=(c[x.j.max()] - c[max(x.j.min() - 1, 0)]) / M[i]['step']))
BU = pd.DataFrame(bu); BU.to_csv(f'{OUT}/bl_d0s_bursts.csv', index=False)
R['t3e_bursts'] = len(BU); R['t3e_lots_per_burst_q'] = BU.lots.quantile([.5, .75, .9, .99]).tolist(); R['t3e_share_lots_in_bursts_ge5'] = float(BU[BU.lots >= 5].lots.sum() / BU.lots.sum()); R['t3e_strikes_per_burst_q'] = BU.strikes.quantile([.5, .9]).tolist()
R['t3e_spot_move_favourable_bursts_ge5'] = float(np.mean([(m < 0) if cp == 'CE' else (m > 0) for m, cp in zip(BU[BU.lots >= 5].spot_move_steps, BU[BU.lots >= 5].cp)]))
# ---------------- T4 strike
def st_share(g):
    ex = []; p1 = []
    for i, j, k in zip(g.cid, g.j, g.strike): a = atm(i, M[i]['c'][max(j - 1, 0)]); ex.append(k == a); p1.append(abs(k - a) <= M[i]['step'] + 1e-6)
    return float(np.mean(ex)), float(np.mean(p1))
PR = S[S.pid >= 0]; R['t4_pair_atm_exact'], R['t4_pair_atm_pm1'] = st_share(PR[PR.cid.isin(D0C)]); R['t4_solo_atm_exact'], R['t4_solo_atm_pm1'] = st_share(SO[SO.cid.isin(D0C)])
hit = []
for i in D0C:
    g = S[S.cid == i].sort_values('tod'); last = {}
    for q in g.itertuples():
        if q.lab == 'solo' and q.cp in last:
            op = M[i]['op'][(q.cp, 'close')][:, max(q.j - 1, 0)]; ok = ~np.isnan(op)
            if ok.any(): K = M[i]['K'][ok]; hit.append(float(K[np.argmin(np.abs(op[ok] - last[q.cp]))] == q.strike))
        last[q.cp] = q.px
R['t4_solo_premium_nearest_prev_sale'] = float(np.mean(hit)); R['t4_solo_n'] = len(hit)
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/bl_d0s_tests.csv', index=False); print(T.round(3).to_string(index=False)); print(T1.groupby('version')[['share_cycles_with_pair', 'off_median_s', 'off_iqr_s']].describe().round(2).T.to_string())
rec('d0s1', R); print({k: (np.round(v, 3) if isinstance(v, float) else v) for k, v in R.items()})
