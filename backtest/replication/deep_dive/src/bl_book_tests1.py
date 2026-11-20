"""Capital-loss trigger study, part 1 (plan tests 1b, 2, 3, 5, 6): where in the book-P&L distribution do the sub-1.2x buy-backs sit? Output bl_book_*.csv, bl_summary_book1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(11); R = {}; C = 2e7; LAKH = 1e5
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz'); V = pd.read_csv(f'{OUT}/bl_book_validation.csv'); O = load_orders()
cl = pd.concat([pd.read_csv(f'{OUT}/bl_close_orders_clusters_{d}.csv') for d in ('D-1', 'D0')])
cl['klass'] = np.where(cl.r_low >= 1.5, 'stop-like (>=1.5x)', np.where(cl.r_low >= 1.2, 'middle (1.2-1.5x)', np.where(cl.cl_has_stop, 'sub-1.2x co-closed', 'sub-1.2x residual')))
cl = cl.merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left'); cl['B_own'] = np.where(cl.cp == 'CE', cl.B_CE, cl.B_PE); cl['B_oth'] = np.where(cl.cp == 'CE', cl.B_PE, cl.B_CE); cl.to_csv(f'{OUT}/bl_book_events.csv', index=False)
# ---- 1b: U8 check: book P&L at the first s_ order of each cycle (causal, previous-minute marks)
S = O[O.module == 's_'].sort_values('te').groupby(['und', 'expiry']).first().reset_index()[['und', 'expiry', 'dayno', 'te', 'tod', 'jj']]; S['day'] = np.where(S.dayno == 0, 'D-1', 'D0'); S['j'] = ((S.tod - ref.OPEN_SEC) // 60).clip(0, 374).astype(int)
S = S.merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left'); S['B_lakh'] = S.B_total / LAKH; S['B_pct'] = S.B_total / C * 100; S['Bday_lakh'] = S.B_day / LAKH; S['DD_lakh'] = S.DD / LAKH
S[['und', 'expiry', 'day', 'j', 'B_lakh', 'B_pct', 'Bday_lakh', 'DD_lakh']].round(3).to_csv(f'{OUT}/bl_book_first_stop.csv', index=False); R['first_stop_n'] = len(S); R['first_stop_B_lakh_q'] = S.B_lakh.quantile([.1, .25, .5, .75, .9]).tolist(); R['first_stop_Bday_lakh_q'] = S.Bday_lakh.quantile([.1, .25, .5, .75, .9]).tolist(); R['first_stop_DD_lakh_q'] = S.DD_lakh.quantile([.1, .25, .5, .75, .9]).tolist()
print(f'first s_ order per cycle: {len(S)} cycles; B_total (lakh) quantiles 10/25/50/75/90: {np.round(R["first_stop_B_lakh_q"], 2)}; B_day {np.round(R["first_stop_Bday_lakh_q"], 2)}; DD {np.round(R["first_stop_DD_lakh_q"], 2)}')
# ---- 2: event table by class
rows = []
for day in ('D-1', 'D0'):
    for k, g in cl[cl.day == day].groupby('klass'):
        rows.append((day, k, len(g), *[np.nanmedian(g[v]) / LAKH for v in ('B_total', 'B_day', 'DD', 'dB15', 'B_own', 'B_oth')], (g.B_total <= -0.5 * LAKH).mean(), (g.B_total <= -1.0 * LAKH).mean(), (g.B_day <= -0.5 * LAKH).mean()))
T2 = pd.DataFrame(rows, columns=['day', 'class', 'orders', 'B_total_med_lakh', 'B_day_med_lakh', 'DD_med_lakh', 'dB15_med_lakh', 'B_own_med_lakh', 'B_oth_med_lakh', 'share_Btotal<=-0.5L', 'share_Btotal<=-1.0L', 'share_Bday<=-0.5L']).round(3); T2.to_csv(f'{OUT}/bl_book_event_classes.csv', index=False); print(T2.to_string(index=False))
# ---- control distribution: cycle-minutes with body shorts open (panel2), minute >= 5
P2 = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz', usecols=['und', 'expiry', 'day', 'j']).drop_duplicates(); P2 = P2.merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left'); P2['bb_A'] = 0; P2['bb_B'] = 0; P2['bb_S'] = 0
cnt = cl.assign(A=(cl.klass.str.startswith('sub')).astype(int), B=(cl.klass == 'sub-1.2x residual').astype(int), S=(cl.klass == 'stop-like (>=1.5x)').astype(int)).groupby(['und', 'expiry', 'day', 'j'])[['A', 'B', 'S']].sum().reset_index()
P2 = P2.drop(columns=['bb_A', 'bb_B', 'bb_S']).merge(cnt, on=['und', 'expiry', 'day', 'j'], how='left').fillna({'A': 0, 'B': 0, 'S': 0}); P2.to_csv(f'{OUT}/bl_book_cycle_minutes.csv.gz', index=False)
# ---- 3: hazard scan by bin of each variable (events = cycle-minutes with >= 1 target order)
BINS = {'B_total': [-1e9, -1.0, -0.5, -0.25, 0, 0.25, 0.5, 1.0, 1e9], 'B_day': [-1e9, -1.0, -0.5, -0.25, 0, 0.25, 0.5, 1.0, 1e9], 'DD': [-1, 0.0001, 0.25, 0.5, 1.0, 1e9], 'dB15': [-1e9, -0.5, -0.25, -0.1, 0.1, 0.25, 0.5, 1e9]}
HZ = []
for day in ('D-1', 'D0'):
    Q = P2[P2.day == day].copy()
    for v, b in BINS.items():
        x = Q[v] / LAKH
        for tgt in ('A', 'B', 'S'):
            t = Q.groupby(pd.cut(x, b), observed=False)[tgt].agg(n='size', ev=lambda s: (s > 0).sum()); t['per1000'] = t.ev / t.n * 1000; t = t.reset_index().rename(columns={v: 'bin'}); t.insert(0, 'var', v); t.insert(0, 'target', tgt); t.insert(0, 'day', day); HZ.append(t)
H = pd.concat(HZ).assign(bin=lambda d: d['bin'].astype(str)); H.to_csv(f'{OUT}/bl_book_hazard.csv', index=False)
for day in ('D-1',):
    for v in ('B_total', 'DD'):
        h = H[(H.day == day) & (H['var'] == v)].pivot(index='bin', columns='target', values='per1000').round(1); n = H[(H.day == day) & (H['var'] == v) & (H.target == 'A')].set_index('bin').n; h['cycle-minutes'] = n; print(f'\n{day} hazard per 1000 cycle-minutes by {v} (lakh): A = all sub-1.2x, B = residual, S = stop-like'); print(h.to_string())
# ---- 5: threshold-crossing event study (first minute with B_total <= -L within each cycle-day); compare target counts in next W minutes with the cycle-day base rate
cm = P2.copy(); ES = []
for day in ('D-1', 'D0'):
    for L in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5):
        for tgt in ('A', 'B', 'S'):
            obs = exp = n = 0
            for (u, e), g in cm[cm.day == day].groupby(['und', 'expiry']):
                g = g.sort_values('j'); hit = g[g.B_total <= -L * LAKH]
                if hit.empty: continue
                j0 = hit.j.iloc[0]; W = 15; w = g[(g.j >= j0) & (g.j < j0 + W)]; obs += w[tgt].sum(); exp += g[tgt].mean() * len(w); n += 1
            ES.append((day, L, tgt, n, obs, exp, obs / exp if exp > 0 else np.nan))
ES = pd.DataFrame(ES, columns=['day', 'L_lakh', 'target', 'cycles_crossing', 'orders_next15', 'expected_at_base_rate', 'ratio']).round(3); ES.to_csv(f'{OUT}/bl_book_crossing.csv', index=False); print('\ncrossing event study (next 15 min, D-1):'); print(ES[ES.day == 'D-1'].pivot(index='L_lakh', columns='target', values='ratio').to_string()); print(ES[ES.day == 'D-1'].pivot(index='L_lakh', columns='target', values='cycles_crossing').to_string())
# ---- 6: s_ adjacency
for day in ('D-1', 'D0'):
    d = cl[(cl.day == day)]; so = O[(O.module == 's_') & (O.dayno == (0 if day == 'D-1' else 1))]
    for nm, mask in (('A all sub-1.2x', d.klass.str.startswith('sub')), ('B residual', d.klass == 'sub-1.2x residual'), ('S stop-like', d.klass == 'stop-like (>=1.5x)')):
        obs = []; null = []
        for (u, e), g in d[mask].groupby(['und', 'expiry']):
            st = so[(so.und == u) & (so.expiry == e)].te.values
            if len(st) == 0: continue
            te = g.te.values; allt = d[(d.und == u) & (d.expiry == e)].te.values; lo, hi = allt.min(), allt.max(); span = max(hi - lo, 1)
            obs.append((np.mean([(np.abs(st - t) <= 60).any() for t in te]), len(te))); nn = [np.mean([(np.abs(st - t) <= 60).any() for t in lo + ((te - lo + rng.uniform(0, span)) % span)]) for _ in range(40)]; null.append((np.mean(nn), len(te)))
        if obs: w = np.array([x[1] for x in obs]); R[f'stopadj_{day}_{nm}'] = [float(np.average([x[0] for x in obs], weights=w)), float(np.average([x[0] for x in null], weights=w)), int(w.sum()), len(obs)]; print(f'{day} {nm}: within 60 s of an s_ order {R[f"stopadj_{day}_{nm}"][0]:.3f} vs shifted null {R[f"stopadj_{day}_{nm}"][1]:.3f} (n={int(w.sum())}, cycles with s_ {len(obs)})')
rec('book1', R)
