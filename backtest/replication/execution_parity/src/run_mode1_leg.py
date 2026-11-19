"""MODE 1 / H-LEG: per-lot stop rule evaluated on the ACTUAL book (lot_lifecycle lots, four ownership conventions) and the actual market.
For every recorded body short lot, find the first decision minute m (after entry, while the lot is open under the convention) at which LTP(previous completed close) >= k x reference.
Reference: own entry | cheapest open body-short entry of the same contract. Entries <= Rs 4 exempt. Each such lot is one simulated stop event (one lot, minute m, contract).
Compared with ACTUAL body buy-backs (num Buy) by one-to-one matching on (cycle, right, strike) within +-2 minutes, plus the phase-preserving null. All cells reported; none selected.
IN-SAMPLE; ownership-dependent through which lots are open (reported per convention). Outputs -> outputs/mode1_leg_stop*.csv"""
import warnings, sys
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import ref, compare as C
sys.path.insert(0, ref.REPL)
import data
from bt import cycles as Cy
F = ref.load_fills(); cyc = pd.read_csv(ref.CYCLES); cl = Cy.cycle_list(); NM = 375
L = pd.read_csv(f'{ref.REPL}/lot_lifecycle/outputs/lots.csv.gz', low_memory=False); L = L[(L.role == 'body') & (L.side == 'SHORT') & (~L.entry_unrecorded.astype(bool))].copy()
comp = set(zip(cyc[cyc.carry_in_known].und, cyc[cyc.carry_in_known].expiry)); L = L[[(u, e) in comp for u, e in zip(L['index'], L.expiry)]]
rowt = F.set_index('row')[['dayno', 'j']]; d1 = {(r.und, r.expiry): r.d1 for r in cyc.itertuples()}
L['ed'] = [0 if d == d1[(u, e)] else 1 for u, e, d in zip(L['index'], L.expiry, L.entry_day)]; L['ej'] = ref.minute_of(L.entry_sec).clip(0, 374); L['et'] = L.ed * NM + L.ej
CONV = ('FIFO', 'LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST')
for cv in CONV:
    cr = L[f'close_row_{cv}']; L[f'ct_{cv}'] = [np.nan if pd.isna(x) or x < 0 else (rowt.dayno.get(int(x), np.nan) * NM + min(max(rowt.j.get(int(x), np.nan), 0), 374)) for x in cr]
mk = {}
def px(und, exp):
    if (und, exp) not in mk:
        m = cl[(cl.und == und) & (cl.expiry == exp)].iloc[0]; c = data.load_cycle(und, exp, m.d1, m.d0); a = {}
        for d in (0, 1):
            for r in ('CE', 'PE'):
                x = np.array(c[(d, r, 'close')], float)
                for j in range(1, x.shape[1]):
                    q = np.isnan(x[:, j]); x[q, j] = x[q, j - 1]
                a[(d, r)] = x
        mk[(und, exp)] = (a, {int(k): i for i, k in enumerate(c['strikes'])})
    return mk[(und, exp)]
def series(und, exp, cp, strike):
    a, si = px(und, exp); i = si.get(int(strike))
    if i is None: return None
    s = np.concatenate([a[(0, cp)][i], a[(1, cp)][i]]); prev = np.concatenate([[np.nan], s[:-1]]); prev[NM] = s[NM - 1]; return prev                  # LTP seen by the decision at minute t = last completed close
act = F[(F.module == 'num') & (F.side == 'Buy') & (F.carry_in_known == True)].copy(); act['t'] = act.dayno * NM + act.j.clip(0, 374)
A_all = pd.DataFrame(dict(und=act.und, expiry=act.expiry, cp=act.cp, strike=act.strike, lots=act.n_lots, j=act.t % NM, day=act.dayno)); A_ex = A_all[~((A_all.day == 1) & (A_all.j >= 358))]       # b: excluding the D0 15:13+ window (flatten / end-of-day)
rows = []; nolot = 0
for cv in CONV:
    for ref_kind in ('own', 'cheapest'):
        for k in (1.55, 1.60, 1.65, 1.70):
            ev = []
            for (u, e, cp, K), g in L.groupby(['index', 'expiry', 'cp', 'strike']):
                p = series(u, e, cp, K)
                if p is None: nolot += len(g); continue
                T = 2 * NM; open_min = np.zeros(T)
                ent = g.entry_price.values; et = g.et.values; ct = g[f'ct_{cv}'].fillna(10 ** 6).values
                cheapest = np.full(T, np.inf)
                for a_, b_, c_ in zip(et, ct, ent):
                    sl = slice(int(a_) + 1, int(min(b_, T - 1)) + 1); cheapest[sl] = np.minimum(cheapest[sl], c_)
                for a_, b_, c_ in zip(et, ct, ent):
                    lo = int(a_) + 1; hi = int(min(b_, T - 1)); 
                    if lo > hi: continue
                    refv = c_ if ref_kind == 'own' else cheapest[lo:hi + 1]
                    ok = (refv > 4.0) if ref_kind == 'own' else (refv > 4.0)
                    cond = (p[lo:hi + 1] >= k * refv) & ok & ~np.isnan(p[lo:hi + 1])
                    if np.any(cond): m = lo + int(np.argmax(cond)); ev.append((u, e, cp, int(K), 1, m % NM, m // NM))
            S = pd.DataFrame(ev, columns=['und', 'expiry', 'cp', 'strike', 'lots', 'j', 'day'])
            for name, A in (('all body buy-backs', A_all), ('excl. D0 15:13+', A_ex)):
                o = C.agree_with_null(S, A, 2, 'same', ndraw=20) if len(S) else dict(matched=0, n_sim=0, n_act=int(A.lots.sum()), P=np.nan, R=0.0, null_P=np.nan, null_R=np.nan, lift_P=np.nan, lift_R=np.nan)
                rows.append(dict(convention=cv, reference=ref_kind, k=k, actual_set=name, tol_min=2, **{kk: o[kk] for kk in ('matched', 'n_sim', 'n_act', 'P', 'R', 'null_P', 'null_R', 'lift_P', 'lift_R')}, cls=C.classify(o)))
R_ = pd.DataFrame(rows); R_.to_csv(f'{ref.OUT}/mode1_leg_stop.csv', index=False); pd.set_option('display.width', 250)
print('lots without market data:', nolot); print(R_[R_.actual_set == 'all body buy-backs'].round(3).to_string(index=False)); print(R_.groupby(['actual_set', 'cls']).size())
