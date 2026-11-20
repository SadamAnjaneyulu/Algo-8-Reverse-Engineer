"""Reactive-pair study, step 2b: strike identity. Reactive pairs sit one strike off the previous-minute ATM (step 2); test whether the strike is one where the book is ALREADY short on both legs (accumulation at held strikes), the strike of the last pair, or the strike with the most existing shorts.
Reference: timetable pairs and solo sells. Contract-level inventory from all orders (ownership-free). Outputs bl_react_strike.csv, bl_summary_react1b.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); R = {}; rows = []
O1 = O[(O.dayno == 0)].copy(); O1['sl'] = np.where(O1.side == 'Buy', O1.lots, -O1.lots)
for (u, e), g in Pr.groupby(['und', 'expiry']):
    z = O1[(O1.und == u) & (O1.expiry == e)].sort_values(['te', 'row']); step = ref.STEP[u]
    for r in g.itertuples():
        zz = z[z.te < r.te - 3]; net = zz.groupby(['cp', 'strike']).sl.sum(); ce = net.xs('CE', level='cp') if 'CE' in net.index.get_level_values(0) else pd.Series(dtype=float); pe = net.xs('PE', level='cp') if 'PE' in net.index.get_level_values(0) else pd.Series(dtype=float)
        sce = -ce.clip(upper=0); spe = -pe.clip(upper=0); both = (sce.reindex(sce.index.union(spe.index), fill_value=0).clip(lower=0) * 0 + np.minimum(sce.reindex(sce.index.union(spe.index), fill_value=0), spe.reindex(sce.index.union(spe.index), fill_value=0)))
        hb = float(both.get(r.strike, 0)); topk = both.idxmax() if len(both) and both.max() > 0 else np.nan
        lastp = Pr[(Pr.und == u) & (Pr.expiry == e) & (Pr.te < r.te - 3)].sort_values('te'); lp = lastp.strike.iloc[-1] if len(lastp) else np.nan; lsp = lastp[lastp.sched].strike.iloc[-1] if lastp.sched.any() else np.nan
        rows.append((u, e, 'reactive' if r.reactive else 'scheduled', r.strike, r.atm_prev, (r.strike - r.atm_prev) / step, hb, int(hb > 0), int(r.strike == topk) if topk == topk else np.nan, int(r.strike == lp) if lp == lp else np.nan, int(r.strike == lsp) if lsp == lsp else np.nan, (r.strike - lsp) / step if lsp == lsp else np.nan))
D = pd.DataFrame(rows, columns=['und', 'expiry', 'kind', 'strike', 'atm_prev', 'off_atm_steps', 'held_both_lots', 'held_both', 'is_top_held', 'is_last_pair_strike', 'is_last_sched_strike', 'off_last_sched_steps']); D.to_csv(f'{OUT}/bl_react_strike.csv', index=False)
t = D.groupby('kind')[['held_both', 'is_top_held', 'is_last_pair_strike', 'is_last_sched_strike']].mean().round(3); print(t.to_string()); print(D[D.kind == 'reactive'].off_last_sched_steps.round(0).value_counts(normalize=True).sort_index().round(3).head(9).to_dict()); R['by_kind'] = t.to_dict('index'); R['n_react'] = int((D.kind == 'reactive').sum()); R['off_last_sched'] = D[D.kind == 'reactive'].off_last_sched_steps.round(0).value_counts(normalize=True).sort_index().round(3).to_dict()
R['react_held_both_median_lots'] = float(D[(D.kind == 'reactive')].held_both_lots.median()); print('reactive: median lots already short on BOTH legs at the strike:', R['react_held_both_median_lots'])
rec('react1b', R)
