"""After-15:00 solo, step 8 (POST-HOC): within minutes where R3 (spot 15-min extreme OR ITM premium 15-min low) holds, which panel variables separate sale from no sale? Univariate AUC, both cycle halves. Output bl_sl_cond.csv, bl_summary_sl8.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
import bl_ohlc, bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); sol = D[(D.typ == 'solo') & ~D.deep]
src = open('bl_sl_prem.py').read(); exec(src[src.index('def panel'):src.index('def auc')])
P = panel(345, 375).fillna(0); X = pd.read_pickle(f'{OUT}/bl_sl_panel.pkl.gz').drop(columns=['y', 'bk15'], errors='ignore'); M = P.merge(X, on=['cid', 'j', 'cp']); M = M[(M.bk15 == 1) | (M.pl15_itm == 1)]
def auc(s, y): m = ~np.isnan(s); s, y = s[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; return (rankdata(s)[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
y = M.y.values; h = (M.cid % 2 == 0).values; rows = []
for v in ['minute', 'fav1', 'fav5', 'fav15', 'pos60', 'rsi_fav', 'mrange', 'rv15', 'strad_chg5', 'strad_chg15', 'vol_rel', 'delta_toward', 'gamma', 'short_lots', 'net_lots', 'bb_own_2m', 'bb_oth_2m', 'lump_5m', 'react_min', 'solo_before15', 'min_since_last', 'last_typ_solo', 'bk5', 'bk60', 'is_ce']:
    x = M[v].values.astype(float); rows.append(dict(variable=v, AUC=auc(x, y), AUC_even=auc(x[h], y[h]), AUC_odd=auc(x[~h], y[~h])))
T = pd.DataFrame(rows); T['s'] = (T.AUC - .5).abs(); T = T.sort_values('s', ascending=False).drop(columns='s'); T.round(3).to_csv(f'{OUT}/bl_sl_cond.csv', index=False); print('cells', len(M), 'sales', int(y.sum())); print(T.head(10).round(3).to_string(index=False)); rec('sl8', dict(cells=len(M), sales=int(y.sum()), table=T.round(4).to_dict('records')))
