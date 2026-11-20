"""H2 dataset: for every h_ BUY order that increases protection (side Buy), attach the triggering body Sell orders (matched in bh_h1, window [1.5,20] s), decision-time reference prices recovered from limit prices (ref = lim/1.15 for Buys, lim/0.85 for Sells; k=0.15 is the modal limit cushion, an estimate), strike offsets in steps and premium ratios.
'simple' = exactly one triggering body order of 1 lot and a wing order of 1 lot. Output outputs/bh_h2_wing_buys.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
K = 0.15
O = order_table(); BL = pd.read_csv(f'{OUT}/bh_h1_body_lots.csv', dtype={'tag': str, 'wing_tag': str}); ST = ref.STEP
Bo = O[O.module == 'num'].set_index('tag'); Wo = O[O.module == 'h_'].set_index('tag')
m = BL[BL.matched & (BL.side == 'Sell')]
g = m.groupby('wing_tag').agg(n_trig_lots=('tag', 'size'), n_trig_orders=('tag', 'nunique'), trig_tags=('tag', lambda s: sorted(set(s)))).reset_index()
W = Wo[Wo.side == 'Buy'].reset_index().merge(g, left_on='tag', right_on='wing_tag', how='left')
W['n_trig_lots'] = W.n_trig_lots.fillna(0).astype(int); W['n_trig_orders'] = W.n_trig_orders.fillna(0).astype(int)
def first_trig(r):
    if not isinstance(r.trig_tags, list): return pd.Series(dict(b_strike=np.nan, b_ref=np.nan, b_fill=np.nan, b_tt=np.nan))
    b = Bo.loc[r.trig_tags[0]]; return pd.Series(dict(b_strike=b.strike, b_ref=b.lim_px / (1 - K), b_fill=b.px_first, b_tt=b.tt_first))
W = pd.concat([W, W.apply(first_trig, axis=1)], axis=1)
W['w_ref'] = W.lim_px / (1 + K); W['step'] = W.und.map(ST)
W['off_steps'] = np.where(W.cp == 'CE', W.strike - W.b_strike, W.b_strike - W.strike) / W.step      # + = further OTM than the sold strike
W['ratio_ref'] = W.w_ref / W.b_ref; W['ratio_fill'] = W.px_first / W.b_fill
W['simple'] = (W.n_trig_orders == 1) & (W.n_trig_lots == 1) & (W.lots == 1)
W.drop(columns=['trig_tags']).to_csv(f'{OUT}/bh_h2_wing_buys.csv', index=False)
s = W[W.simple]
print('wing Buy orders', len(W), 'with a trigger', int((W.n_trig_lots > 0).sum()), 'simple', len(s), 'cycles', s.groupby(['und', 'expiry']).ngroups)
print('offset (steps OTM) quantiles', s.off_steps.quantile([.05, .25, .5, .75, .95]).tolist()); print('ratio_ref quantiles', s.ratio_ref.quantile([.05, .25, .5, .75, .95]).round(4).tolist())
print(s.groupby(['und', 'dayno']).agg(n=('tag', 'size'), off_med=('off_steps', 'median'), ratio_med=('ratio_ref', 'median'), wref_med=('w_ref', 'median')).round(3))
