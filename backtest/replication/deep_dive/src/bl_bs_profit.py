"""Buy-back second pass, step 7 (descriptive): buy-backs where every open lot on the contract is in profit at the decision price (13%): coincidence with a stop on the same right, sells right after (re-centering), buy-backs on the other right, moneyness, time. Output bl_summary_bs6.json"""
import sys; sys.path.insert(0, '.')
from bl_common import *
E = pd.read_csv(f'{OUT}/bl_bb_events.csv'); G = pd.read_csv(f'{OUT}/bl_bb_eventlevel.csv'); O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}
rows = []
for nm, sub in (('all lots in profit', E[E.r_ref_min <= 1]), ('in loss (cheapest lot)', E[E.r_ref_min > 1])):
    for x in sub.itertuples():
        r = CY.iloc[x.cid]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]
        sa = SD[(SD.cid == x.cid) & (SD.te >= x.te) & (SD.te <= x.te + 10)]
        rows.append(dict(group=nm, stop_same_right_3s=int(((G.cid == x.cid) & (G.cp == x.cp) & (G.r_first >= 1.45) & ((G.te - x.te).abs() <= 3)).any()), sell_within_10s=int(len(sa) > 0), sell_same_right_10s=int((sa.cp == x.cp).any()),
                         bb_other_right_3s=int(len(z[(z.module == 'num') & (z.role == 'cover_short') & ((z.te - x.te).abs() <= 3) & (z.cp != x.cp)]) > 0), itm=x.itm_steps, after_1500=int(x.te >= 54000), sec0=int(x.sec == 0), ratio=x.r_ref_min))
Z = pd.DataFrame(rows); T = Z.groupby('group').mean(numeric_only=True).round(3); T['n'] = Z.groupby('group').size(); print(T.T.to_string())
R = {g: {k: float(v) for k, v in row.items()} for g, row in T.iterrows()}; rec('bs6', R)
