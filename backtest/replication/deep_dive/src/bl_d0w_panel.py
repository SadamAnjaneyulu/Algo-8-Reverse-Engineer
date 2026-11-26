"""D0 burst buy-backs and body-stream longs, step 1: enriched minute-cell panel (plan reports/D0_BURST_LONG_PLAN.md).
Adds to the 14,962-cell panel of bl_d0f_panel (cycle x minute x right, j >= 1 used): lot-state features of the right at the start of the minute (bars to j-1 only: ITM depth, drift, side loss, lots at risk),
buy-back outcomes by type from bl_d0y_lots, body-stream long outcomes and book state (S, L per right at j-1 from bl_d0u_timeline), premium at the long-strike target.
Also builds the lot-level table for burst cells (which lots a burst takes).
Outputs bl_d0w_panel.pkl.gz, bl_d0w_burstlots.pkl.gz, bl_summary_d0w1.json"""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); R = {}
PN = pd.read_pickle(f'{OUT}/bl_d0f_panel.pkl.gz').reset_index(drop=True); PN = PN[PN.j >= 1].copy()
Pn = pd.read_pickle(f'{OUT}/bl_d0b_panel.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); TL = pd.read_pickle(f'{OUT}/bl_d0u_timeline.pkl.gz')
UNIT = CY.unit.values.astype(float); STEP = np.array([ref.STEP[u] for u in CY.und]); cl = {i: SPT[(CY.und[i], CY.expiry[i])].close.values for i in range(len(CY)) if (CY.und[i], CY.expiry[i]) in SPT}
# ---------- lot state at the start of minute j (bars to j-1)
Pn = Pn.sort_values(['lid', 'j']).reset_index(drop=True); g = Pn.groupby('lid'); Pn['px_prev'] = g.px.shift(1); jp_ = g.j.shift(1); Pn.loc[jp_ != Pn.j - 1, 'px_prev'] = np.nan
Pn['px_prev'] = Pn.px_prev.fillna(Pn.entry); Pn['ratio_prev'] = Pn.px_prev / Pn.entry
sp_prev = np.array([cl[c][j - 1] if c in cl else np.nan for c, j in zip(Pn.cid.values, Pn.j.values)]); st = STEP[Pn.cid.values]; u = UNIT[Pn.cid.values]
Pn['itm'] = np.where(Pn.cp.values == 'CE', (sp_prev - Pn.strike.values) / st, (Pn.strike.values - sp_prev) / st); Pn['loss'] = (Pn.px_prev - Pn.entry) * u / 1e5; Pn['coll'] = Pn.entry * u / 1e5
Pn['carried'] = (Pn.origin == 'D-1').astype(float)
Pn['r12'] = (Pn.ratio_prev >= 1.2).astype(int); Pn['r14'] = (Pn.ratio_prev >= 1.4).astype(int)
for k in (1, 2, 3, 5, 8): Pn[f'i{k}'] = (Pn.itm >= k).astype(int)
A = Pn.groupby(['cid', 'j', 'cp']).agg(n_open=('lid', 'size'), n_itm1=('i1', 'sum'), n_itm2=('i2', 'sum'), n_itm3=('i3', 'sum'), n_itm5=('i5', 'sum'), n_itm8=('i8', 'sum'), max_itm=('itm', 'max'), mean_itm=('itm', 'mean'), min_itm=('itm', 'min'),
                                       loss_lakh=('loss', 'sum'), coll_lakh=('coll', 'sum'), n_r12=('r12', 'sum'), n_r14=('r14', 'sum'), max_ratio_prev=('ratio_prev', 'max'), mean_ratio_prev=('ratio_prev', 'mean'), carried_share=('carried', 'mean')).reset_index()
A['loss_pct'] = A.loss_lakh / A.coll_lakh.replace(0, np.nan); A['share_itm2'] = A.n_itm2 / A.n_open; A['share_r14'] = A.n_r14 / A.n_open
# ---------- buy-back outcomes by type (in scope: types 3-8; clearance and the cycle-stop window excluded)
Xs = X[~X.type.astype(str).str.startswith(('1', '2'))].copy(); Xs['t'] = Xs.type.astype(str).str.slice(0, 1).astype(int); cnt = Xs.groupby(['cid', 'j', 'cp', 't']).size().unstack(fill_value=0); cnt.columns = [f'n_t{c}' for c in cnt.columns]; cnt = cnt.reset_index()
B = PN.merge(A, on=['cid', 'j', 'cp'], how='left').merge(cnt, on=['cid', 'j', 'cp'], how='left')
for c in [f'n_t{t}' for t in (3, 4, 5, 6, 7, 8)]: B[c] = B[c].fillna(0) if c in B else 0
B['n_bb'] = B[[f'n_t{t}' for t in (3, 4, 5, 6, 7, 8)]].sum(axis=1); B['y_any_bb'] = (B.n_bb > 0).astype(float); B['y_burst'] = (B.n_bb >= 5).astype(float)
for t, nm in ((3, 'stop_loss'), (4, 'take_profit'), (5, 'partner'), (6, 'roll_out'), (7, 'burst_member'), (8, 'other_bb')): B[f'y_{nm}'] = (B[f'n_t{t}'] > 0).astype(float)
# ---------- body-stream longs: outcomes and book state
D = pd.read_pickle(f'{OUT}/bl_d0u_orders.pkl.gz'); key = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; D['cid'] = [key.get((a, b), -1) for a, b in zip(D.und, D.expiry)]
Lg = D[D.klass.isin(['body long buy', 'body long sell'])].groupby(['cid', 'jm', 'cp', 'klass']).lots.sum().unstack(fill_value=0).reset_index().rename(columns={'jm': 'j', 'body long buy': 'long_buy_lots', 'body long sell': 'long_sell_lots'})
B = B.merge(Lg, on=['cid', 'j', 'cp'], how='left'); B['long_buy_lots'] = B.long_buy_lots.fillna(0); B['long_sell_lots'] = B.long_sell_lots.fillna(0); B['y_long_buy'] = (B.long_buy_lots > 0).astype(float); B['y_long_sell'] = (B.long_sell_lots > 0).astype(float)
S_ = np.full(len(B), np.nan); L_ = np.full(len(B), np.nan); So = np.full(len(B), np.nan); Lo = np.full(len(B), np.nan)
for n, (c, cp, j) in enumerate(zip(B.cid.values, B.cp.values, B.j.values)):
    t = TL.get((c, cp)); o = TL.get((c, 'PE' if cp == 'CE' else 'CE'))
    if t is not None and j >= 1: S_[n] = t['S'][j - 1]; L_[n] = t['L'][j - 1]
    if o is not None and j >= 1: So[n] = o['S'][j - 1]; Lo[n] = o['L'][j - 1]
B['S_own'] = S_; B['L_own'] = L_; B['S_oth'] = So; B['L_oth'] = Lo; B['gap_own'] = B.S_own - B.L_own; B['gap_oth'] = B.S_oth - B.L_oth
# premium at the far-OTM strikes at j-1: ATM premium and the OTM strike offsets whose premium is closest to 1, 2.15, 3 Rs (diagnostic features for the long strike rule)
def otm_feats(c, cp, j):
    r = CY.iloc[c]; op = OPT.get((r.und, r.expiry))
    if op is None or j < 1: return (np.nan, np.nan, np.nan, np.nan)
    K = op['K']; pr = op[(cp, 'close')][:, j - 1]; spv = cl[c][j - 1]; stp = ref.STEP[r.und]; off = (K - spv) / stp * (1 if cp == 'CE' else -1); ok = (off > 0) & np.isfinite(pr)
    if not ok.any(): return (np.nan, np.nan, np.nan, np.nan)
    atm = K[np.argmin(np.abs(K - spv))]; a = float(op[(cp, 'close')][np.argmin(np.abs(K - spv)), j - 1]); res = [a]
    for tgt in (1.0, 2.15, 3.0): res.append(float(off[ok][np.argmin(np.abs(pr[ok] - tgt))]))
    return tuple(res)
OF = np.array([otm_feats(c, cp, j) for c, cp, j in zip(B.cid.values, B.cp.values, B.j.values)]); B['atm_prem_prev'] = OF[:, 0]; B['otm_steps_at_1'] = OF[:, 1]; B['otm_steps_at_2'] = OF[:, 2]; B['otm_steps_at_3'] = OF[:, 3]
B = B.replace([np.inf, -np.inf], np.nan); B.to_pickle(f'{OUT}/bl_d0w_panel.pkl.gz')
# ---------- lot-level table for burst cells (>= 5 lots bought back in the minute): which open lots are taken
bc = B[B.y_burst == 1][['cid', 'j', 'cp']]; Lb = Pn.merge(bc, on=['cid', 'j', 'cp']); take = Xs[['cid', 'j', 'cp', 'lid']].assign(taken=1); Lb = Lb.merge(take, on=['cid', 'j', 'cp', 'lid'], how='left'); Lb['taken'] = Lb.taken.fillna(0)
Lb['premium'] = Lb.px_prev; Lb['age_carried'] = Lb.carried; Lb.to_pickle(f'{OUT}/bl_d0w_burstlots.pkl.gz')
R.update(cells=len(B), cycles=int(B.cid.nunique()), any_bb_cells=int(B.y_any_bb.sum()), burst_cells=int(B.y_burst.sum()), lots_in_scope=int(B.n_bb.sum()), burst_lot_rows=len(Lb), burst_lots_taken=int(Lb.taken.sum()),
         long_buy_cells=int(B.y_long_buy.sum()), long_sell_cells=int(B.y_long_sell.sum()), long_buy_lots_in_panel=int(B.long_buy_lots.sum()), long_sell_lots_in_panel=int(B.long_sell_lots.sum()), missing_lot_state=float(B.n_open.isna().mean()))
rec('d0w1', R); print(json.dumps(R, indent=1)); print(B[['y_any_bb', 'y_burst', 'y_stop_loss', 'y_take_profit', 'y_partner', 'y_roll_out', 'y_burst_member', 'y_other_bb', 'y_long_buy', 'y_long_sell']].mean().round(4).to_dict())
