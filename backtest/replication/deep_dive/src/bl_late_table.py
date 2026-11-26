"""Late D-1 sale table (D-1 from 14:15 to 15:40): every real short-opening order with the book state just before it, the index state and the last sales.
Spot after 15:29 = last 15:29 close (index static). Output outputs/late/late_sales.csv (one row per real order)."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from collections import defaultdict
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; LT = f'{OUT}/late'; os.makedirs(LT, exist_ok=True); CAS = '2026-08-03'; J0 = 300
O = DG.real_orders(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok].set_index(['und', 'expiry']); rows = []
for (u, e), g in O[O.dayno == 0].groupby(['und', 'expiry']):
    if (u, e) not in T.index: continue
    t = T.loc[(u, e)]; c = S.load(u, e); sp = c['spot1']; C, H, L = (sp[k].values.astype(float) for k in ('close', 'high', 'low')); K = c['opt1']['K']; st = S.ref.STEP[u]
    pos = defaultdict(int); last = {'CE': None, 'PE': None}; last_any = None; prev_t = None
    for r in g.itertuples():
        j = int(r.t_last // 60 - 555); jj = min(max(j, 1), 374); Sp = C[jj - 1]; atm = float(K[np.argmin(np.abs(K - Sp))]); key = (r.cp, int(r.strike))
        if r.role == 'open_short' and j >= J0:
            sc = sum(-v for (cp, k), v in pos.items() if cp == 'CE' and v < 0); spe = sum(-v for (cp, k), v in pos.items() if cp == 'PE' and v < 0)
            lc = sum(v for (cp, k), v in pos.items() if cp == 'CE' and v > 0); lpe = sum(v for (cp, k), v in pos.items() if cp == 'PE' and v > 0)
            sgn = 1 if r.cp == 'CE' else -1; ls = last[r.cp]; lo = max(jj - 60, 0)
            same_side_strikes = {k: -v for (cp, k), v in pos.items() if cp == r.cp and v < 0}
            rows.append(dict(und=u, expiry=e, d1=t.d1, era='after' if t.d0 >= CAS else 'before', t=r.t_last, j=j, cp=r.cp, strike=int(r.strike), lots=int(r.lots), premium=r.px_avg, spot=Sp, atm=atm,
                             offset=sgn * (r.strike - atm) / st, short_CE=sc, short_PE=spe, long_CE=lc, long_PE=lpe, imb_same_minus_other=(sc - spe) * sgn,
                             last_strike=ls['k'] if ls else np.nan, last_price=ls['p'] if ls else np.nan, last_j=ls['j'] if ls else np.nan, same_as_last=bool(ls and ls['k'] == r.strike),
                             strike_held_short=int(r.strike) in same_side_strikes, biggest_short_strike=max(same_side_strikes, key=same_side_strikes.get) if same_side_strikes else np.nan,
                             spot_move_15=Sp - C[max(jj - 16, 0)], new_low_60=bool(L[jj - 1] <= L[lo:jj].min()) if jj > 1 else False, new_high_60=bool(H[jj - 1] >= H[lo:jj].max()) if jj > 1 else False,
                             secs_since_prev_order=(r.t_last - prev_t) if prev_t is not None else np.nan, last_any_cp=last_any))
        if r.role == 'open_short': last[r.cp] = dict(k=int(r.strike), p=r.px_avg, j=j); last_any = r.cp
        pos[key] += r.sg * int(r.lots); prev_t = r.t_last
D = pd.DataFrame(rows); D.to_csv(f'{LT}/late_sales.csv', index=False)
pd.set_option('display.width', 250)
for era, g in D.groupby('era'):
    print(f'== {era}: {len(g)} orders, {g.lots.sum()} lots, {g.expiry.nunique()} cycles')
    print('offset (steps OTM) distribution:', g.offset.value_counts().sort_index().to_dict())
    print('same strike as last same-side sale %.2f | strike already held short %.2f | side CE %.2f | side = the side with MORE shorts already %.2f | after a new 60-min low %.2f / high %.2f'
          % (g.same_as_last.mean(), g.strike_held_short.mean(), (g.cp == 'CE').mean(), (g.imb_same_minus_other > 0).mean(), g.new_low_60.mean(), g.new_high_60.mean()))
    print('CE share when spot fell 15m: %.2f, rose: %.2f | lots>1 share %.2f' % ((g[g.spot_move_15 < 0].cp == 'CE').mean(), (g[g.spot_move_15 > 0].cp == 'CE').mean(), (g.lots > 1).mean()))
