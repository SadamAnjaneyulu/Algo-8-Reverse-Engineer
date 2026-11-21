"""Solo decode step 1: option one-minute OHLC cache for D-1 (Breeze option bars incl. high/low) and the solo-sale order table with the state at each sale.
Outputs outputs/bl_opt_ohlc.pkl.gz ((und, expiry) -> {'K': strikes, ('CE'|'PE', 'open'|'high'|'low'|'close'): K x 375}), outputs/bl_sd_orders.pkl.gz"""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
OPATH = f'{OUT}/bl_opt_ohlc.pkl.gz'
def build_opt():
    import data as D
    S = D.Src(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); out = {}
    for r in CY.itertuples():
        x = S.csv(f'normalized/{r.und.lower()}/options/exp{r.expiry}_{r.d1}.csv'); h = x.datetime.str.slice(11, 16).map(D.MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int))
        K = np.array(sorted(x.strike.unique()), float); ki = {k: i for i, k in enumerate(K)}; o = {'K': K}
        for cp in ('CE', 'PE'):
            z = x[x.right == cp]
            for col in ('open', 'high', 'low', 'close'):
                a = np.full((len(K), 375), np.nan); a[z.strike.map(ki).values, z.j.values] = z[col].values; o[(cp, col)] = pd.DataFrame(a).T.ffill().T.values
        out[(r.und, r.expiry)] = o
    pd.to_pickle(out, OPATH); return out
def load_opt(): return pd.read_pickle(OPATH) if os.path.exists(OPATH) else build_opt()
if __name__ == '__main__':
    OP = load_opt(); OH = bl_ohlc.load(); O = load_orders(); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); rows = []
    for cid, r in enumerate(CY.itertuples()):
        u, e = r.und, r.expiry; sp = OH[(u, e)]; step = ref.STEP[u]; op = OP[(u, e)]; K = op['K']
        s = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & (O.role == 'open_short')].sort_values(['te', 'row']); g = Pr[(Pr.und == u) & (Pr.expiry == e)]; used = set(); typ = []
        for o in s.itertuples():
            t = 'solo'
            for p in g[(g.strike == o.strike) & ((g.te - o.te).abs() <= 3)].itertuples():
                if (p.Index, o.cp) not in used: used.add((p.Index, o.cp)); t = 'scheduled' if p.sched else 'reactive'; break
            typ.append(t)
        s = s.assign(typ=typ, cid=cid, j=((s.te - 33300) // 60).astype(int))
        for o in s.itertuples():
            j = min(max(o.j, 1), 374); atm = K[np.argmin(np.abs(K - sp.close.values[j - 1]))]
            rows.append(dict(cid=cid, und=u, expiry=e, te=o.te, j=o.j, cp=o.cp, strike=int(o.strike), lots=int(o.lots), px=o.px_avg, typ=o.typ, off_atm=(o.strike - atm) / step, step=step))
    D = pd.DataFrame(rows); D['deep'] = (D.off_atm.abs() >= 5) & (D.typ == 'solo'); D.to_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); print(D.groupby(['typ', 'deep']).lots.agg(['size', 'sum']))
