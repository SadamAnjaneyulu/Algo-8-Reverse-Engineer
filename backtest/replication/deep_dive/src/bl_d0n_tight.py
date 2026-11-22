"""N4b: what the same-instant (|lag| <= 2 s) sales are. Post-hoc follow-up to N4 (labelled post-hoc in the report).
Outputs bl_d0n_tight.csv (per tight sale), bl_d0n_tight_sum.csv, bl_summary_d0n3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import json
from scipy.stats import spearmanr
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz')
rng = np.random.default_rng(97); R = {}; other = lambda c: 'PE' if c == 'CE' else 'CE'
EV = X.groupby(['cid', 'cp', 'tod']).agg(lots=('lid', 'size'), type=('type', lambda s: s.value_counts().idxmax()), strike=('strike', 'median'), px=('px', 'median'), entry=('entry', 'median'), ratio=('ratio', 'median'), j=('j', 'min')).reset_index()
def nearest(q, lim=2):
    b = EV[(EV.cid == q.cid) & (EV.cp == other(q.cp))]; d = b.tod.values - q.tod; k = np.abs(d) <= lim
    if not k.any(): return None
    z = b[k].iloc[np.argmin(np.abs(d[k]))]; return z, float(d[k][np.argmin(np.abs(d[k]))])
rows = []
for q in SO.itertuples():
    m = nearest(q)
    if m is None: continue
    z, lag = m; rows.append(dict(cid=q.cid, tod=q.tod, cp=q.cp, sold_lots=q.lots, sold_px=q.px, sold_strike=q.strike, lag_s=-lag, bb_lots=z.lots, bb_type=z.type, bb_px=z.px, bb_strike=z.strike, bb_ratio=z.ratio, label=q.type, j=q.j))
Tt = pd.DataFrame(rows); Tt['same_strike'] = Tt.sold_strike == Tt.bb_strike; Tt['sold_over_bought_lots'] = Tt.sold_lots / Tt.bb_lots; Tt['px_ratio'] = Tt.sold_px / Tt.bb_px; Tt.to_csv(f'{OUT}/bl_d0n_tight.csv', index=False)
R['n_tight_orders'] = len(Tt); R['n_tight_lots'] = int(Tt.sold_lots.sum()); R['share_of_solo_lots'] = float(Tt.sold_lots.sum() / SO.lots.sum()); R['lag_s_q'] = Tt.lag_s.quantile([.05, .25, .5, .75, .95]).tolist(); R['share_sale_before_or_same'] = float((Tt.lag_s <= 0).mean()); R['share_lag_zero'] = float((Tt.lag_s == 0).mean())
R['by_bb_type'] = Tt.groupby('bb_type').agg(orders=('sold_lots', 'size'), lots=('sold_lots', 'sum'), median_bb_lots=('bb_lots', 'median')).to_dict('index')
R['label_mix'] = Tt.label.value_counts().to_dict()
R['lots_equal'] = float((Tt.sold_lots == Tt.bb_lots).mean()); R['spearman_sold_vs_bought_lots'] = float(spearmanr(Tt.sold_lots, Tt.bb_lots)[0]); R['median_sold_over_bought_lots'] = float(Tt.sold_over_bought_lots.median())
R['same_strike'] = float(Tt.same_strike.mean()); R['px_ratio_q'] = Tt.px_ratio.quantile([.1, .25, .5, .75, .9]).tolist(); R['median_sold_lots'] = float(Tt.sold_lots.median()); R['bb_lots_q'] = Tt.bb_lots.quantile([.25, .5, .75, .95]).tolist()
# which stop-loss events have a tight sale (event-level)
SL = EV[EV.type == '3 stop-loss'].copy()
def has(q, lim=2):
    s = SO[(SO.cid == q.cid) & (SO.cp == other(q.cp))].tod.values; return bool((np.abs(s - q.tod) <= lim).any())
SL['t60'] = [has(q, 60) for q in SL.itertuples()]; SL['tight'] = [has(q) for q in SL.itertuples()]; R['stop_loss_events'] = len(SL); R['stop_loss_events_with_tight_sale'] = float(SL.tight.mean())
SL['hour'] = (SL.tod // 3600).astype(int); R['tight_by_hour'] = SL.groupby('hour').tight.mean().round(3).to_dict(); R['tight_by_lots_bought'] = {str(k): float(v) for k, v in SL.groupby(pd.cut(SL.lots, [0, 1, 2, 4, 100])).tight.mean().round(3).items()}
# every buy-back type: tight sale rate
EV['tight'] = [has(q) for q in EV.itertuples()]; TB = EV.groupby('type').agg(events=('tight', 'size'), share_with_tight_sale=('tight', 'mean')).reset_index(); TB.to_csv(f'{OUT}/bl_d0n_tight_sum.csv', index=False); print(TB.round(3).to_string(index=False))
# panel features of stop-loss events with vs without a tight sale (decision-time state of the sold right in the event minute)
K = SL.merge(PN, left_on=['cid', 'j'], right_on=['cid', 'j'], how='inner'); K = K[K.cp_y != K.cp_x]
K['atlow'] = K.prem_vs_daymin <= 1.0001; R['by_other_premium_at_low'] = {str(bool(k)): dict(events=int(len(g)), sale_within_2s=float(g.tight.mean()), sale_within_60s=float(g.t60.mean())) for k, g in K.groupby('atlow')}
for f in ('prem_vs_daymin', 'fav_ret_5', 'fav_ret_15', 'fresh_60', 'prem_chg_3', 'n_own', 'share_own', 'mtm_to_stop'):
    a = K[K.tight][f].dropna(); b = K[~K.tight][f].dropna(); R[f'feat_{f}'] = dict(tight_median=float(a.median()), other_median=float(b.median()), n=[len(a), len(b)])
R['decomp_by_bb_label'] = Tt.groupby('label').sold_lots.sum().to_dict(); rec('d0n3', R); print(json.dumps({k: v for k, v in R.items() if not k.startswith('feat_')}, indent=0, default=float)[:2500]); print({k: v for k, v in R.items() if k.startswith('feat_')})
