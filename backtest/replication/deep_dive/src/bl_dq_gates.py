"""Decoding step 3: what gates (a) a first break that gets no entry and (b) a repeat entry, using a broad feature set: market (extension, minute range, speed, minute-in-candle), option microstructure (target-strike volume net of Algo 8's own fills, premium change), portfolio (short lots, delta, ITM short lots, MTM P&L and its change, wing coverage), clock/schedule.
Outputs bl_dq_gate_first.csv, bl_dq_gate_repeat.csv, bl_dq_gate_models.csv, bl_summary_dq4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
exec(open('bl_dq_ohlc.py').read().split("rows = []\nfor nm, kw")[0])
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
R = {}; ch = Chain(); O = load_orders(); unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}
def feats(d, cb, j, s, first_j, n_prev, H, L):
    k = (d['und'], d['expiry']); c = ch.cyc(*k); K_ = np.array(c['strikes'], float); atm = K_[np.argmin(np.abs(K_ - d['c'][max(j - 1, 0)]))]; tgt = atm + s * d['step']; ki = int(np.argmin(np.abs(K_ - tgt)))
    vol = lambda jj: (c[(0, 'CE', 'volume')][ki, jj] + c[(0, 'PE', 'volume')][ki, jj]) if 0 <= jj < 375 else np.nan
    z = O[(O.und == k[0]) & (O.expiry == k[1]) & (O.dayno == 0) & (O.strike == tgt)]; own = lambda jj: z[((z.te - 33300) // 60) == jj].lots.sum() * unit[k]
    v1 = vol(j - 1) - own(j - 1); vh = np.nanmean([vol(x) - own(x) for x in range(max(j - 31, 0), j - 1)])
    prem = lambda jj: c[(0, 'CE', 'close')][ki, jj] + c[(0, 'PE', 'close')][ki, jj]
    st = cb.state(33300 + 60 * j, d['c'][max(j - 1, 0)], max(j - 1, 0)); st15 = cb.state(33300 + 60 * j - 900, d['c'][max(j - 16, 0)], max(j - 16, 0), pnl_only=True)
    ext = (d['h'][j] - H) / d['step'] if s > 0 else (L - d['l'][j]) / d['step']
    return dict(ext_beyond_channel=ext, minute_range=(d['h'][j] - d['l'][j]) / d['step'], ret5=s * (d['c'][max(j - 1, 0)] - d['c'][max(j - 6, 0)]) / d['step'], ret15=s * (d['c'][max(j - 1, 0)] - d['c'][max(j - 16, 0)]) / d['step'], chan_width=(H - L) / d['step'],
                min_in_candle=((33300 + 60 * j) % 1800) / 60, min_since_first=(j - first_j) if first_j is not None else np.nan, n_prev_in_candle=n_prev, hour=(33300 + 60 * j) / 3600,
                vol_net_prev=v1, vol_rel=v1 / vh if vh and vh > 0 else np.nan, prem_chg5=prem(j - 1) / prem(max(j - 6, 0)) - 1 if prem(max(j - 6, 0)) > 0 else np.nan, prem_tgt=prem(j - 1),
                short_lots=st.get('short_lots', np.nan), delta_vs_side=-s * st.get('delta', np.nan), itm_short=st.get('itm_short', np.nan), pnl=st.get('pnl_pct', np.nan), pnl_chg15=st.get('pnl_pct', np.nan) - st15['pnl_pct'], cover=(st.get('net_lots', np.nan) + st.get('short_lots', np.nan)) / max(st.get('short_lots', 1), 1))
first_rows = []; rep_rows = []
for d in CYC:
    k = (d['und'], d['expiry']); cb = CycleBook(k[0], k[1], unit[k]); fi = machine(d); A = set(d['A'])
    firsts = {}
    for f, s in fi:
        b = (33300 + 60 * f) // 1800; firsts[(b, s)] = f; H, L = chan(d, f, 2, 'hl')
        r = feats(d, cb, f, s, f, 0, H, L); r.update(cid=d['cid'], y=int(any(abs(a - f) <= 1 for a in A))); first_rows.append(r)
    # eligible repeat minutes: after the first entry (same side, same candle), the minute makes a new running candle extreme beyond the channel
    for (b, s), f0 in firsts.items():
        b_start = int((b * 1800 - 33300) // 60); n_prev = 1; last = f0
        for j in range(f0 + 2, min(b_start + 30, J1 + 1)):
            H, L = chan(d, j, 2, 'hl'); run = d['h'][b_start:j].max() if s > 0 else d['l'][b_start:j].min()
            if not ((d['h'][j] > max(run, H)) if s > 0 else (d['l'][j] < min(run, L))): continue
            y = int(j in A); r = feats(d, cb, j, s, f0, n_prev, H, L); r.update(cid=d['cid'], y=y, min_since_last=j - last, j=j, side=s); rep_rows.append(r)
            if y: n_prev += 1; last = j
F1d = pd.DataFrame(first_rows); RPd = pd.DataFrame(rep_rows); F1d.to_csv(f'{OUT}/bl_dq_gate_first_rows.csv', index=False); RPd.to_csv(f'{OUT}/bl_dq_gate_repeat_rows.csv', index=False)
print('first breaks', len(F1d), 'with entry', int(F1d.y.sum()), '| eligible repeat minutes', len(RPd), 'with re-entry', int(RPd.y.sum()))
def auc(x, y):
    m = ~np.isnan(x); x = x[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1
    return np.nan if n1 < 5 or n0 < 5 else (rankdata(x)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
out = {}
for nm, D in (('first', F1d), ('repeat', RPd)):
    y = D.y.values; half = D.cid.values % 2 == 0; rows = []
    for v in [c for c in D.columns if c not in ('cid', 'y', 'j', 'side')]:
        x = D[v].values.astype(float); rows.append(dict(variable=v, AUC=auc(x, y), AUC_even=auc(x[half], y[half]), AUC_odd=auc(x[~half], y[~half])))
    U = pd.DataFrame(rows); U['s'] = (U.AUC - .5).abs(); U = U.sort_values('s', ascending=False).drop(columns='s'); U.round(3).to_csv(f'{OUT}/bl_dq_gate_{nm}.csv', index=False); print(nm); print(U.round(3).head(12).to_string(index=False)); out[nm] = U.round(4).to_dict('records')
# LOCO models for the repeat gate
D = RPd.reset_index(drop=True); y = D.y.values; cid = D.cid.values; cols = [c for c in D.columns if c not in ('cid', 'y', 'j', 'side')]; mrows = []
def loco(cs, kind):
    X = D[cs].values.astype(float); p = np.zeros(len(y))
    for c_ in np.unique(cid):
        te = cid == c_; tr = ~te
        if y[tr].sum() < 3: continue
        if kind == 'lr': med = np.nanmedian(X[tr], 0); med = np.where(np.isnan(med), 0, med); Xt = np.where(np.isnan(X), med, X); sc = StandardScaler().fit(Xt[tr]); p[te] = LogisticRegression(C=0.3, max_iter=500).fit(sc.transform(Xt[tr]), y[tr]).predict_proba(sc.transform(Xt[te]))[:, 1]
        else: p[te] = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=15, l2_regularization=1.0, random_state=0).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return p
blocks = dict(market=['ext_beyond_channel', 'minute_range', 'ret5', 'ret15', 'chan_width', 'min_in_candle', 'min_since_first', 'min_since_last', 'n_prev_in_candle', 'hour'], volume_premium=['vol_net_prev', 'vol_rel', 'prem_chg5', 'prem_tgt'], portfolio=['short_lots', 'delta_vs_side', 'itm_short', 'pnl', 'pnl_chg15', 'cover'])
for nm, cs in list(blocks.items()) + [('all', cols)]:
    for kd in ('lr', 'gb'): p = loco(cs, kd); mrows.append(dict(block=nm, model=kd, AUC=auc(p, y)))
M = pd.DataFrame(mrows); M.round(3).to_csv(f'{OUT}/bl_dq_gate_models.csv', index=False); print(M.round(3).to_string(index=False)); R['univariate'] = out; R['models'] = M.round(4).to_dict('records'); R['n_first'] = len(F1d); R['n_first_entry'] = int(F1d.y.sum()); R['n_rep'] = len(RPd); R['n_rep_entry'] = int(RPd.y.sum()); rec('dq4', R)
