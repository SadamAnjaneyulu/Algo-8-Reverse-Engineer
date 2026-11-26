"""User hypothesis test, step 3: (F) is the trigger the P&L asymmetry between the two legs (other leg losing minus own leg profit)? (E) the 'slow injection' (drip) structure during favourable moves."""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy import stats
P = pd.read_csv(f'{OUT}/bl_move_panel.csv'); ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); ch = Chain(); rng = np.random.default_rng(1)
P['asym'] = P.other_ratio - P.own_ratio            # + = other leg losing / own leg winning
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
print('(F) AUC of the leg-asymmetry variable (other_ratio - own_ratio) vs single features:')
for day, Q in P.groupby('day'):
    y = Q.ep.values; cy = (Q.und + Q.expiry).values; ucy = np.unique(cy); idx = {c: np.where(cy == c)[0] for c in ucy}
    for f in ('asym', 'fav30', 'own_ratio', 'other_ratio'):
        x = Q[f].values.astype(float); a = auc(x, y)
        ii = [np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(300)]; bs = np.array([auc(x[i], y[i]) for i in ii]); print('  ', day, f, 'AUC %.3f (%.3f-%.3f)' % (a, np.quantile(bs, .025), np.quantile(bs, .975)))
Q = P[P.day == 'D-1']; base = Q.ep.mean()
t = Q.groupby(pd.cut(Q.asym, [-5, -.2, 0, .1, .2, .3, .4, .6, 5])).ep.agg(['size', 'sum']); t['rate_per_1000'] = (t['sum'] / t['size'] * 1000).round(1); t['lift'] = (t['sum'] / t['size'] / base).round(2); print('\n(F) D-1 episode-start rate by asym bin (other-leg ratio minus own-leg ratio):'); print(t.to_string()); t.to_csv(f'{OUT}/bl_move_asym_bins.csv')
rows = []
for th in (.1, .2, .3, .4, .5): m = Q.asym >= th; rows.append((f'asym >= {th}', m.mean(), Q[m].ep.sum() / Q.ep.sum(), Q[m].ep.mean() / base))
print(pd.DataFrame(rows, columns=['rule', 'share_flagged', 'recall', 'lift']).round(3).to_string(index=False))
# 2D: asym bins x fav30 sign
print('\n(F) D-1 rate per 1000 minutes: asym (rows) x favourable 30-min move (cols)'); Q2 = Q.assign(ab=pd.cut(Q.asym, [-5, 0, .2, .4, 5], labels=['<=0', '0-.2', '.2-.4', '>.4']), fb=pd.cut(Q.fav30, [-100, 0, .1, 100], labels=['<=0', '0-.1', '>.1'])); tt = Q2.groupby(['ab', 'fb']).ep.agg(['size', 'sum']); tt['rate'] = (tt['sum'] / tt['size'] * 1000).round(1); print(tt.rate.unstack().to_string()); print(tt['size'].unstack().to_string())
# (E) drip
S = ALL[~ALL.paired].copy(); sp = {}
def fav30(r):
    d = r.dayno; j = min(int((r.tod - ref.OPEN_SEC) // 60), 374); k = (r.und, r.expiry, d)
    if k not in sp: sp[k] = np.array([ch.spot(r.und, r.expiry, d, jj) for jj in range(375)])
    s = sp[k]; sgn = 1 if r.cp == 'CE' else -1
    return -sgn * (s[j - 1] / s[j - 31] - 1) * 100 if j >= 31 else np.nan
S['fav30'] = S.apply(fav30, axis=1); S['day'] = S.dayno.map({0: 'D-1', 1: 'D0'}); S = S.sort_values(['und', 'expiry', 'cp', 'dayno', 'tt_first'])
S['gap'] = S.groupby(['und', 'expiry', 'cp', 'dayno']).tt_first.diff(); S['cond'] = pd.cut(S.fav30, [-100, 0, .1, .2, 100], labels=['<=0', '0-.1', '.1-.2', '>.2'])
print('\n(E) solo sales by the favourable 30-min move at the time of the sale:'); g = S[S.day == 'D-1'].groupby('cond').agg(sales=('lots', 'size'), lots_per_sale=('lots', 'mean'), median_gap_s=('gap', 'median')).round(2); print(g.to_string()); g.to_csv(f'{OUT}/bl_move_drip_sales.csv')
print('share of D-1 solo sales with a favourable 30-min move >0: %.3f ; >0.1%%: %.3f ; >0.2%%: %.3f' % ((S[S.day == 'D-1'].fav30 > 0).mean(), (S[S.day == 'D-1'].fav30 > .1).mean(), (S[S.day == 'D-1'].fav30 > .2).mean()))
# window-level: solo lots per 15-min clock window vs favourable move inside the window
w = []
for (u, e, d), s in sp.items():
    pass
W = []
for day, d in (('D-1', 0), ('D0', 1)):
    for (u, e, cp), g in S[S.dayno == d].groupby(['und', 'expiry', 'cp']):
        s = sp.get((u, e, d)); 
        if s is None: continue
        sgn = 1 if cp == 'CE' else -1; lots = g.groupby(((g.tod - ref.OPEN_SEC) // 900).astype(int)).lots.sum()
        for b in range(0, 24):
            a, z = b * 15, min(b * 15 + 15, 374); mv = -sgn * (s[z] / s[a] - 1) * 100 if s[a] == s[a] and s[z] == s[z] else np.nan; W.append((day, u, e, cp, b, mv, lots.get(b, 0)))
W = pd.DataFrame(W, columns=['day', 'und', 'expiry', 'cp', 'win', 'fav_win', 'solo_lots']); W['fb'] = pd.cut(W.fav_win, [-100, -.2, -.1, 0, .1, .2, .35, 100])
tw = W.groupby(['day', 'fb']).agg(windows=('solo_lots', 'size'), mean_solo_lots=('solo_lots', 'mean'), share_with_solo=('solo_lots', lambda x: (x > 0).mean())).round(2); tw.to_csv(f'{OUT}/bl_move_drip_windows.csv'); print('\n(E) solo lots per 15-minute window by favourable move INSIDE the window (cycle-right windows):'); print(tw.to_string())
for day in ('D-1', 'D0'):
    x = W[(W.day == day)].dropna(subset=['fav_win']); rho = stats.spearmanr(x.fav_win, x.solo_lots); print(day, 'Spearman(favourable window move, solo lots in window) = %.3f (p=%.2g, n=%d)' % (rho.statistic, rho.pvalue, len(x)))
# heavy spells: consecutive minutes with fav30 >= 0.2%
sp_rows = []
for (u, e, d), s in sp.items():
    for cp in ('CE', 'PE'):
        sgn = 1 if cp == 'CE' else -1; f = np.array([-sgn * (s[j - 1] / s[j - 31] - 1) * 100 if j >= 31 else np.nan for j in range(375)]); heavy = f >= .2; j = 31
        g = S[(S.und == u) & (S.expiry == e) & (S.cp == cp) & (S.dayno == d)]
        while j < 375:
            if heavy[j]:
                k = j
                while k + 1 < 375 and heavy[k + 1]: k += 1
                a = ref.OPEN_SEC + j * 60; z = ref.OPEN_SEC + (k + 1) * 60; sp_rows.append((['D-1', 'D0'][d], u, e, cp, j, k - j + 1, g[(g.tod >= a) & (g.tod < z)].lots.sum(), f[j:k + 1].max())); j = k + 1
            else: j += 1
H = pd.DataFrame(sp_rows, columns=['day', 'und', 'expiry', 'cp', 'start_min', 'minutes', 'solo_lots', 'max_fav30']); H['lots_per_hour'] = H.solo_lots / H.minutes * 60; H.to_csv(f'{OUT}/bl_move_drip_spells.csv', index=False)
for day in ('D-1', 'D0'):
    h = H[H.day == day]; print('\n(E)', day, 'heavy spells (fav30 >= 0.2 %% for consecutive minutes): n=%d, median duration %.0f min, spells with zero solo lots %.2f, median solo lots per spell %.0f, mean %.2f, solo lots per hour: median %.1f mean %.2f' % (len(h), h.minutes.median(), (h.solo_lots == 0).mean(), h.solo_lots.median(), h.solo_lots.mean(), h.lots_per_hour.median(), h.lots_per_hour.mean()))
    allw = W[W.day == day]; print('   for scale: mean solo lots per 15-min window overall %.2f => per hour %.2f' % (allw.solo_lots.mean(), allw.solo_lots.mean() * 4))

x1 = W[W.day == 'D-1'].dropna(subset=['fav_win']); x0 = W[W.day == 'D0'].dropna(subset=['fav_win']); Qa = P[P.day == 'D-1']
rec('move2', dict(asym_auc=auc(Qa.asym.values.astype(float), Qa.ep.values), rho_d1=stats.spearmanr(x1.fav_win, x1.solo_lots).statistic, n_d1=len(x1), rho_d0=stats.spearmanr(x0.fav_win, x0.solo_lots).statistic, n_d0=len(x0), per_hour_d1=W[W.day == 'D-1'].solo_lots.mean() * 4, per_hour_d0=W[W.day == 'D0'].solo_lots.mean() * 4))
