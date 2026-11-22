"""D0 chunk 2 tests B1, B3, B4 (plan reports/D0_BUYBACKS_PLAN.md). Population: D0 body buy-back lots before 15:10 and before the cycle's stop.
B1 hazard panel (every open body short lot x D0 minute, label = removed in the minute) by ratio bin (minute high / entry; previous close / entry), origin, hour block.
B3 clocking: second :00 and block minutes 14 / 0 (15-min blocks from 09:15) by group. B4 context of in-profit buy-backs (partner, re-centre pair, same-right roll) vs +-10 min shifted nulls.
Outputs bl_d0b_panel.pkl.gz, bl_d0b_hazard.csv, bl_d0b_hazard_hour.csv, bl_d0b_b3.csv, bl_d0b_b4.csv, bl_summary_d0b1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); BK = pd.read_pickle(f'{OUT}/bl_d0b_book.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0b_removed.pkl.gz'); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz')
D0C = sorted(BK); STOP = {}
for i in D0C:
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.module == 's_')]; STOP[i] = float(z.tod.min()) if len(z) else 1e9
JEND = {i: int(min(354, (STOP[i] - 33300) // 60 - 1)) for i in D0C}                 # last minute in scope: 15:09 or the minute before the stop
grp = lambda r: np.where(r > 1, 'loss', np.where(r >= 0.25, 'mid-profit', 'deep-profit'))
X['grp'] = grp(X.ratio.values); X['inscope'] = [(t < 54600) and (t < STOP[i]) for i, t in zip(X.cid, X.tod)]; XS = X[X.inscope].copy(); R = dict(lots_in_scope=int(len(XS)), by_group=XS.grp.value_counts().to_dict())
# ---------------- B1 panel
rows = []
for i in D0C:
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}; je = JEND[i]
    for L in BK[i]['lots']:
        if L['entry_day'] == 0 and L.get('exit_day', 1) == 0 and L['exit_tod'] == L['exit_tod']: continue          # closed on D-1
        if L['strike'] not in ki: continue
        j0 = 0 if L['entry_day'] == 0 else int((L['entry_tod'] - 33300) // 60) + 1; jx = int((L['exit_tod'] - 33300) // 60) if (L['exit_tod'] == L['exit_tod'] and L.get('exit_day', 1) == 1) else 10 ** 6
        j1 = min(je, jx)
        if j1 < max(j0, 1): continue
        js = np.arange(max(j0, 1), j1 + 1); x = ki[L['strike']]; e = L['entry']
        rows.append(pd.DataFrame(dict(cid=i, lid=L['lid'], j=js, cp=L['cp'], strike=L['strike'], origin='D-1' if L['entry_day'] == 0 else 'D0', typ=L['typ'], entry=e, rh=op[(L['cp'], 'high')][x, js] / e, rc=op[(L['cp'], 'close')][x, js - 1] / e,
                                      rl=op[(L['cp'], 'low')][x, js] / e, px=op[(L['cp'], 'close')][x, js], y=(js == jx).astype(int))))
P = pd.concat(rows, ignore_index=True); P.to_pickle(f'{OUT}/bl_d0b_panel.pkl.gz'); R['panel_rows'] = int(len(P)); R['panel_events'] = int(P.y.sum())
BINS = [0, .1, .2, .25, .3, .4, .5, .75, 1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2, 2.5, 99]
hz = []
for col in ('rh', 'rc'):
    for org in ('all', 'D-1', 'D0'):
        g = P if org == 'all' else P[P.origin == org]; t = g.groupby(pd.cut(g[col], BINS), observed=True).y.agg(['mean', 'size', 'sum']).reset_index()
        for x in t.itertuples(): hz.append(dict(price=col, origin=org, ratio_bin=str(x[1]), hazard_pct=100 * x.mean, lot_minutes=int(x.size), events=int(x.sum)))
HZ = pd.DataFrame(hz); HZ.to_csv(f'{OUT}/bl_d0b_hazard.csv', index=False)
P['hb'] = pd.cut(P.j, [0, 105, 225, 355], labels=['09:15-11:00', '11:00-13:00', '13:00-15:10']); P['rg'] = pd.cut(P.rh, [0, .25, .5, 1, 1.3, 1.6, 2, 99])
HH = P.groupby(['hb', 'rg'], observed=True).y.agg(['mean', 'size']).reset_index(); HH['hazard_pct'] = 100 * HH['mean']; HH[['hb', 'rg', 'hazard_pct', 'size']].astype(str).to_csv(f'{OUT}/bl_d0b_hazard_hour.csv', index=False)
print(HH.pivot(index='rg', columns='hb', values='hazard_pct').round(2).to_string())
a = HZ[(HZ.price == 'rh') & (HZ.origin == 'all')]; print(a.round(2).to_string(index=False))
# ---------------- B3 clocking
XS['sec0'] = ((XS.tod % 60).round() % 60 == 0); XS['blk'] = ((XS.tod - 33300) // 60) % 15; b3 = []
for g_, d in [('all', XS)] + list(XS.groupby('grp')):
    b3.append(dict(group=g_, lots=len(d), sec00=d.sec0.mean(), block_min14=(d.blk == 14).mean(), block_min0=(d.blk == 0).mean(), uniform_one_minute=1 / 15))
B3 = pd.DataFrame(b3); B3.to_csv(f'{OUT}/bl_d0b_b3.csv', index=False); print(B3.round(3).to_string(index=False))
# ---------------- B4 context of in-profit buy-backs
SP = S[S.pid >= 0]; b4 = []
def ctx(d, sh=0):
    out = dict(partner=0, recentre=0, roll=0)
    for x in d.itertuples():
        t = x.tod + sh; o = 'PE' if x.cp == 'CE' else 'CE'; xl = XS[(XS.cid == x.cid) & (XS.cp == o) & (XS.strike == x.strike) & (XS.grp == 'loss')]
        out['partner'] += int(((xl.tod >= t - 60) & (xl.tod <= t + 60)).any())
        sp = SP[(SP.cid == x.cid) & (SP.tod > t) & (SP.tod <= t + 60)]; out['recentre'] += int(len(sp) > 0)
        ss = S[(S.cid == x.cid) & (S.cp == x.cp) & (S.tod > t) & (S.tod <= t + 60)]; out['roll'] += int(len(ss) > 0)
    return {k: v / max(len(d), 1) for k, v in out.items()}
for g_ in ('mid-profit', 'deep-profit', 'loss'):
    d = XS[XS.grp == g_]; real = ctx(d); n1 = ctx(d, 600); n2 = ctx(d, -600)
    for k in real: b4.append(dict(group=g_, context=k, share=real[k], null=(n1[k] + n2[k]) / 2, lots=len(d)))
B4 = pd.DataFrame(b4); B4.to_csv(f'{OUT}/bl_d0b_b4.csv', index=False); print(B4.round(3).to_string(index=False))
R['b3'] = B3.round(4).to_dict('records'); R['b4'] = B4.round(4).to_dict('records'); rec('d0b1', R)
